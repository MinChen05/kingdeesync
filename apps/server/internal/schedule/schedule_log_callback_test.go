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

func openScheduleLogTestDB(t *testing.T, tag string) *gorm.DB {
	t.Helper()
	oldDB := gormdb.DB
	db, err := gorm.Open(sqlite.Open(fmt.Sprintf("file:%s-%d?mode=memory&cache=shared", tag, time.Now().UnixNano())), &gorm.Config{})
	if err != nil {
		t.Fatalf("open test sqlite: %v", err)
	}
	// gormdb.AutoMigrate 作用于全局 DB（原因：迁移助手与运行时同接口，测试须先切换指针）
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
	return db
}

// 调度轮执行前必须在引擎上注册实时日志回调
// （原因：回归保护 2026-11-16 日志审计发现的 [LOG-MSG] Skipping: cb is nil——
// 调度轮从未注册回调，实时日志全部丢弃）。
func TestRunJobRegistersLogCallbackOnEngine(t *testing.T) {
	oldDB := gormdb.DB
	oldRunner := scheduledSyncRunner
	oldCompletionHook := scheduleRunCompletionHook
	db, err := gorm.Open(sqlite.Open(fmt.Sprintf("file:scheduler-cb-test-%d?mode=memory&cache=shared", time.Now().UnixNano())), &gorm.Config{})
	if err != nil {
		t.Fatalf("open test sqlite: %v", err)
	}
	gormdb.DB = db
	if err := gormdb.AutoMigrate(); err != nil {
		t.Fatalf("migrate test sqlite: %v", err)
	}
	var callbackRegistered bool
	var runnerRunID string
	scheduledSyncRunner = func(_ context.Context, eng *syncengine.SyncEngine, runID string, _ []string, _ string) (*syncengine.SyncResult, error) {
		callbackRegistered = eng.HasLogCallback()
		runnerRunID = runID
		return &syncengine.SyncResult{RunID: runID, Status: syncengine.StatusSuccess}, nil
	}
	completionDone := make(chan struct{})
	mu.Lock()
	scheduleRunCompletionHook = func(string) { close(completionDone) }
	mu.Unlock()
	t.Cleanup(func() {
		mu.Lock()
		scheduleRunCompletionHook = oldCompletionHook
		mu.Unlock()
		scheduledSyncRunner = oldRunner
		gormdb.DB = oldDB
		if sqlDB, err := db.DB(); err == nil {
			_ = sqlDB.Close()
		}
	})

	job := gormdb.ScheduleJob{Name: "scheduler-cb-test", CronExpr: "0 * * * * *", SyncType: "incremental", Forms: `["missing-form"]`}
	if err := db.Create(&job).Error; err != nil {
		t.Fatalf("create schedule job: %v", err)
	}
	eng := &syncengine.SyncEngine{}
	runJob(&job, eng)

	select {
	case <-completionDone:
	case <-time.After(3 * time.Second):
		t.Fatal("调度任务未在超时内完成")
	}
	if !callbackRegistered {
		t.Fatal("runJob 未在 scheduledSyncRunner 执行前注册日志回调")
	}
	if !eng.HasLogCallback() {
		t.Fatal("调度轮结束后引擎回调应仍处于注册状态（与手动轮一致的覆盖式语义）")
	}
	if runnerRunID == "" {
		t.Fatal("scheduledSyncRunner 未收到 runID")
	}
}

// newScheduleLogCallback 必须把实时日志写入与 API 手动轮一致的 go_sync_errors 表
// （原因：前端 runs/:id/logs 从该表读取，落库失败或字段错位会让调度轮日志视图为空）。
func TestNewScheduleLogCallbackPersistsRunLogs(t *testing.T) {
	db := openScheduleLogTestDB(t, "schedule-logcb-persist")

	cb := newScheduleLogCallback(db)
	cb("run-logs-1", "生产用料清单明细表", "INFO", "已拉取 100 条")
	cb("run-logs-1", "生产用料清单明细表", "WARN", "接近表单预算")
	cb("run-logs-2", "科目余额表", "INFO", "已拉取 10 条")

	var entries []gormdb.SyncError
	if err := db.Where("run_id = ?", "run-logs-1").Order("id ASC").Find(&entries).Error; err != nil {
		t.Fatalf("读取 run 日志失败: %v", err)
	}
	if len(entries) != 2 {
		t.Fatalf("run-logs-1 日志行数 = %d，期望 2", len(entries))
	}
	if entries[0].Level != "INFO" || entries[0].Message != "已拉取 100 条" {
		t.Fatalf("第 1 条日志字段不符：%+v", entries[0])
	}
	if entries[1].Level != "WARN" || entries[1].Message != "接近表单预算" {
		t.Fatalf("第 2 条日志字段不符：%+v", entries[1])
	}

	// 状态库为 nil 时静默忽略、不 panic（原因：日志通道故障绝不能让调度轮崩溃）
	newScheduleLogCallback(nil)("run-x", "表单A", "INFO", "消息")
}
