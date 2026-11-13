package v1

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/kingdee-sync/go/internal/gormdb"
	"github.com/kingdee-sync/go/internal/syncengine"
	"github.com/stretchr/testify/require"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

func setupRunTest(t *testing.T) (*gin.Engine, *gorm.DB) {
	t.Helper()
	oldDB := gormdb.DB

	db, err := gorm.Open(sqlite.Open(fmt.Sprintf("file:v1-runs-test-%d?mode=memory&cache=shared", time.Now().UnixNano())), &gorm.Config{})
	require.NoError(t, err)
	gormdb.DB = db

	t.Cleanup(func() {
		gormdb.DB = oldDB
	})

	require.NoError(t, db.AutoMigrate(&gormdb.SyncRun{}, &gormdb.SyncRunForm{}, &gormdb.SyncError{}))

	r := gin.New()
	InitRunsRoutes(r, nil)
	return r, db
}

func performRequest(r *gin.Engine, method, path, body string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(method, path, strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()
	r.ServeHTTP(rec, req)
	return rec
}

func TestListRunsWithoutDB(t *testing.T) {
	oldDB := gormdb.DB
	gormdb.DB = nil
	t.Cleanup(func() { gormdb.DB = oldDB })

	r := gin.New()
	InitRunsRoutes(r, nil)
	rec := performRequest(r, http.MethodGet, "/api/v1/runs", "")
	require.Equal(t, http.StatusOK, rec.Code)

	var result map[string]any
	require.NoError(t, json.Unmarshal(rec.Body.Bytes(), &result))
	require.NotNil(t, result["data"])
	require.NotNil(t, result["meta"])
}

func TestListRunsWithFilters(t *testing.T) {
	r, db := setupRunTest(t)

	// Insert test runs
	now := time.Now()
	end1 := now.Add(5 * time.Minute)
	db.Create(&gormdb.SyncRun{RunID: "run-1", Status: "success", SyncType: "full", StartTime: now, EndTime: &end1, TotalRecords: 100})
	db.Create(&gormdb.SyncRun{RunID: "run-2", Status: "failed", SyncType: "incremental", StartTime: now})
	db.Create(&gormdb.SyncRun{RunID: "run-3", Status: "success", SyncType: "incremental", StartTime: now})

	// Filter by status
	rec := performRequest(r, http.MethodGet, "/api/v1/runs?status=failed", "")
	require.Equal(t, http.StatusOK, rec.Code)

	var result map[string]any
	require.NoError(t, json.Unmarshal(rec.Body.Bytes(), &result))
	data := result["data"].([]any)
	require.Len(t, data, 1)

	// Filter by sync_type
	rec = performRequest(r, http.MethodGet, "/api/v1/runs?sync_type=full", "")
	require.Equal(t, http.StatusOK, rec.Code)
	require.NoError(t, json.Unmarshal(rec.Body.Bytes(), &result))
	data = result["data"].([]any)
	require.Len(t, data, 1)

	// No filter returns all
	rec = performRequest(r, http.MethodGet, "/api/v1/runs", "")
	require.Equal(t, http.StatusOK, rec.Code)
	require.NoError(t, json.Unmarshal(rec.Body.Bytes(), &result))
	data = result["data"].([]any)
	require.Len(t, data, 3)
	meta := result["meta"].(map[string]any)
	require.Equal(t, float64(3), meta["total"])
}

func TestGetRun(t *testing.T) {
	r, db := setupRunTest(t)
	now := time.Now()
	db.Create(&gormdb.SyncRun{RunID: "run-001", Status: "success", SyncType: "full", StartTime: now, TotalRecords: 50})

	rec := performRequest(r, http.MethodGet, "/api/v1/runs/run-001", "")
	require.Equal(t, http.StatusOK, rec.Code)

	var result map[string]any
	require.NoError(t, json.Unmarshal(rec.Body.Bytes(), &result))
	data := result["data"].(map[string]any)
	require.Equal(t, "run-001", data["run_id"])
	require.Equal(t, "success", data["status"])
}

func TestGetRunNotFound(t *testing.T) {
	r, _ := setupRunTest(t)

	rec := performRequest(r, http.MethodGet, "/api/v1/runs/nonexistent", "")
	require.Equal(t, http.StatusNotFound, rec.Code)

	var result map[string]any
	require.NoError(t, json.Unmarshal(rec.Body.Bytes(), &result))
	err := result["error"].(map[string]any)
	require.Equal(t, "RUN_NOT_FOUND", err["code"])
}

func TestListRunEvents(t *testing.T) {
	r, db := setupRunTest(t)
	now := time.Now()
	db.Create(&gormdb.SyncRun{RunID: "run-001", Status: "success", StartTime: now})
	db.Create(&gormdb.SyncError{RunID: "run-001", FormName: "t_BD_Material", Level: "ERROR", Message: "timeout"})
	db.Create(&gormdb.SyncError{RunID: "run-001", FormName: "t_BD_Material", Level: "INFO", Message: "retrying"})

	rec := performRequest(r, http.MethodGet, "/api/v1/runs/run-001/events", "")
	require.Equal(t, http.StatusOK, rec.Code)

	var result map[string]any
	require.NoError(t, json.Unmarshal(rec.Body.Bytes(), &result))
	data := result["data"].([]any)
	require.Len(t, data, 2)
}

func TestListRunEventsRedactsSecrets(t *testing.T) {
	r, db := setupRunTest(t)
	now := time.Now()
	db.Create(&gormdb.SyncRun{RunID: "run-001", Status: "success", StartTime: now})
	db.Create(&gormdb.SyncError{RunID: "run-001", FormName: "test", Level: "ERROR", Message: "password=secret123"})

	rec := performRequest(r, http.MethodGet, "/api/v1/runs/run-001/events", "")
	require.Equal(t, http.StatusOK, rec.Code)
	require.NotContains(t, rec.Body.String(), "secret123")
}

func TestListRunEventsNotFound(t *testing.T) {
	r, _ := setupRunTest(t)

	rec := performRequest(r, http.MethodGet, "/api/v1/runs/nonexistent/events", "")
	require.Equal(t, http.StatusNotFound, rec.Code)
}

func TestCreateRunEngineNotInitialized(t *testing.T) {
	r, _ := setupRunTest(t)

	rec := performRequest(r, http.MethodPost, "/api/v1/runs", `{"forms":["A"],"sync_type":"full"}`)
	require.Equal(t, http.StatusServiceUnavailable, rec.Code)

	var result map[string]any
	require.NoError(t, json.Unmarshal(rec.Body.Bytes(), &result))
	err := result["error"].(map[string]any)
	require.Equal(t, "SYNC_ENGINE_NOT_INITIALIZED", err["code"])
}

// 回归测试：retryFailedForms 此前在 syncMutex.Lock 之后的所有出口都不解锁，
// 首次调用即永久锁死全部 runs 接口（原因：批一修复死锁，防止回归）。
// 通过注入 activeTask 让请求走"锁内发现已有任务 → 409"路径，
// 连续两次调用都必须在超时前返回 409；若锁未释放，第二次调用会永久阻塞。
func TestRetryFailedFormsReleasesSyncMutex(t *testing.T) {
	r, db := setupRunTest(t)

	oldEng, oldTask := syncEng, activeTask
	t.Cleanup(func() {
		syncMutex.Lock()
		syncEng, activeTask = oldEng, oldTask
		syncMutex.Unlock()
	})

	syncEng = syncengine.NewSyncEngine()
	activeTask = &activeSyncTask{runID: "RUN-BUSY"}

	require.NoError(t, db.Create(&gormdb.SyncRun{
		RunID:  "RUN-RETRY-SRC",
		Status: "failed",
	}).Error)
	require.NoError(t, db.Create(&gormdb.SyncRunForm{
		RunID:    "RUN-RETRY-SRC",
		FormName: "BD_Material",
		Status:   "failed",
	}).Error)

	type outcome struct {
		statuses [2]int
	}
	done := make(chan outcome, 1)
	go func() {
		first := performRequest(r, http.MethodPost, "/api/v1/runs/RUN-RETRY-SRC/retry-failed", "")
		second := performRequest(r, http.MethodPost, "/api/v1/runs/RUN-RETRY-SRC/retry-failed", "")
		done <- outcome{statuses: [2]int{first.Code, second.Code}}
	}()

	select {
	case res := <-done:
		require.Equal(t, [2]int{http.StatusConflict, http.StatusConflict}, res.statuses,
			"两次 retry-failed 调用都应返回 409（锁内冲突分支），且第二次不得阻塞")
	case <-time.After(10 * time.Second):
		t.Fatal("retryFailedForms 连续调用出现死锁：syncMutex 未在出口释放")
	}
}

// 回归测试：授予排队守卫接入 API 手动触发路径（原因：2026-11-03 卡死的是
// API 触发的全量，守卫此前只挂在调度入口，手动路径可无条件发起注定超时的空跑）。
func TestCreateRunBlockedByGrantGuard(t *testing.T) {
	r, db := setupRunTest(t)

	oldEng, oldGuard, oldTask := syncEng, grantGuardForTrigger, activeTask
	t.Cleanup(func() {
		syncEng, grantGuardForTrigger, activeTask = oldEng, oldGuard, oldTask
	})
	syncEng = syncengine.NewSyncEngine()
	grantGuardForTrigger = func(string) (bool, string) {
		return true, "目标库内存授予排队 10m（阈值 1m），本轮跳过"
	}

	rec := performRequest(r, http.MethodPost, "/api/v1/runs", `{"forms":["A"],"sync_type":"full"}`)
	require.Equal(t, http.StatusConflict, rec.Code)

	var result map[string]any
	require.NoError(t, json.Unmarshal(rec.Body.Bytes(), &result))
	errObj, ok := result["error"].(map[string]any)
	require.True(t, ok)
	require.Equal(t, "TARGET_DB_GRANT_QUEUE_BUSY", errObj["code"])
	require.Contains(t, errObj["message"], "内存授予排队")

	var count int64
	require.NoError(t, db.Model(&gormdb.SyncRun{}).Count(&count).Error)
	require.Zero(t, count, "守卫拦截时不得留下 sync run 记录")

	syncMutex.Lock()
	require.Nil(t, activeTask, "守卫拦截不得占用 activeTask")
	syncMutex.Unlock()
}

// 重试与 createRun 同一写入路径，同样必须被守卫拦截。
func TestRetryFailedFormsBlockedByGrantGuard(t *testing.T) {
	r, db := setupRunTest(t)

	oldEng, oldGuard, oldTask := syncEng, grantGuardForTrigger, activeTask
	t.Cleanup(func() {
		syncEng, grantGuardForTrigger, activeTask = oldEng, oldGuard, oldTask
	})
	syncEng = syncengine.NewSyncEngine()
	grantGuardForTrigger = func(string) (bool, string) {
		return true, "目标库内存授予排队 10m（阈值 1m），本轮跳过"
	}

	require.NoError(t, db.Create(&gormdb.SyncRun{RunID: "RUN-GUARD-SRC", Status: "failed"}).Error)
	require.NoError(t, db.Create(&gormdb.SyncRunForm{
		RunID: "RUN-GUARD-SRC", FormName: "BD_Material", Status: "failed",
	}).Error)

	rec := performRequest(r, http.MethodPost, "/api/v1/runs/RUN-GUARD-SRC/retry-failed", "")
	require.Equal(t, http.StatusConflict, rec.Code)

	var result map[string]any
	require.NoError(t, json.Unmarshal(rec.Body.Bytes(), &result))
	errObj, ok := result["error"].(map[string]any)
	require.True(t, ok)
	require.Equal(t, "TARGET_DB_GRANT_QUEUE_BUSY", errObj["code"])

	// 守卫出口必须已释放 syncMutex：getSyncStatus 同样要拿这把锁，
	// 无活动运行时按设计返回 404——能正常返回即证明锁未泄漏（对照既有死锁回归测试）
	statusRec := performRequest(r, http.MethodGet, "/api/v1/sync/status", "")
	require.Equal(t, http.StatusNotFound, statusRec.Code)
}
