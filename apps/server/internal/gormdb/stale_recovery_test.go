package gormdb

import (
	"testing"
	"time"
)

func TestRecoverStaleRunningRunsFreshDBNoError(t *testing.T) {
	setupStateTestDB(t)
	_, err := RecoverStaleRunningRuns()
	if err != nil {
		t.Fatalf("startup recovery on fresh state db must not error: %v", err)
	}
}

func TestRecoverStaleRunningRunsRecoversStaleRun(t *testing.T) {
	setupStateTestDB(t)
	if _, err := CreateSyncRun("stale-run", "task", "incremental"); err != nil {
		t.Fatal(err)
	}
	staleTime := time.Now().Add(-4 * time.Hour)
	result := DB.Model(&SyncRun{}).
		Where("run_id = ?", "stale-run").
		Update("start_time", staleTime)
	if result.Error != nil {
		t.Fatalf("backdate start time failed: %v", result.Error)
	}
	staleCount, err := RecoverStaleRunningRuns()
	if err != nil || staleCount != 1 {
		t.Fatalf("expected 1 stale run recovered, got %d: %v", staleCount, err)
	}
}
