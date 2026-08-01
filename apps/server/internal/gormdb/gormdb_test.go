package gormdb

import (
	"fmt"
	"sync"
	"testing"
	"time"

	"github.com/kingdee-sync/go/internal/api/contract"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

func setupStateTestDB(t *testing.T) *gorm.DB {
	t.Helper()
	oldDB := DB
	db, err := gorm.Open(sqlite.Open(fmt.Sprintf("file:gorm-state-test-%d?mode=memory&cache=shared", time.Now().UnixNano())), &gorm.Config{})
	if err != nil {
		t.Fatalf("open sqlite: %v", err)
	}
	DB = db
	if sqlDB, err := db.DB(); err == nil {
		sqlDB.SetMaxOpenConns(1)
		sqlDB.SetMaxIdleConns(1)
	}
	if err := AutoMigrate(); err != nil {
		t.Fatalf("migrate sqlite: %v", err)
	}
	t.Cleanup(func() {
		DB = oldDB
		if sqlDB, err := db.DB(); err == nil {
			_ = sqlDB.Close()
		}
	})
	return db
}

func TestFinishSyncRunAtomicTerminalRace(t *testing.T) {
	setupStateTestDB(t)
	const runID = "atomic-finish"
	if _, err := CreateSyncRun(runID, "test", "incremental"); err != nil {
		t.Fatal(err)
	}

	start := make(chan struct{})
	var wg sync.WaitGroup
	errs := make([]error, 2)
	statuses := []string{string(contract.StatusSuccess), string(contract.StatusFailed)}
	for i := range statuses {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			<-start
			errs[i] = FinishSyncRun(runID, statuses[i], 1, int64(11+i), int64(11+i), 0, 1, 1, 0, "")
		}(i)
	}
	close(start)
	wg.Wait()
	for _, err := range errs {
		if err != nil {
			t.Fatalf("finish race returned error: %v", err)
		}
	}

	run, err := GetSyncRun(runID)
	if err != nil {
		t.Fatal(err)
	}
	if run.Status != string(contract.StatusSuccess) && run.Status != string(contract.StatusFailed) {
		t.Fatalf("final status = %q, want one competing terminal status", run.Status)
	}
	if run.TotalRecords != 11 && run.TotalRecords != 12 {
		t.Fatalf("final total records = %d, want one competing update", run.TotalRecords)
	}
}

func TestUpdateSyncRunStatusUsesConditionalTransition(t *testing.T) {
	setupStateTestDB(t)
	const runID = "atomic-transition"
	if _, err := CreateSyncRun(runID, "test", "incremental"); err != nil {
		t.Fatal(err)
	}

	start := make(chan struct{})
	var wg sync.WaitGroup
	errs := make([]error, 2)
	for i, status := range []string{string(contract.StatusSuccess), string(contract.StatusFailed)} {
		wg.Add(1)
		go func(i int, status string) {
			defer wg.Done()
			<-start
			errs[i] = UpdateSyncRunStatus(runID, status, status)
		}(i, status)
	}
	close(start)
	wg.Wait()

	passed := 0
	for _, err := range errs {
		if err == nil {
			passed++
		}
	}
	if passed != 1 {
		t.Fatalf("successful conditional updates = %d, want 1; errors=%v", passed, errs)
	}
}

func TestTerminalRunCannotBeRecoveredAsAbnormal(t *testing.T) {
	db := setupStateTestDB(t)
	const runID = "terminal-recovery"
	if _, err := CreateSyncRun(runID, "test", "incremental"); err != nil {
		t.Fatal(err)
	}
	if err := FinishSyncRun(runID, string(contract.StatusSuccess), 1, 1, 1, 0, 1, 1, 0, ""); err != nil {
		t.Fatal(err)
	}
	oldHeartbeat := time.Now().Add(-time.Hour)
	if err := db.Model(&SyncRun{}).Where("run_id = ?", runID).Update("last_heartbeat", oldHeartbeat).Error; err != nil {
		t.Fatal(err)
	}
	if recovered, err := RecoverAbnormalRuns(time.Minute); err != nil {
		t.Fatal(err)
	} else if recovered != 0 {
		t.Fatalf("recovered terminal runs = %d, want 0", recovered)
	}
	run, err := GetSyncRun(runID)
	if err != nil {
		t.Fatal(err)
	}
	if run.Status != string(contract.StatusSuccess) {
		t.Fatalf("terminal status = %q, want success", run.Status)
	}
}

func TestFinishSyncRunWithRetryReportsUnavailableStore(t *testing.T) {
	oldDB := DB
	DB = nil
	t.Cleanup(func() { DB = oldDB })
	if err := FinishSyncRunWithRetry("missing-run", "success", 0, 0, 0, 0, 0, 0, 0, ""); err == nil {
		t.Fatal("state persistence failure was silently accepted")
	}
}
