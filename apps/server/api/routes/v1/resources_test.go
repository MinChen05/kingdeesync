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

func setupV1Test(t *testing.T) (*gin.Engine, *gorm.DB) {
	t.Helper()
	oldDB := gormdb.DB

	db, err := gorm.Open(sqlite.Open(fmt.Sprintf("file:v1-test-%d?mode=memory&cache=shared", time.Now().UnixNano())), &gorm.Config{})
	require.NoError(t, err)
	gormdb.DB = db

	t.Cleanup(func() {
		gormdb.DB = oldDB
	})

	require.NoError(t, db.AutoMigrate(&gormdb.SyncRun{}, &gormdb.SyncRunForm{}, &gormdb.SyncError{}, &gormdb.ScheduleJob{}))

	r := gin.New()
	InitRoutes(r, nil)
	return r, db
}

func performReq(r *gin.Engine, method, path, body string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(method, path, nil)
	if body != "" {
		req = httptest.NewRequest(method, path, strings.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
	}
	rec := httptest.NewRecorder()
	r.ServeHTTP(rec, req)
	return rec
}

func TestOverviewReturnsEnvelope(t *testing.T) {
	r, _ := setupV1Test(t)

	rec := performReq(r, http.MethodGet, "/api/v1/overview", "")
	require.Equal(t, http.StatusOK, rec.Code)

	var result map[string]any
	require.NoError(t, json.Unmarshal(rec.Body.Bytes(), &result))
	require.NotNil(t, result["data"])
	data := result["data"].(map[string]any)
	require.NotNil(t, data["today"])
	require.NotNil(t, data["health"])
	require.NotNil(t, data["trend"])
}

func TestListSchedulesEmpty(t *testing.T) {
	r, _ := setupV1Test(t)

	rec := performReq(r, http.MethodGet, "/api/v1/schedules", "")
	require.Equal(t, http.StatusOK, rec.Code)

	var result map[string]any
	require.NoError(t, json.Unmarshal(rec.Body.Bytes(), &result))
	data := result["data"].([]any)
	require.Len(t, data, 0)
}

func TestSchedulerStatus(t *testing.T) {
	r, _ := setupV1Test(t)

	rec := performReq(r, http.MethodGet, "/api/v1/schedules/status", "")
	require.Equal(t, http.StatusOK, rec.Code)

	var result map[string]any
	require.NoError(t, json.Unmarshal(rec.Body.Bytes(), &result))
	data := result["data"].(map[string]any)
	require.Contains(t, data, "enabled")
}

func TestCreateAndGetSchedule(t *testing.T) {
	r, _ := setupV1Test(t)

	// Create
	createBody := `{"name":"test-job","cron_expr":"0 */20 * * * *","sync_type":"incremental"}`
	rec := performReq(r, http.MethodPost, "/api/v1/schedules", createBody)
	require.Equal(t, http.StatusCreated, rec.Code)

	var result map[string]any
	require.NoError(t, json.Unmarshal(rec.Body.Bytes(), &result))
	data := result["data"].(map[string]any)
	require.Equal(t, "test-job", data["name"])

	// List should have one
	rec = performReq(r, http.MethodGet, "/api/v1/schedules", "")
	require.Equal(t, http.StatusOK, rec.Code)
	require.NoError(t, json.Unmarshal(rec.Body.Bytes(), &result))
	dataList := result["data"].([]any)
	require.Len(t, dataList, 1)
}

func TestDeleteSchedule(t *testing.T) {
	r, db := setupV1Test(t)

	// Create first
	db.Create(&gormdb.ScheduleJob{Name: "del-me", CronExpr: "0 * * * *", SyncType: "incremental"})

	rec := performReq(r, http.MethodDelete, "/api/v1/schedules/1", "")
	require.Equal(t, http.StatusOK, rec.Code)

	// Verify deleted
	rec = performReq(r, http.MethodDelete, "/api/v1/schedules/999", "")
	require.Equal(t, http.StatusNotFound, rec.Code)
}

func TestDiagnostics(t *testing.T) {
	r, _ := setupV1Test(t)

	rec := performReq(r, http.MethodGet, "/api/v1/system/diagnostics", "")
	require.Equal(t, http.StatusOK, rec.Code)

	var result map[string]any
	require.NoError(t, json.Unmarshal(rec.Body.Bytes(), &result))
	data := result["data"].(map[string]any)
	require.NotNil(t, data["kingdee_api"])
	require.NotNil(t, data["database"])
}

func TestSystemConfigNotLoaded(t *testing.T) {
	r, _ := setupV1Test(t)

	rec := performReq(r, http.MethodGet, "/api/v1/system/config", "")
	// May return 503 if config is not loaded in test env
	require.Contains(t, []int{http.StatusOK, http.StatusServiceUnavailable}, rec.Code)
}

func TestUpdateSystemConfigNotImplemented(t *testing.T) {
	r, _ := setupV1Test(t)

	rec := performReq(r, http.MethodPut, "/api/v1/system/config", "{}")
	require.Equal(t, http.StatusNotImplemented, rec.Code)
}
