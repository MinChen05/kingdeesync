package gormdb

import (
	"testing"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

func TestOrphanDeleteApprovalIsBoundAndSingleUse(t *testing.T) {
	var err error
	DB, err = gorm.Open(sqlite.Open("file:orphan-approval?mode=memory&cache=shared"), &gorm.Config{})
	if err != nil {
		t.Fatal(err)
	}
	if err := DB.AutoMigrate(&OrphanDeleteApproval{}); err != nil {
		t.Fatal(err)
	}
	approval := &OrphanDeleteApproval{
		SnapshotID: "snap-1", TargetTable: "orders__next_abcdef01",
		SnapshotHash:        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
		ExpectedOrphanCount: 1200, Approver: "local-admin", Reason: "reviewed source deletion",
	}
	if err := CreateOrphanDeleteApproval(approval); err != nil {
		t.Fatal(err)
	}
	if err := ConsumeOrphanDeleteApproval("snap-1", "orders__next_abcdef01", approval.SnapshotHash, 1200); err != nil {
		t.Fatal(err)
	}
	if err := ConsumeOrphanDeleteApproval("snap-1", "orders__next_abcdef01", approval.SnapshotHash, 1200); err == nil {
		t.Fatal("expected reused approval to be rejected")
	}
}
