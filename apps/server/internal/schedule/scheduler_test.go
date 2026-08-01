package schedule

import (
	"context"
	"fmt"
	"testing"
	"time"

	"github.com/kingdee-sync/go/internal/gormdb"
	"github.com/kingdee-sync/go/internal/syncengine"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

func TestRunJobReusesPrecreatedSyncRun(t *testing.T) {
	oldDB := gormdb.DB
	oldRunner := scheduledSyncRunner
	oldTimeout := schedulerRunTimeout
	oldCompletionHook := scheduleRunCompletionHook
	db, err := gorm.Open(sqlite.Open(fmt.Sprintf("file:scheduler-test-%d?mode=memory&cache=shared", time.Now().UnixNano())), &gorm.Config{})
	if err != nil {
		t.Fatalf("open test sqlite: %v", err)
	}
	gormdb.DB = db
	if err := gormdb.AutoMigrate(); err != nil {
		t.Fatalf("migrate test sqlite: %v", err)
	}
	t.Cleanup(func() {
		mu.Lock()
		scheduleRunCompletionHook = oldCompletionHook
		mu.Unlock()
		scheduledSyncRunner = oldRunner
		schedulerRunTimeout = oldTimeout
		gormdb.DB = oldDB
		if sqlDB, err := db.DB(); err == nil {
			_ = sqlDB.Close()
		}
	})

	job := gormdb.ScheduleJob{
		Name:     "scheduler-run-id-test",
		CronExpr: "0 * * * * *",
		SyncType: "incremental",
		Forms:    `["missing-form"]`,
	}
	if err := db.Create(&job).Error; err != nil {
		t.Fatalf("create schedule job: %v", err)
	}

	runJob(&job, &syncengine.SyncEngine{})

	var scheduleRun gormdb.ScheduleRun
	var syncRuns []gormdb.SyncRun
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if err := db.Where("job_id = ?", job.ID).First(&scheduleRun).Error; err == nil && scheduleRun.EndTime != nil {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	if scheduleRun.EndTime == nil {
		t.Fatal("scheduled run did not finish")
	}
	if err := db.Where("task_name = ?", job.Name).Find(&syncRuns).Error; err != nil {
		t.Fatalf("load sync runs: %v", err)
	}
	if len(syncRuns) != 1 {
		t.Fatalf("sync run count = %d, want 1", len(syncRuns))
	}
	if syncRuns[0].RunID != scheduleRun.RunID {
		t.Fatalf("sync run id = %q, schedule run id = %q", syncRuns[0].RunID, scheduleRun.RunID)
	}
	if syncRuns[0].Status != string(syncengine.StatusFailed) {
		t.Fatalf("sync run status = %q, want failed", syncRuns[0].Status)
	}
}

func TestRunJobTimeoutFinishesScheduleAndSyncRun(t *testing.T) {
	oldDB := gormdb.DB
	oldRunner := scheduledSyncRunner
	oldTimeout := schedulerRunTimeout
	oldCompletionHook := scheduleRunCompletionHook
	db, err := gorm.Open(sqlite.Open(fmt.Sprintf("file:scheduler-timeout-test-%d?mode=memory&cache=shared", time.Now().UnixNano())), &gorm.Config{})
	if err != nil {
		t.Fatalf("open sqlite: %v", err)
	}
	gormdb.DB = db
	if err := gormdb.AutoMigrate(); err != nil {
		t.Fatalf("migrate sqlite: %v", err)
	}
	schedulerRunTimeout = 10 * time.Millisecond
	runnerDone := make(chan struct{})
	completionDone := make(chan struct{})
	mu.Lock()
	scheduleRunCompletionHook = func(string) { close(completionDone) }
	mu.Unlock()
	scheduledSyncRunner = func(ctx context.Context, _ *syncengine.SyncEngine, _ string, _ []string, _ string) (*syncengine.SyncResult, error) {
		<-ctx.Done()
		close(runnerDone)
		return nil, ctx.Err()
	}
	t.Cleanup(func() {
		mu.Lock()
		scheduleRunCompletionHook = oldCompletionHook
		mu.Unlock()
		scheduledSyncRunner = oldRunner
		schedulerRunTimeout = oldTimeout
		gormdb.DB = oldDB
		if sqlDB, err := db.DB(); err == nil {
			_ = sqlDB.Close()
		}
	})

	job := gormdb.ScheduleJob{Name: "scheduler-timeout-test", CronExpr: "0 * * * * *", SyncType: "incremental", Forms: `["missing-form"]`}
	if err := db.Create(&job).Error; err != nil {
		t.Fatalf("create schedule job: %v", err)
	}
	runJob(&job, &syncengine.SyncEngine{})

	var scheduleRun gormdb.ScheduleRun
	var syncRun gormdb.SyncRun
	deadline := time.Now().Add(time.Second)
	for time.Now().Before(deadline) {
		_ = db.Where("job_id = ?", job.ID).First(&scheduleRun).Error
		if scheduleRun.RunID != "" {
			_ = db.Where("run_id = ?", scheduleRun.RunID).First(&syncRun).Error
		}
		if scheduleRun.EndTime != nil && syncRun.Status == string(syncengine.StatusFailedAbnormalExit) {
			break
		}
		time.Sleep(time.Millisecond)
	}
	if scheduleRun.EndTime == nil || scheduleRun.Status != string(syncengine.StatusFailedAbnormalExit) {
		t.Fatalf("schedule timeout state = status=%q end=%v, want abnormal terminal", scheduleRun.Status, scheduleRun.EndTime)
	}
	if syncRun.Status != string(syncengine.StatusFailedAbnormalExit) {
		t.Fatalf("sync timeout status = %q, want failed_abnormal_exit", syncRun.Status)
	}
	<-runnerDone
	<-completionDone
}

func TestLateRunnerCannotOverwriteWatchdogSummaryWithSuccess(t *testing.T) {
	oldDB := gormdb.DB
	oldRunner := scheduledSyncRunner
	oldTimeout := schedulerRunTimeout
	oldCompletionHook := scheduleRunCompletionHook
	db, err := gorm.Open(sqlite.Open(fmt.Sprintf("file:scheduler-late-runner-test-%d?mode=memory&cache=shared", time.Now().UnixNano())), &gorm.Config{})
	if err != nil {
		t.Fatalf("open sqlite: %v", err)
	}
	gormdb.DB = db
	if err := gormdb.AutoMigrate(); err != nil {
		t.Fatal(err)
	}
	schedulerRunTimeout = 10 * time.Millisecond
	runnerStarted := make(chan struct{})
	releaseRunner := make(chan struct{})
	completionDone := make(chan struct{})
	scheduledSyncRunner = func(context.Context, *syncengine.SyncEngine, string, []string, string) (*syncengine.SyncResult, error) {
		close(runnerStarted)
		<-releaseRunner
		return &syncengine.SyncResult{Status: syncengine.StatusSuccess, Message: "late success"}, nil
	}
	mu.Lock()
	scheduleRunCompletionHook = func(string) { close(completionDone) }
	mu.Unlock()
	t.Cleanup(func() {
		mu.Lock()
		scheduleRunCompletionHook = oldCompletionHook
		mu.Unlock()
		scheduledSyncRunner = oldRunner
		schedulerRunTimeout = oldTimeout
		gormdb.DB = oldDB
		if sqlDB, err := db.DB(); err == nil {
			_ = sqlDB.Close()
		}
	})

	job := gormdb.ScheduleJob{Name: "scheduler-late-runner-test", CronExpr: "0 * * * * *", SyncType: "incremental", Forms: `["missing-form"]`}
	if err := db.Create(&job).Error; err != nil {
		t.Fatalf("create schedule job: %v", err)
	}
	runJob(&job, &syncengine.SyncEngine{})
	<-runnerStarted

	var scheduleRun gormdb.ScheduleRun
	deadline := time.Now().Add(time.Second)
	for time.Now().Before(deadline) {
		if err := db.Where("job_id = ?", job.ID).First(&scheduleRun).Error; err == nil && scheduleRun.Status == string(syncengine.StatusFailedAbnormalExit) {
			break
		}
		time.Sleep(time.Millisecond)
	}
	if scheduleRun.Status != string(syncengine.StatusFailedAbnormalExit) {
		t.Fatalf("watchdog status = %q, want failed_abnormal_exit", scheduleRun.Status)
	}
	close(releaseRunner)
	<-completionDone

	var persistedJob gormdb.ScheduleJob
	if err := db.First(&persistedJob, job.ID).Error; err != nil {
		t.Fatal(err)
	}
	if persistedJob.LastRunID != scheduleRun.RunID {
		t.Fatalf("job last run id = %q, want %q", persistedJob.LastRunID, scheduleRun.RunID)
	}
	if persistedJob.LastStatus != string(syncengine.StatusFailedAbnormalExit) {
		t.Fatalf("job last status = %q, want watchdog status %q", persistedJob.LastStatus, scheduleRun.Status)
	}
}
