package syncengine

import (
	"context"
	"database/sql"
	"database/sql/driver"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"reflect"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/jmoiron/sqlx"
	"github.com/kingdee-sync/go/internal/config"
	"github.com/kingdee-sync/go/internal/db"
	"github.com/kingdee-sync/go/internal/gormdb"
	"github.com/kingdee-sync/go/internal/kind"
)

func TestAccountBalanceEndPeriodMatchesPythonSyncRule(t *testing.T) {
	if year, period := accountBalanceEndPeriod(time.Date(2026, time.July, 30, 0, 0, 0, 0, time.Local)); year != 2026 || period != 6 {
		t.Fatalf("July end period = %d-%d, want 2026-6", year, period)
	}
	if year, period := accountBalanceEndPeriod(time.Date(2026, time.January, 1, 0, 0, 0, 0, time.Local)); year != 2025 || period != 12 {
		t.Fatalf("January end period = %d-%d, want 2025-12", year, period)
	}
}

func TestAccountBalanceStartPeriodSixMonthWindow(t *testing.T) {
	// 2026-07-30: end period 2026-6, six-month window starts 2026-1
	if year, period := accountBalanceStartPeriod(time.Date(2026, time.July, 30, 0, 0, 0, 0, time.Local), 6); year != 2026 || period != 1 {
		t.Fatalf("July window start = %d-%d, want 2026-1", year, period)
	}
	// 2026-03-15: end period 2026-2, six-month window starts 2025-9
	if year, period := accountBalanceStartPeriod(time.Date(2026, time.March, 15, 0, 0, 0, 0, time.Local), 6); year != 2025 || period != 9 {
		t.Fatalf("March window start = %d-%d, want 2025-9", year, period)
	}
	// 2026-01-10: end period 2025-12, six-month window starts 2025-7
	if year, period := accountBalanceStartPeriod(time.Date(2026, time.January, 10, 0, 0, 0, 0, time.Local), 6); year != 2025 || period != 7 {
		t.Fatalf("January window start = %d-%d, want 2025-7", year, period)
	}
	// 跨年边界：2026-02-01 → end 2026-1 → window 2025-8
	if year, period := accountBalanceStartPeriod(time.Date(2026, time.February, 1, 0, 0, 0, 0, time.Local), 6); year != 2025 || period != 8 {
		t.Fatalf("February window start = %d-%d, want 2025-8", year, period)
	}
}

func TestStandardCursorKeysCoverAllStandardForms(t *testing.T) {
	for _, form := range []string{"发货通知单", "生产入库单", "销售订单", "销售出库单", "销售退货单", "预测订单", "生产订单主表", "生产订单明细", "客户资料", "生产用料清单主表", "生产用料清单明细表", "物料", "仓库", "物料清单", "物料清单子项", "采购订单", "采购入库单", "委外订单", "应付单", "应收单"} {
		if got := cursorKeysForForm(form); len(got) == 0 {
			t.Fatalf("%s has no cursor key", form)
		}
	}
	if got := cursorKeysForForm("科目余额表"); len(got) != 0 {
		t.Fatalf("snapshot form cursor keys = %#v, want none", got)
	}
}

func TestBuildCursorFilterUsesLexicographicCompositeKey(t *testing.T) {
	filter, err := BuildCursorFilter("FOrgId = 1", []string{"FID", "FENTRYID"}, []interface{}{float64(10), "20"})
	if err != nil {
		t.Fatal(err)
	}
	want := "(FOrgId = 1) AND (FID > 10 OR (FID = 10 AND FENTRYID > '20'))"
	if filter != want {
		t.Fatalf("filter = %q, want %q", filter, want)
	}
}

func TestValidateCursorKeyFieldsRejectsMissingKey(t *testing.T) {
	if err := ValidateCursorKeyFields([]string{"FID"}, []string{"FID", "FENTRYID"}); err == nil {
		t.Fatal("expected missing cursor key error")
	}
}

func TestValidateCursorPageRejectsDuplicateCompositeKey(t *testing.T) {
	_, err := ValidateCursorPage([]map[string]interface{}{
		{"FID": float64(1), "FENTRYID": float64(1)},
		{"FID": float64(1), "FENTRYID": float64(1)},
	}, []string{"FID", "FENTRYID"}, nil)
	if err == nil {
		t.Fatal("expected duplicate cursor key rejection")
	}
}

