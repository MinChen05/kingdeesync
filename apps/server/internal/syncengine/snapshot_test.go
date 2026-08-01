package syncengine

import (
	"context"
	"fmt"
	"strings"
	"testing"
	"time"

	"github.com/kingdee-sync/go/internal/gormdb"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

func setupSnapshotTest(t *testing.T) {
	t.Helper()
	oldDB := gormdb.DB
	db, err := gorm.Open(sqlite.Open(fmt.Sprintf("file:snapshot-test-%d?mode=memory&cache=shared", time.Now().UnixNano())), &gorm.Config{})
	if err != nil {
		t.Fatalf("open test sqlite: %v", err)
	}
	gormdb.DB = db
	if err := gormdb.AutoMigrate(); err != nil {
		t.Fatalf("migrate test sqlite: %v", err)
	}
	t.Cleanup(func() {
		gormdb.DB = oldDB
		if sqlDB, err := db.DB(); err == nil {
			_ = sqlDB.Close()
		}
	})
}

func TestSnapshotCreateAndValidate(t *testing.T) {
	setupSnapshotTest(t)
	mgr := NewSnapshotManager("test-run", "物料", "bd_material", nil)
	if err := mgr.Create(); err != nil {
		t.Fatal(err)
	}

	mgr.UpdateFetched(10)
	mgr.UpdateWritten(10)

	rows := []map[string]interface{}{
		{"FID": "1", "FNAME": "A"},
		{"FID": "2", "FNAME": "B"},
	}
	err := mgr.Validate(rows, []string{"FID"})
	if err != nil {
		t.Fatalf("Validate() error = %v", err)
	}

	var meta gormdb.SnapshotMeta
	gormdb.DB.Where("snapshot_id = ?", mgr.SnapshotID()).First(&meta)
	if meta.Status != string(SnapshotValidated) {
		t.Fatalf("status = %q, want validated", meta.Status)
	}
	if meta.FetchedCount != 10 || meta.WrittenCount != 10 {
		t.Fatalf("counts = fetched=%d written=%d", meta.FetchedCount, meta.WrittenCount)
	}
}

func TestSnapshotRejectsIncompleteWrite(t *testing.T) {
	setupSnapshotTest(t)
	mgr := NewSnapshotManager("test-run", "物料", "bd_material", nil)
	if err := mgr.Create(); err != nil {
		t.Fatal(err)
	}

	mgr.UpdateFetched(10)
	mgr.UpdateWritten(5) // partial write

	rows := []map[string]interface{}{{"FID": "1"}}
	err := mgr.Validate(rows, []string{"FID"})
	if err == nil {
		t.Fatal("expected error for partial write")
	}
	if !strings.Contains(err.Error(), "partial write") {
		t.Fatalf("error = %v, want partial write message", err)
	}

	var meta gormdb.SnapshotMeta
	gormdb.DB.Where("snapshot_id = ?", mgr.SnapshotID()).First(&meta)
	if meta.Status != string(SnapshotAborted) {
		t.Fatalf("status = %q, want aborted", meta.Status)
	}
}

func TestSnapshotRejectsEmptyFetch(t *testing.T) {
	setupSnapshotTest(t)
	mgr := NewSnapshotManager("test-run", "物料", "bd_material", nil)
	if err := mgr.Create(); err != nil {
		t.Fatal(err)
	}

	// Don't call UpdateFetched — stays at 0
	mgr.UpdateWritten(0)

	rows := []map[string]interface{}{{"FID": "1"}}
	err := mgr.Validate(rows, []string{"FID"})
	if err == nil {
		t.Fatal("expected error for empty fetch")
	}
}

func TestSnapshotRejectsMissingPK(t *testing.T) {
	setupSnapshotTest(t)
	mgr := NewSnapshotManager("test-run", "物料", "bd_material", nil)
	if err := mgr.Create(); err != nil {
		t.Fatal(err)
	}

	mgr.UpdateFetched(5)
	mgr.UpdateWritten(5)

	rows := []map[string]interface{}{{"FID": "1"}}
	err := mgr.Validate(rows, []string{})
	if err == nil {
		t.Fatal("expected error for missing PK columns")
	}
}

func TestSnapshotRejectsOrphanDeleteBeforeValidation(t *testing.T) {
	setupSnapshotTest(t)
	writer := &recoveryTestWriter{}
	mgr := NewSnapshotManager("test-run", "物料", "bd_material", writer)
	if err := mgr.Create(); err != nil {
		t.Fatal(err)
	}

	_, err := mgr.DeleteOrphaned(context.Background(), []map[string]interface{}{{"FID": "1"}}, []string{"FID"})
	if err == nil {
		t.Fatal("expected error: cannot delete orphans before validation")
	}
}

func TestSnapshotPkCountTracking(t *testing.T) {
	setupSnapshotTest(t)
	mgr := NewSnapshotManager("test-run", "销售订单", "saleorder", nil)
	if err := mgr.Create(); err != nil {
		t.Fatal(err)
	}

	rows := []map[string]interface{}{
		{"FID": "SO-1", "FENTRYID": "1"},
		{"FID": "SO-1", "FENTRYID": "2"},
		{"FID": "SO-2", "FENTRYID": "1"},
	}
	mgr.UpdatePkCount(rows, []string{"FID", "FENTRYID"})

	var meta gormdb.SnapshotMeta
	gormdb.DB.Where("snapshot_id = ?", mgr.SnapshotID()).First(&meta)
	if meta.PkCount != 3 {
		t.Fatalf("pk_count = %d, want 3", meta.PkCount)
	}
}

func TestSnapshotAbortRecordsReason(t *testing.T) {
	setupSnapshotTest(t)
	mgr := NewSnapshotManager("test-run", "物料", "bd_material", nil)
	if err := mgr.Create(); err != nil {
		t.Fatal(err)
	}

	if err := mgr.Abort("test abort reason"); err == nil {
		t.Fatal("expected abort error")
	}

	var meta gormdb.SnapshotMeta
	gormdb.DB.Where("snapshot_id = ?", mgr.SnapshotID()).First(&meta)
	if meta.Status != string(SnapshotAborted) {
		t.Fatalf("status = %q, want aborted", meta.Status)
	}
	if meta.ErrorReason != "test abort reason" {
		t.Fatalf("error_reason = %q, want 'test abort reason'", meta.ErrorReason)
	}
}

func TestSnapshotPkKeyComposite(t *testing.T) {
	mgr := NewSnapshotManager("run", "form", "table", nil)
	row := map[string]interface{}{"FID": "A", "FENTRYID": "1"}
	key := mgr.pkKey(row, []string{"FID", "FENTRYID"})
	if key != "A|1" {
		t.Fatalf("pkKey = %q, want A|1", key)
	}
}

func TestSnapshotPkKeyNilValue(t *testing.T) {
	mgr := NewSnapshotManager("run", "form", "table", nil)
	row := map[string]interface{}{"FID": nil, "FENTRYID": "1"}
	key := mgr.pkKey(row, []string{"FID", "FENTRYID"})
	if key != "<nil>|1" {
		t.Fatalf("pkKey with nil = %q, want <nil>|1", key)
	}
}

func TestSnapshotPkKeyUppercaseFallback(t *testing.T) {
	mgr := NewSnapshotManager("run", "form", "table", nil)
	row := map[string]interface{}{"FID": "A"}
	key := mgr.pkKey(row, []string{"fid"})
	if key != "A" {
		t.Fatalf("pkKey uppercase fallback = %q, want A", key)
	}
}
