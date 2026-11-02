package syncengine

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/kingdee-sync/go/internal/config"
	"github.com/kingdee-sync/go/internal/db"
)

// findRepoConfigPath 从测试工作目录向上查找 config.local.ini，取最靠近仓库根的那一份。
// （原因：go test 的 CWD 是包目录，硬编码相对层数会随目录调整失效；
// 且 apps/server 下存在旧副本，必须优先用仓库根那份生效配置）
func findRepoConfigPath(t *testing.T) string {
	t.Helper()
	dir, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	found := ""
	for i := 0; i < 8; i++ {
		candidate := filepath.Join(dir, "config.local.ini")
		if _, err := os.Stat(candidate); err == nil {
			found = candidate
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	if found == "" {
		t.Fatal("未找到 config.local.ini")
	}
	return found
}

// TestSQLServerReplaceSnapshotIsAtomic 验证快照整体替换的事务语义：
// ① 成功换入全量覆盖；② 空快照被拒绝且目标表不变；
// ③ 换入语句在事务内失败时目标表必须保持上一轮快照（ADR-0007 的核心保证）。
// 需要 MSSQL_INTEGRATION=1 与可连的测试实例；默认跳过以免连生产库。
// （原因：mssql 写入路径无纯单测可覆盖，见 sqlserver_writer.go 中的同名单测说明）
func TestSQLServerReplaceSnapshotIsAtomic(t *testing.T) {
	if os.Getenv("MSSQL_INTEGRATION") != "1" {
		t.Skip("set MSSQL_INTEGRATION=1 to run against a dedicated SQL Server test instance")
	}
	if _, err := config.Load(findRepoConfigPath(t)); err != nil {
		t.Fatal(err)
	}
	writer := NewSQLServerWriter()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer cancel()

	// openSQL 复用全局连接，故先建立主连接（原因：ReplaceSnapshot 与建表都走全局 db.DB）
	if err := db.Init(); err != nil {
		t.Fatal(err)
	}
	handle := db.DB

	table := fmt.Sprintf("snap_it_%d", time.Now().UnixNano())
	// CHECK 约束只存在于目标表（staging 仅复制列类型与可空性），
	// 因此越界值只会在事务内 INSERT…SELECT 阶段失败，正好用来验证回滚。
	createSQL := fmt.Sprintf(
		"CREATE TABLE dbo.%s ([FID] BIGINT NOT NULL, [FGRP] BIGINT NOT NULL, [FVAL] INT NOT NULL, "+
			"[SYNC_TIME] DATETIME NULL, CONSTRAINT PK_%s PRIMARY KEY (FID, FGRP), "+
			"CONSTRAINT CK_%s CHECK (FVAL < 100))", table, table, table)
	if _, err := handle.ExecContext(ctx, createSQL); err != nil {
		t.Fatal(err)
	}
	defer func() {
		_, _ = handle.Exec("IF OBJECT_ID(N'dbo." + table + "', 'U') IS NOT NULL DROP TABLE dbo." + table)
	}()

	cols := []string{"FID", "FGRP", "FVAL", "SYNC_TIME"} // 引擎侧 appendSyncTimeCol 会追加该列，测试需同构
	pkCols := []string{"FID", "FGRP"}

	countRows := func() int64 {
		var n int64
		if err := handle.QueryRowContext(ctx, "SELECT COUNT(*) FROM dbo.["+table+"]").Scan(&n); err != nil {
			t.Fatalf("count rows: %v", err)
		}
		return n
	}
	sumVal := func() int64 {
		var s int64
		if err := handle.QueryRowContext(ctx, "SELECT SUM(FVAL) FROM dbo.["+table+"]").Scan(&s); err != nil {
			t.Fatalf("sum FVAL: %v", err)
		}
		return s
	}

	first := []map[string]interface{}{
		{"FID": int64(1), "FGRP": int64(1), "FVAL": 10},
		{"FID": int64(2), "FGRP": int64(1), "FVAL": 20},
	}
	if res, err := writer.ReplaceSnapshot(ctx, table, first, cols, pkCols, nil); err != nil {
		t.Fatalf("首轮换入失败: %v", err)
	} else if res.Total != 2 || res.Inserted != 2 {
		t.Fatalf("首轮统计 = %+v, want Total=2 Inserted=2", res)
	}
	if got := countRows(); got != 2 {
		t.Fatalf("首轮换入后行数 = %d, want 2", got)
	}
	var synced int
	if err := handle.QueryRowContext(ctx, "SELECT COUNT(*) FROM dbo.["+table+"] WHERE SYNC_TIME IS NOT NULL").Scan(&synced); err != nil {
		t.Fatal(err)
	}
	if synced != 2 {
		t.Fatalf("SYNC_TIME 非空行数 = %d, want 2（原因：水位为空会让增量窗口退化为全量）", synced)
	}

	// ② 空快照必须拒绝，且不得清空目标表
	if _, err := writer.ReplaceSnapshot(ctx, table, nil, cols, pkCols, nil); err == nil {
		t.Fatal("空快照应被拒绝")
	}
	if got := countRows(); got != 2 {
		t.Fatalf("空快照拒绝后行数 = %d, want 2", got)
	}

	// ③ 事务内失败（CHECK 约束）必须整体回滚：目标表保持上一轮快照
	bad := []map[string]interface{}{
		{"FID": int64(9), "FGRP": int64(1), "FVAL": 500},
	}
	if _, err := writer.ReplaceSnapshot(ctx, table, bad, cols, pkCols, nil); err == nil {
		t.Fatal("违反 CHECK 约束的换入应失败")
	}
	if got := countRows(); got != 2 {
		t.Fatalf("失败换入后行数 = %d, want 2（TRUNCATE 不得单独生效，否则生产表被清空）", got)
	}
	if got := sumVal(); got != 30 {
		t.Fatalf("失败换入后 SUM(FVAL) = %d, want 30（上一轮数据必须原样保留）", got)
	}

	// ④ 成功换入是全量覆盖：旧主键不存在、行数等于新快照
	second := []map[string]interface{}{
		{"FID": int64(7), "FGRP": int64(1), "FVAL": 70},
		{"FID": int64(8), "FGRP": int64(1), "FVAL": 80},
		{"FID": int64(9), "FGRP": int64(1), "FVAL": 90},
	}
	if _, err := writer.ReplaceSnapshot(ctx, table, second, cols, pkCols, nil); err != nil {
		t.Fatalf("二次换入失败: %v", err)
	}
	if got := countRows(); got != 3 {
		t.Fatalf("覆盖后行数 = %d, want 3", got)
	}
	var stale int
	if err := handle.QueryRowContext(ctx, "SELECT COUNT(*) FROM dbo.["+table+"] WHERE FID IN (1,2)").Scan(&stale); err != nil {
		t.Fatal(err)
	}
	if stale != 0 {
		t.Fatalf("覆盖后仍残留 %d 行旧快照数据", stale)
	}

	// ⑤ 失败换入不得留下孤儿 staging 表
	var leaked int
	if err := handle.QueryRowContext(ctx, "SELECT COUNT(*) FROM sys.tables WHERE name LIKE 'stg[_]%'").Scan(&leaked); err != nil {
		t.Fatal(err)
	}
	if leaked != 0 {
		t.Fatalf("残留 stg_* 表 = %d, want 0（原因：清理必须使用不被取消的上下文）", leaked)
	}
}

// 单元层面验证 ReplaceSnapshot 的前置防护，不接触数据库。
func TestReplaceSnapshotRejectsUnsafeInput(t *testing.T) {
	writer := &SQLServerWriter{}
	cols := []string{"FID"}
	pkCols := []string{"FID"}
	rows := []map[string]interface{}{{"FID": int64(1)}}

	if _, err := writer.ReplaceSnapshot(context.Background(), "bd_stock", nil, cols, pkCols, nil); err == nil {
		t.Fatal("空快照应被拒绝")
	}
	if _, err := writer.ReplaceSnapshot(context.Background(), "bd_stock; DROP TABLE x", rows, cols, pkCols, nil); err == nil {
		t.Fatal("非法表名应被拒绝")
	}
	if _, err := writer.ReplaceSnapshot(context.Background(), "bd_stock", rows, []string{"FID] NVARCHAR(9); DROP TABLE x"}, pkCols, nil); err == nil {
		t.Fatal("非法列名应被拒绝")
	}
}

func TestSupportsSnapshotReplaceRequiresCapableWriter(t *testing.T) {
	sqlWriterEngine := &SyncEngine{writer: &SQLServerWriter{}}
	if !sqlWriterEngine.supportsSnapshotReplace() {
		t.Fatal("SQLServerWriter 实现了 SnapshotReplacer，应支持单事务替换")
	}

	fakeEngine := &SyncEngine{writer: &recoveryTestWriter{}}
	if fakeEngine.supportsSnapshotReplace() {
		t.Fatal("未实现 SnapshotReplacer 的写入器不应启用替换路径")
	}

	stubbedEngine := &SyncEngine{
		writer: &SQLServerWriter{},
		writeRowsFunc: func(context.Context, string, []map[string]interface{}, []string, map[string]string) (UpsertResult, error) {
			return UpsertResult{}, nil
		},
	}
	if stubbedEngine.supportsSnapshotReplace() {
		t.Fatal("注入 writeRowsFunc 的测试替身应优先，不走替换路径")
	}
}

// 保证接口断言在编译期成立（原因：避免 supportsSnapshotReplace 因签名漂移而静默失效）
var _ SnapshotReplacer = (*SQLServerWriter)(nil)
var _ RowWriter = (*SQLServerWriter)(nil)