func TestValidateCursorPageSkipsEmptyCursorKeyRows(t *testing.T) {
	// Simulate Kingdee returning a header-only row (no entry lines) where
	// the entry cursor key is null/empty. These rows should be skipped.
	last, err := ValidateCursorPage([]map[string]interface{}{
		{"FID": float64(1), "FENTRYID": nil},          // header-only, should skip
		{"FID": float64(2), "FENTRYID": float64(100)}, // valid row
		{"FID": float64(3), "FENTRYID": ""},           // header-only, should skip
		{"FID": float64(4), "FENTRYID": float64(200)}, // valid row
	}, []string{"FID", "FENTRYID"}, nil)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if last == nil || len(last) != 2 {
		t.Fatalf("expected last cursor values, got %v", last)
	}
	if v, ok := last[1].(float64); !ok || v != 200 {
		t.Fatalf("last FENTRYID = %v, want 200", last[1])
	}
}

func TestValidateCursorPageMarksAllEmptyCursorKeys(t *testing.T) {
	_, err := ValidateCursorPage([]map[string]interface{}{
		{"FID": float64(5), "FENTRYID": nil},
	}, []string{"FID", "FENTRYID"}, []interface{}{float64(4), float64(100)})
	if !errors.Is(err, errCursorPageWithoutKeys) {
		t.Fatalf("err = %v, want errCursorPageWithoutKeys", err)
	}
}

func TestIsTerminalEmptyCursorPage(t *testing.T) {
	tests := []struct {
		name     string
		rowCount int
		pageSize int
		want     bool
	}{
		{"short tail page", 1, 10000, true},
		{"full page", 10000, 10000, false},
		{"empty page", 0, 10000, false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := isTerminalEmptyCursorPage(tt.rowCount, tt.pageSize); got != tt.want {
				t.Fatalf("isTerminalEmptyCursorPage(%d, %d) = %v, want %v", tt.rowCount, tt.pageSize, got, tt.want)
			}
		})
	}
}

func TestGetFormPriority(t *testing.T) {
	tests := map[string]int{
		"物料":     0,
		"销售订单":   1,
		"生产订单主表": 2,
		"未配置表单":  1,
	}
	for form, want := range tests {
		if got := GetFormPriority(form); got != want {
			t.Errorf("GetFormPriority(%q) = %d, want %d", form, got, want)
		}
	}
}

func TestProductionConfigPrimaryKeyMappingContract(t *testing.T) {
	if got := config.FormToTableName("销售订单"); got != "saleorder" {
		t.Fatalf("FormToTableName(销售订单) = %q, want saleorder", got)
	}
	pk := db.GetPrimaryKey(" saleorder ")
	if pk != "FID,FENTRYID" {
		t.Fatalf("GetPrimaryKey(saleorder) = %q, want composite key", pk)
	}
}

func TestNewSyncEngineUsesSQLServerWriter(t *testing.T) {
	if runIsolatedSQLConfigTest(t, "sqlserver") {
		return
	}

	engine := NewSyncEngine()
	writer, ok := engine.writer.(*SQLServerWriter)
	if !ok {
		t.Fatalf("writer = %T, want *SQLServerWriter for DATABASE.type=sqlserver", engine.writer)
	}
	host, user, password, err := writer.getSQLTarget()
	if err != nil {
		t.Fatalf("getSQLTarget() error = %v", err)
	}
	if host != "doris.test" || user != "test-user" || password != "test-password" {
		t.Fatalf("sqlserver target = (%q, %q, %q), want configured offline target", host, user, password)
	}
}

func TestSQLTargetErrorDoesNotExposeConfiguredCredentials(t *testing.T) {
	if runIsolatedSQLConfigTest(t, "unsupported") {
		return
	}

	_, _, _, err := (&SQLServerWriter{}).getSQLTarget()
	if err == nil {
		t.Fatal("getSQLTarget() error = nil, want unsupported database type error")
	}
	message := err.Error()
	for _, secret := range []string{"secret-user", "super-secret-password", "doris.internal"} {
		if strings.Contains(message, secret) {
			t.Fatalf("getSQLTarget() error %q exposes configured value %q", message, secret)
		}
	}
}

func TestWriteRowsPassesCompositePrimaryKeyToWriter(t *testing.T) {
	oldDB := db.DB
	db.DB = newColumnTestDB(t)
	t.Cleanup(func() {
		db.DB = oldDB
	})

	writer := &capturingWriter{}
	engine := &SyncEngine{writer: writer}
	rows := []map[string]interface{}{{"FID": "SO-1", "FENTRYID": "10", "FBILLNO": "SO-001"}}
	fieldKeys := []string{"FID", "FENTRYID", "FBILLNO"}
	written, err := engine.writeRows("saleorder", rows, fieldKeys, nil)
	if err != nil {
		t.Fatalf("writeRows() error = %v", err)
	}
	if written.Total != 1 || writer.tableName != "saleorder" {
		t.Fatalf("writeRows() = (%d, table %q), want one saleorder row", written.Total, writer.tableName)
	}
	if !reflect.DeepEqual(writer.pkCols, []string{"FID", "FENTRYID"}) {
		t.Fatalf("writer PK columns = %#v, want ordered composite key", writer.pkCols)
	}
	if !reflect.DeepEqual(writer.cols, fieldKeys) || !reflect.DeepEqual(writer.rows, rows) {
		t.Fatalf("writer rows/columns = %#v / %#v, want %#v / %#v", writer.rows, writer.cols, rows, fieldKeys)
	}
}

