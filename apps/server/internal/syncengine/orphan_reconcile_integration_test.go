package syncengine

import (
	"context"
	"fmt"
	"os"
	"testing"
	"time"

	"github.com/kingdee-sync/go/internal/config"
)

// TestSQLServerOrphanReconciliationDeletesOnlyTargetOnlyKey verifies the
// orphan reconciliation flow against a real SQL Server instance.
// Requires MSSQL_INTEGRATION=1 and a reachable SQL Server per config.local.ini.
// （原因：P0-3 将孤儿删除从 Doris 改写为 SQL Server；集成测试默认跳过避免连生产库）
func TestSQLServerOrphanReconciliationDeletesOnlyTargetOnlyKey(t *testing.T) {
	if os.Getenv("MSSQL_INTEGRATION") != "1" {
		t.Skip("set MSSQL_INTEGRATION=1 to run against a dedicated SQL Server test instance")
	}
	if _, err := config.Load("../../../config.local.ini"); err != nil {
		t.Fatal(err)
	}
	writer := NewSQLServerWriter()
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	db, _, err := writer.openSQL(ctx)
	if err != nil {
		t.Fatal(err)
	}
	table := fmt.Sprintf("orphan_it_%d", time.Now().UnixNano())
	if _, err := db.ExecContext(ctx, fmt.Sprintf(
		"CREATE TABLE dbo.%s ([FID] BIGINT NOT NULL, [FDATE] DATETIME NOT NULL, [FVALUE] VARCHAR(50) NULL, [SYNC_TIME] DATETIME NULL)",
		table,
	)); err != nil {
		t.Fatal(err)
	}
	defer func() { _, _ = db.Exec("IF OBJECT_ID(N'dbo." + table + "', 'U') IS NOT NULL DROP TABLE dbo." + table) }()

	targetRows := make([]map[string]interface{}, 0, 101)
	for id := 1; id <= 101; id++ {
		targetRows = append(targetRows, map[string]interface{}{
			"FID": id, "FDATE": "2025-01-01 00:00:00", "FVALUE": fmt.Sprintf("value-%d", id),
		})
	}
if written, err := writer.Upsert(ctx, table, targetRows, []string{"FID", "FDATE", "FVALUE"}, []string{"FID", "FDATE"}, nil); err != nil || written.Total != 101 {
			t.Fatalf("seed target: written=%d err=%v", written.Total, err)
	}
	sourceRows := targetRows[:100]
	result, err := writer.ReconcileOrphans(ctx, OrphanReconcileInput{
		SnapshotID: "integration-snapshot", TargetTable: table, SourceRows: sourceRows,
		StorageKeyColumns: []string{"FID", "FDATE"}, PreviousSourceCount: 100, ExecuteDelete: true,
	})
	if err != nil {
		t.Fatal(err)
	}
	if result.OrphanCount != 1 || result.DeletedCount != 1 || result.Decision != OrphanDeleteAutoApproved {
		t.Fatalf("reconcile result = %+v", result)
	}
	var count, deletedKey int
	if err := db.Get(&count, "SELECT COUNT(*) FROM dbo."+table); err != nil {
		t.Fatal(err)
	}
	if err := db.Get(&deletedKey, "SELECT COUNT(*) FROM dbo."+table+" WHERE FID = 101"); err != nil {
		t.Fatal(err)
	}
	if count != 100 || deletedKey != 0 {
		t.Fatalf("target after delete count=%d deleted-key-count=%d", count, deletedKey)
	}
}
