package syncengine

import (
	"context"
	"database/sql"
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
	if res, err := writer.ReplaceSnapshot(ctx, table, first, cols, pkCols, nil, nil); err != nil {
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
	if _, err := writer.ReplaceSnapshot(ctx, table, nil, cols, pkCols, nil, nil); err == nil {
		t.Fatal("空快照应被拒绝")
	}
	if got := countRows(); got != 2 {
		t.Fatalf("空快照拒绝后行数 = %d, want 2", got)
	}

	// ③ 事务内失败（CHECK 约束）必须整体回滚：目标表保持上一轮快照
	bad := []map[string]interface{}{
		{"FID": int64(9), "FGRP": int64(1), "FVAL": 500},
	}
	if _, err := writer.ReplaceSnapshot(ctx, table, bad, cols, pkCols, nil, nil); err == nil {
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
	if _, err := writer.ReplaceSnapshot(ctx, table, second, cols, pkCols, nil, nil); err != nil {
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

// TestSQLServerReplaceSnapshotScoped 验证"按作用域替换"（issue #7 路线 A）：
// ① 窗口外期间必须保留；② 作用域内旧行被本批整体换入；
// ③ 作用域内失败必须整体回滚（含已删除的作用域行）；④ 作用域值为 NULL 时拒绝执行
// 且不产生任何副作用；⑤ scopeCols 为空时退化为整表替换；⑥ 不残留 staging 表。
// 需要 MSSQL_INTEGRATION=1；默认跳过以免连生产库。
func TestSQLServerReplaceSnapshotScoped(t *testing.T) {
	if os.Getenv("MSSQL_INTEGRATION") != "1" {
		t.Skip("set MSSQL_INTEGRATION=1 to run against a dedicated SQL Server test instance")
	}
	if _, err := config.Load(findRepoConfigPath(t)); err != nil {
		t.Fatal(err)
	}
	writer := NewSQLServerWriter()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer cancel()

	if err := db.Init(); err != nil {
		t.Fatal(err)
	}
	handle := db.DB

	table := fmt.Sprintf("snap_sc_%d", time.Now().UnixNano())
	// CHECK 约束只存在于目标表，因此越界值只在事务内 INSERT…SELECT 阶段失败，
	// 正好用来验证"作用域删除已执行"也会被回滚。
	createSQL := fmt.Sprintf(
		"CREATE TABLE dbo.%s ([FID] BIGINT NOT NULL, [FACCTYEAR] NVARCHAR(10) NOT NULL, "+
			"[FACCTPERIOD] NVARCHAR(10) NOT NULL, [FVAL] INT NOT NULL, [SYNC_TIME] DATETIME NULL, "+
			"CONSTRAINT PK_%s PRIMARY KEY CLUSTERED (FID, FACCTYEAR, FACCTPERIOD), "+
			"CONSTRAINT CK_%s CHECK (FVAL < 100))", table, table, table)
	if _, err := handle.ExecContext(ctx, createSQL); err != nil {
		t.Fatal(err)
	}
	defer func() {
		_, _ = handle.Exec("IF OBJECT_ID(N'dbo." + table + "', 'U') IS NOT NULL DROP TABLE dbo." + table)
	}()

	cols := []string{"FID", "FACCTYEAR", "FACCTPERIOD", "FVAL", "SYNC_TIME"}
	pkCols := []string{"FID", "FACCTYEAR", "FACCTPERIOD"}
	scopeCols := []string{"FACCTYEAR", "FACCTPERIOD"}

	// 种子数据：2 个"本批会替换"的期间 + 1 个"窗口外"期间
	seed := []map[string]interface{}{
		{"FID": int64(1), "FACCTYEAR": "2026", "FACCTPERIOD": "1", "FVAL": 10},
		{"FID": int64(2), "FACCTYEAR": "2026", "FACCTPERIOD": "1", "FVAL": 11},
		{"FID": int64(3), "FACCTYEAR": "2026", "FACCTPERIOD": "2", "FVAL": 20},
		{"FID": int64(4), "FACCTYEAR": "2025", "FACCTPERIOD": "12", "FVAL": 90},
	}
	if _, err := writer.ReplaceSnapshot(ctx, table, seed, cols, pkCols, nil, nil); err != nil {
		t.Fatalf("种子数据换入失败: %v", err)
	}

	countWhere := func(clause string, args ...interface{}) int {
		t.Helper()
		var n int
		q := "SELECT COUNT(*) FROM dbo.[" + table + "]"
		if clause != "" {
			q += " WHERE " + clause
		}
		if err := handle.QueryRowContext(ctx, q, args...).Scan(&n); err != nil {
			t.Fatalf("count (%s): %v", clause, err)
		}
		return n
	}
	sumVal := func(clause string) int {
		t.Helper()
		var s sql.NullInt64
		q := "SELECT SUM(FVAL) FROM dbo.[" + table + "]"
		if clause != "" {
			q += " WHERE " + clause
		}
		if err := handle.QueryRowContext(ctx, q).Scan(&s); err != nil {
			t.Fatalf("sum (%s): %v", clause, err)
		}
		if !s.Valid {
			return -1
		}
		return int(s.Int64)
	}
	stagingCount := func() int {
		t.Helper()
		// 统计库内全部 stg_* 表：运行本测试前须暂停调度，否则并发同步的 staging 会造成误报
		var n int
		if err := handle.QueryRowContext(ctx, "SELECT COUNT(*) FROM sys.tables WHERE name LIKE 'stg[_]%'").Scan(&n); err != nil {
			t.Fatal(err)
		}
		return n
	}

	// ① + ② 只替换 2026-1 与 2026-2；2025-12 必须原样保留
	batch := []map[string]interface{}{
		{"FID": int64(1), "FACCTYEAR": "2026", "FACCTPERIOD": "1", "FVAL": 15},
		{"FID": int64(10), "FACCTYEAR": "2026", "FACCTPERIOD": "1", "FVAL": 16},
		{"FID": int64(3), "FACCTYEAR": "2026", "FACCTPERIOD": "2", "FVAL": 25},
	}
	res, err := writer.ReplaceSnapshot(ctx, table, batch, cols, pkCols, nil, scopeCols)
	if err != nil {
		t.Fatalf("作用域替换失败: %v", err)
	}
	if res.Total != 3 || res.Inserted != 3 {
		t.Fatalf("作用域替换统计 = %+v, want Total=3 Inserted=3", res)
	}
	if got := countWhere("FACCTYEAR = '2025'"); got != 1 {
		t.Fatalf("窗口外期间行数 = %d, want 1（原因：整表删除会抹掉历史期间，正是 issue #7）", got)
	}
	if got := countWhere("FACCTYEAR = '2026' AND FACCTPERIOD = '1'"); got != 2 {
		t.Fatalf("作用域期间行数 = %d, want 2", got)
	}
	if got := sumVal("FACCTYEAR = '2026' AND FACCTPERIOD = '1'"); got != 31 {
		t.Fatalf("作用域期间 SUM(FVAL) = %d, want 31（旧行 10+11 必须被换入值 15+16 覆盖）", got)
	}
	if got := sumVal("FACCTYEAR = '2025'"); got != 90 {
		t.Fatalf("窗口外期间 SUM(FVAL) = %d, want 90", got)
	}

	// ③ 作用域内失败必须整体回滚：窗口外与窗口内都保持上一轮
	bad := []map[string]interface{}{
		{"FID": int64(1), "FACCTYEAR": "2026", "FACCTPERIOD": "1", "FVAL": 500}, // 违反 CHECK
	}
	if _, err := writer.ReplaceSnapshot(ctx, table, bad, cols, pkCols, nil, scopeCols); err == nil {
		t.Fatal("违反 CHECK 约束的作用域替换应失败")
	}
	if got := countWhere("FACCTYEAR = '2026' AND FACCTPERIOD = '1'"); got != 2 {
		t.Fatalf("失败回滚后作用域行数 = %d, want 2（原因：DELETE…JOIN 已执行就必须回滚，否则本期间被清空）", got)
	}
	if got := sumVal("FACCTYEAR = '2026' AND FACCTPERIOD = '1'"); got != 31 {
		t.Fatalf("失败回滚后作用域 SUM(FVAL) = %d, want 31", got)
	}
	if got := countWhere(""); got != 4 {
		t.Fatalf("失败回滚后总行数 = %d, want 4", got)
	}

	// ④ 作用域值为 NULL 时拒绝执行，且不产生任何副作用（连 staging 都不建）
	nullScope := []map[string]interface{}{
		{"FID": int64(1), "FACCTYEAR": "2026", "FACCTPERIOD": nil, "FVAL": 10},
	}
	if _, err := writer.ReplaceSnapshot(ctx, table, nullScope, cols, pkCols, nil, scopeCols); err == nil {
		t.Fatal("作用域值为 NULL 必须拒绝（否则 DELETE…JOIN 删不到旧行，留下重复数据）")
	}
	if got := countWhere(""); got != 4 {
		t.Fatalf("拒绝执行后总行数 = %d, want 4", got)
	}
	if got := stagingCount(); got != 0 {
		t.Fatalf("拒绝执行后残留 staging 表 = %d, want 0", got)
	}

	// ⑤ scopeCols 为空退化为整表替换
	full := []map[string]interface{}{
		{"FID": int64(99), "FACCTYEAR": "2026", "FACCTPERIOD": "3", "FVAL": 30},
	}
	if _, err := writer.ReplaceSnapshot(ctx, table, full, cols, pkCols, nil, nil); err != nil {
		t.Fatalf("整表替换失败: %v", err)
	}
	if got := countWhere(""); got != 1 {
		t.Fatalf("整表替换后行数 = %d, want 1", got)
	}
	if got := countWhere("FACCTYEAR = '2025'"); got != 0 {
		t.Fatalf("整表替换后仍残留窗口外数据 %d 行", got)
	}

	// ⑥ 多轮之后不残留 staging 表
	if got := stagingCount(); got != 0 {
		t.Fatalf("残留 stg_* 表 = %d, want 0", got)
	}
}

// 单元层面验证 ReplaceSnapshot 的前置防护，不接触数据库。
func TestReplaceSnapshotRejectsUnsafeInput(t *testing.T) {
	writer := &SQLServerWriter{}
	cols := []string{"FID"}
	pkCols := []string{"FID"}
	rows := []map[string]interface{}{{"FID": int64(1)}}

	if _, err := writer.ReplaceSnapshot(context.Background(), "bd_stock", nil, cols, pkCols, nil, nil); err == nil {
		t.Fatal("空快照应被拒绝")
	}
	if _, err := writer.ReplaceSnapshot(context.Background(), "bd_stock; DROP TABLE x", rows, cols, pkCols, nil, nil); err == nil {
		t.Fatal("非法表名应被拒绝")
	}
	if _, err := writer.ReplaceSnapshot(context.Background(), "bd_stock", rows, []string{"FID] NVARCHAR(9); DROP TABLE x"}, pkCols, nil, nil); err == nil {
		t.Fatal("非法列名应被拒绝")
	}
	if _, err := writer.ReplaceSnapshot(context.Background(), "bd_stock", rows, cols, pkCols, nil,
		[]string{"FACCTYEAR"}); err == nil {
		t.Fatal("作用域列不在写列中应被拒绝")
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