// 目标表存在 SYNC_TIME 列时必须追加进写列白名单（原因：SYNC_TIME 非金蝶字段，
// 不加则被 staging/MERGE 过滤，增量窗口下界失效）；不存在或已包含时不改动。
func TestAppendSyncTimeCol(t *testing.T) {
	cases := []struct {
		name         string
		cols         []string
		existingCols map[string]string
		want         []string
	}{
		{
			name:         "目标表有 SYNC_TIME 列时追加",
			cols:         []string{"FID", "FBILLNO"},
			existingCols: map[string]string{"FID": "FID", "FBILLNO": "FBILLNO", "SYNC_TIME": "SYNC_TIME"},
			want:         []string{"FID", "FBILLNO", "SYNC_TIME"},
		},
		{
			name:         "目标表无 SYNC_TIME 列时不追加",
			cols:         []string{"FID"},
			existingCols: map[string]string{"FID": "FID"},
			want:         []string{"FID"},
		},
		{
			name:         "金蝶字段已映射出 SYNC_TIME 时不重复追加",
			cols:         []string{"FID", "sync_time"},
			existingCols: map[string]string{"SYNC_TIME": "SYNC_TIME"},
			want:         []string{"FID", "sync_time"},
		},
	}
	for _, c := range cases {
		got := appendSyncTimeCol(c.cols, c.existingCols)
		if !reflect.DeepEqual(got, c.want) {
			t.Fatalf("%s: appendSyncTimeCol() = %#v, want %#v", c.name, got, c.want)
		}
	}
}

func TestInjectSyncTime(t *testing.T) {
	// 写列不含 SYNC_TIME 时不得注入
	rows := []map[string]interface{}{{"FID": 1}}
	injectSyncTime(rows, []string{"FID"})
	if _, ok := rows[0]["SYNC_TIME"]; ok {
		t.Fatal("cols 无 SYNC_TIME 却注入了该键")
	}

	// 含 SYNC_TIME（大小写不敏感）时为每行注入东八区时间戳并覆盖旧值
	rows = []map[string]interface{}{{"FID": 1}, {"FID": 2, "SYNC_TIME": "2020-01-01 00:00:00"}}
	injectSyncTime(rows, []string{"FID", "sync_time"})
	for _, row := range rows {
		v, ok := row["SYNC_TIME"].(string)
		if !ok {
			t.Fatalf("SYNC_TIME 未注入: %#v", row)
		}
		if _, err := time.Parse("2006-01-02 15:04:05", v); err != nil {
			t.Fatalf("SYNC_TIME 格式非法: %q", v)
		}
	}
	if rows[1]["SYNC_TIME"] == "2020-01-01 00:00:00" {
		t.Fatal("旧 SYNC_TIME 未被刷新，MERGE 的 ISNULL 语义下将导致增量窗口停滞")
	}
}

func TestSyncDataProcessesPriorityGroupsInOrder(t *testing.T) {
	setupRecoveryTest(t)
	const runID = "priority-groups"
	if _, err := gormdb.CreateSyncRun(runID, "test", "full"); err != nil {
		t.Fatal(err)
	}

	forms := []string{"生产订单主表", "销售订单", "物料"}
	var starts []string
	engine := &SyncEngine{
		formQuery: func(formName string) (config.FormQuery, bool) {
			return config.FormQuery{FormID: formName, FieldKeys: "FID"}, true
		},
		fetchRows: func(_ context.Context, formName string, _ int) (*kind.QueryResult, error) {
			starts = append(starts, formName)
			return &kind.QueryResult{Rows: []map[string]interface{}{{"FID": formName}}}, nil
		},
		writeRowsFunc: func(_ context.Context, _ string, rows []map[string]interface{}, _ []string, _ map[string]string) (UpsertResult, error) {
			return UpsertResult{Inserted: len(rows), Total: len(rows)}, nil
		},
	}
	if err := engine.PrepareRun(runID, true); err != nil {
		t.Fatal(err)
	}
	result, err := engine.SyncDataWithRunID(context.Background(), runID, forms, "full", true)
	if err != nil {
		t.Fatalf("SyncDataWithRunID() error = %v", err)
	}
	if result.Status != StatusSuccess {
		t.Fatalf("sync status = %q, want success", result.Status)
	}
	wantStarts := []string{"物料", "销售订单", "生产订单主表"}
	if !reflect.DeepEqual(starts, wantStarts) {
		t.Fatalf("form start order = %#v, want priority groups %#v", starts, wantStarts)
	}
}

