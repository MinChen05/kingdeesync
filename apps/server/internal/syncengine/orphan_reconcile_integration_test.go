package syncengine

import (
	"context"
	"fmt"
	"os"
	"testing"
	"time"

	"github.com/kingdee-sync/go/internal/config"
)

func TestDorisOrphanReconciliationDeletesOnlyTargetOnlyKey(t *testing.T) {
	if os.Getenv("DORIS_INTEGRATION") != "1" {
		t.Skip("set DORIS_INTEGRATION=1 to run against the isolated Doris test table")
	}
	if _, err := config.Load("../../../config.local.ini"); err != nil {
		t.Fatal(err)
	}
	writer := NewDorisWriter()
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	db, _, err := writer.openDorisSQL(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	table := fmt.Sprintf("orphan_it_%d", time.Now().UnixNano())
	_, err = db.ExecContext(ctx, fmt.Sprintf(
		"CREATE TABLE `%s` (`FID` BIGINT NOT NULL, `FDATE` DATETIME NOT NULL, `FVALUE` VARCHAR(20) NULL, `SYNC_TIME` DATETIME NULL) UNIQUE KEY(`FID`,`FDATE`) DISTRIBUTED BY HASH(`FID`) BUCKETS 1 PROPERTIES (\"enable_unique_key_merge_on_write\"=\"true\", \"replication_num\"=\"1\")",
		table,
	))
	if err != nil {
		t.Fatal(err)
	}
	defer func() { _, _ = db.Exec("DROP TABLE IF EXISTS `" + table + "`") }()

	targetRows := make([]map[string]interface{}, 0, 101)
	for id := 1; id <= 101; id++ {
		targetRows = append(targetRows, map[string]interface{}{
			"FID": id, "FDATE": "2025-01-01 00:00:00", "FVALUE": fmt.Sprintf("value-%d", id),
		})
	}
	if written, err := writer.Upsert(ctx, table, targetRows, []string{"FID", "FDATE", "FVALUE"}, []string{"FID", "FDATE"}, nil); err != nil || written != 101 {
		t.Fatalf("seed target: written=%d err=%v", written, err)
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
	if err := db.Get(&count, "SELECT COUNT(*) FROM `"+table+"`"); err != nil {
		t.Fatal(err)
	}
	if err := db.Get(&deletedKey, "SELECT COUNT(*) FROM `"+table+"` WHERE FID = 101"); err != nil {
		t.Fatal(err)
	}
	if count != 100 || deletedKey != 0 {
		t.Fatalf("target after delete count=%d deleted-key-count=%d", count, deletedKey)
	}
}
