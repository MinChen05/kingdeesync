package v1

import (
	"net/http"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/kingdee-sync/go/internal/config"
	"github.com/kingdee-sync/go/internal/dashboard"
	kingdeeDB "github.com/kingdee-sync/go/internal/db"
	"github.com/kingdee-sync/go/internal/gormdb"
	"github.com/kingdee-sync/go/internal/kind"
)

func initSystemRoutes(group *gin.RouterGroup) {
	group.GET("/system/diagnostics", getDiagnostics)
	group.GET("/system/config", getSystemConfig)
	group.PUT("/system/config", updateSystemConfig)
	group.POST("/system/test-connections", testConnections)
	group.GET("/system/version", getVersion)
	group.POST("/system/archive", archiveSystem)
	group.GET("/logs", listLogs)
}

func getDiagnostics(c *gin.Context) {
	health := dashboard.GetHealthStatus()

	WriteData(c, http.StatusOK, Diagnostics{
		KingdeeAPI: DiagService{
			Status:     health.KingdeeAPI.Status,
			ResponseMs: &health.KingdeeAPI.ResponseMs,
		},
		Database: DiagService{
			Status:     health.Database.Status,
			ResponseMs: &health.Database.ResponseMs,
		},
		Scheduler: DiagService{
			Status: health.Scheduler.Status,
		},
		LogService: DiagService{
			Status: health.LogService.Status,
		},
	})
}

func getSystemConfig(c *gin.Context) {
	cfg := config.Get()
	if cfg == nil {
		WriteProblem(c, http.StatusServiceUnavailable, Problem{
			Code:    "INTERNAL_ERROR",
			Message: "config not loaded",
		})
		return
	}

	dbCfg := cfg.GetEffectiveDatabase()

	WriteData(c, http.StatusOK, SystemConfig{
		"server": map[string]any{
			"host": cfg.Server.Host,
			"port": cfg.Server.Port,
		},
		"sync": map[string]any{
			"auto_sync":         cfg.Sync.AutoSync,
			"sync_interval":     cfg.Sync.SyncInterval,
			"sync_type":         cfg.Sync.SyncType,
			"time_window_days":  cfg.Sync.TimeWindowDays,
			"table_concurrency": cfg.Sync.TableConcurrency,
		},
		"kingdee": map[string]any{
			"login_url":           cfg.Kingdee.LoginURL,
			"query_url":           cfg.Kingdee.QueryURL,
			"acct_id":             cfg.Kingdee.AcctID,
			"username":            cfg.Kingdee.Username,
			"lcid":                cfg.Kingdee.Lcid,
			"page_size":           cfg.Kingdee.PageSize,
			"max_pages":           cfg.Kingdee.MaxPages,
			"rate_limit_qps":      cfg.Kingdee.RateLimitQPS,
			"keep_session_alive":  cfg.Kingdee.KeepSessionAlive,
			"keep_alive_interval": cfg.Kingdee.KeepAliveInterval,
		},
		"database": map[string]any{
			"type":     dbCfg.Type,
			"host":     dbCfg.Host,
			"port":     dbCfg.Port,
			"user":     dbCfg.User,
			"database": dbCfg.DBName,
		},
	})
}

func updateSystemConfig(c *gin.Context) {
	// Delegate to legacy PUT /api/config for now
	WriteProblem(c, http.StatusNotImplemented, Problem{
		Code:    "NOT_IMPLEMENTED",
		Message: "use PUT /api/config for now",
	})
}

func testConnections(c *gin.Context) {
	db := gormdb.DB
	dbOk := db != nil && kingdeeDB.DB != nil && kingdeeDB.DB.Ping() == nil

	// Test Kingdee API connection with timeout
	kdOk := false
	kdStart := time.Now()
	done := make(chan struct{})
	go func() {
		client := kind.NewKingdeeClient()
		kdOk = client.TestConnection()
		close(done)
	}()
	select {
	case <-done:
	case <-time.After(8 * time.Second):
		kdOk = false
	}
	kdMs := int(time.Since(kdStart).Milliseconds())

	WriteData(c, http.StatusOK, gin.H{
		"kingdee_api": map[string]any{
			"status":      map[bool]string{true: "ok", false: "error"}[kdOk],
			"response_ms": kdMs,
		},
		"database": map[string]any{
			"status": map[bool]string{true: "ok", false: "error"}[dbOk],
		},
	})
}

// config package is used for Get()
var _ = config.Get

func getVersion(c *gin.Context) {
	WriteData(c, http.StatusOK, gin.H{
		"version":    "0.1.0",
		"build_time": "2026-08-01T10:00:00Z",
	})
}

func archiveSystem(c *gin.Context) {
	var body struct {
		DaysToKeep int `json:"days_to_keep"`
	}
	if err := c.ShouldBindJSON(&body); err != nil || body.DaysToKeep <= 0 {
		WriteProblem(c, http.StatusBadRequest, Problem{
			Code:    "INVALID_PARAMS",
			Message: "days_to_keep must be a positive integer",
		})
		return
	}

	db := gormdb.DB
	if db == nil {
		WriteProblem(c, http.StatusServiceUnavailable, Problem{
			Code:    "DB_NOT_AVAILABLE",
			Message: "database not available",
		})
		return
	}

	cutoff := time.Now().AddDate(0, 0, -body.DaysToKeep)

	errResult := db.Where("created_at < ?", cutoff).Delete(&gormdb.SyncError{})
	if errResult.Error != nil {
		WriteProblem(c, http.StatusInternalServerError, Problem{
			Code:    "INTERNAL_ERROR",
			Message: "failed to archive errors: " + errResult.Error.Error(),
		})
		return
	}
	runResult := db.Where("start_time < ?", cutoff).Delete(&gormdb.SyncRun{})
	if runResult.Error != nil {
		WriteProblem(c, http.StatusInternalServerError, Problem{
			Code:    "INTERNAL_ERROR",
			Message: "failed to archive runs: " + runResult.Error.Error(),
		})
		return
	}

	WriteData(c, http.StatusOK, gin.H{
		"message":        "archived successfully",
		"days_to_keep":   body.DaysToKeep,
		"errors_deleted": errResult.RowsAffected,
		"runs_deleted":   runResult.RowsAffected,
		"total_deleted":  errResult.RowsAffected + runResult.RowsAffected,
	})
}

func listLogs(c *gin.Context) {
	db := gormdb.DB
	if db == nil {
		WriteData(c, http.StatusOK, gin.H{"logs": []RunEvent{}, "total": 0})
		return
	}

	level := c.Query("level")
	formName := c.Query("form_name")
	daysStr := c.DefaultQuery("days", "7")
	limitStr := c.DefaultQuery("limit", "50")

	days, _ := strconv.Atoi(daysStr)
	limit, _ := strconv.Atoi(limitStr)
	if days < 1 {
		days = 7
	}
	if limit < 1 || limit > 200 {
		limit = 50
	}

	since := time.Now().AddDate(0, 0, -days)

	query := db.Model(&gormdb.SyncError{}).Where("created_at >= ?", since)
	if level != "" {
		query = query.Where("level = ?", level)
	}
	if formName != "" {
		query = query.Where("form_name = ?", formName)
	}

	var total int64
	query.Count(&total)

	var errors []gormdb.SyncError
	query.Order("created_at DESC").Limit(limit).Find(&errors)

	events := make([]RunEvent, len(errors))
	for i, e := range errors {
		events[i] = toV1RunEvent(e)
	}

	WriteData(c, http.StatusOK, gin.H{
		"logs":  events,
		"total": total,
	})
}