func runIsolatedSQLConfigTest(t *testing.T, mode string) bool {
	t.Helper()
	childMode := os.Getenv("SYNCENGINE_DORIS_CONFIG_TEST")
	if childMode == "" {
		cmd := exec.Command(os.Args[0], "-test.run", "^"+t.Name()+"$")
		cmd.Env = append(os.Environ(), "SYNCENGINE_DORIS_CONFIG_TEST="+mode)
		if output, err := cmd.CombinedOutput(); err != nil {
			t.Fatalf("isolated config test failed: %v\n%s", err, output)
		}
		return true
	}

	content := "[DATABASE]\ntype = unsupported\nhost = doris.internal\nuser = secret-user\npassword = super-secret-password\n"
	if childMode == "sqlserver" {
		content = "[DATABASE]\ntype = sqlserver\n\n[SQLSERVER]\nhost = doris.test\nport = 1433\nuser = test-user\npassword = test-password\ndatabase = sync_db\n"
	}
	path := filepath.Join(t.TempDir(), "config.ini")
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := config.Load(path); err != nil {
		t.Fatalf("load isolated config: %v", err)
	}
	return false
}

type capturingWriter struct {
	tableName string
	rows      []map[string]interface{}
	cols      []string
	pkCols    []string
}

func (w *capturingWriter) Upsert(_ context.Context, tableName string, rows []map[string]interface{}, cols []string, pkCols []string, _ map[string]string) (UpsertResult, error) {
	w.tableName = tableName
	w.rows = rows
	w.cols = cols
	w.pkCols = pkCols
	return UpsertResult{Inserted: len(rows), Total: len(rows)}, nil
}

func (w *capturingWriter) DeleteOrphaned(context.Context, string, []map[string]interface{}, []string) (int, error) {
	return 0, nil
}

func (w *capturingWriter) Close() error { return nil }

var columnDriverRegistration sync.Once

func newColumnTestDB(t *testing.T) *sqlx.DB {
	t.Helper()
	columnDriverRegistration.Do(func() {
		sql.Register("syncengine-test-columns", columnTestDriver{})
	})
	sqlDB, err := sql.Open("syncengine-test-columns", "")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = sqlDB.Close() })
	return sqlx.NewDb(sqlDB, "syncengine-test-columns")
}

type columnTestDriver struct{}

func (columnTestDriver) Open(string) (driver.Conn, error) { return columnTestConn{}, nil }

type columnTestConn struct{}

func (columnTestConn) Prepare(string) (driver.Stmt, error) { return nil, driver.ErrSkip }
func (columnTestConn) Close() error                        { return nil }
func (columnTestConn) Begin() (driver.Tx, error)           { return nil, driver.ErrSkip }

func (columnTestConn) QueryContext(_ context.Context, query string, args []driver.NamedValue) (driver.Rows, error) {
	// 表名通过 @p1 命名参数绑定，mock 校验参数值而非 SQL 文本拼接
	if !strings.Contains(query, "INFORMATION_SCHEMA.COLUMNS") || len(args) != 1 {
		return nil, fmt.Errorf("unexpected table metadata query: %s args=%v", query, args)
	}
	if args[0].Value != "saleorder" {
		return nil, fmt.Errorf("unexpected table metadata query: %s args=%v", query, args)
	}
	return &columnTestRows{values: []string{"FID", "FENTRYID", "FBILLNO"}}, nil
}

type columnTestRows struct {
	values []string
	index  int
}

func (r *columnTestRows) Columns() []string { return []string{"COLUMN_NAME"} }
func (r *columnTestRows) Close() error      { return nil }
func (r *columnTestRows) Next(dest []driver.Value) error {
	if r.index == len(r.values) {
		return io.EOF
	}
	dest[0] = r.values[r.index]
	r.index++
	return nil
}

func TestSyncEngineStartsIdle(t *testing.T) {
	engine := &SyncEngine{}
	status, message, progress, form, elapsed, stats := engine.GetStatus()
	if status != StatusIdle || message != "" || progress != 0 || form != "" || elapsed != 0 || stats != nil {
		t.Fatalf("initial status = %q, %q, %d, %q, %v, %v", status, message, progress, form, elapsed, stats)
	}
}
