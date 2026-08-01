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
