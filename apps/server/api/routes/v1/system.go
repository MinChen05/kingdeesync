package v1

import (
	"crypto/sha256"
	"encoding/hex"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
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
	// Webhook
	group.GET("/webhooks", listWebhooks)
	group.POST("/webhooks", createWebhook)
	group.DELETE("/webhooks/:id", deleteWebhook)
	// Config snapshots
	group.GET("/config/snapshots", listConfigSnapshots)
	group.POST("/config/snapshots", createConfigSnapshot)
	group.POST("/config/snapshots/:id/rollback", rollbackConfigSnapshot)
	// Form templates
	group.GET("/templates", listFormTemplates)
	group.POST("/templates", createFormTemplate)
	group.DELETE("/templates/:id", deleteFormTemplate)
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
		client := kind.SharedClient()
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

// ─── Webhook endpoints ───

func listWebhooks(c *gin.Context) {
	db := gormdb.DB
	if db == nil {
		WriteData(c, http.StatusOK, []gin.H{})
		return
	}
	var webhooks []gormdb.WebhookConfig
	db.Find(&webhooks)
	WriteData(c, http.StatusOK, webhooks)
}

func createWebhook(c *gin.Context) {
	db := gormdb.DB
	if db == nil {
		WriteProblem(c, http.StatusServiceUnavailable, Problem{Code: "INTERNAL_ERROR", Message: "database not initialized"})
		return
	}
	var req struct {
		URL     string `json:"url" binding:"required"`
		Events  string `json:"events"`
		Enabled *bool  `json:"enabled"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		WriteProblem(c, http.StatusBadRequest, Problem{Code: "INVALID_REQUEST", Message: err.Error()})
		return
	}
	wh := gormdb.WebhookConfig{
		URL:     req.URL,
		Events:  req.Events,
		Enabled: req.Enabled == nil || *req.Enabled,
	}
	if err := db.Create(&wh).Error; err != nil {
		WriteProblem(c, http.StatusInternalServerError, Problem{Code: "INTERNAL_ERROR", Message: "failed to create webhook"})
		return
	}
	WriteData(c, http.StatusCreated, wh)
}

func deleteWebhook(c *gin.Context) {
	db := gormdb.DB
	if db == nil {
		WriteProblem(c, http.StatusServiceUnavailable, Problem{Code: "INTERNAL_ERROR", Message: "database not initialized"})
		return
	}
	id := c.Param("id")
	if err := db.Delete(&gormdb.WebhookConfig{}, id).Error; err != nil {
		WriteProblem(c, http.StatusInternalServerError, Problem{Code: "INTERNAL_ERROR", Message: "failed to delete webhook"})
		return
	}
	WriteData(c, http.StatusOK, gin.H{"message": "webhook deleted"})
}

// ─── Config Snapshot endpoints ───

// configSnapshotSummary 是快照的脱敏视图。
// （原因：IniContent/JsonConfig 含密码等凭据，列表与创建响应不得原样序列化全文内容；
// 回滚为服务端按 id 读取快照，无需将内容下发给客户端）
type configSnapshotSummary struct {
	ID         uint      `json:"id"`
	ConfigHash string    `json:"config_hash"`
	Labels     string    `json:"labels"`
	CreatedAt  time.Time `json:"created_at"`
	IniSize    int       `json:"ini_size"`
	JsonSize   int       `json:"json_size"`
}

func snapshotSummaryOf(s gormdb.ConfigSnapshot) configSnapshotSummary {
	return configSnapshotSummary{
		ID:         s.ID,
		ConfigHash: s.ConfigHash,
		Labels:     s.Labels,
		CreatedAt:  s.CreatedAt,
		IniSize:    len(s.IniContent),
		JsonSize:   len(s.JsonConfig),
	}
}

func listConfigSnapshots(c *gin.Context) {
	db := gormdb.DB
	if db == nil {
		WriteData(c, http.StatusOK, []gin.H{})
		return
	}
	var snapshots []gormdb.ConfigSnapshot
	db.Order("created_at DESC").Limit(50).Find(&snapshots)
	summaries := make([]configSnapshotSummary, 0, len(snapshots))
	for _, s := range snapshots {
		summaries = append(summaries, snapshotSummaryOf(s))
	}
	WriteData(c, http.StatusOK, summaries)
}

func createConfigSnapshot(c *gin.Context) {
	db := gormdb.DB
	if db == nil {
		WriteProblem(c, http.StatusServiceUnavailable, Problem{Code: "INTERNAL_ERROR", Message: "database not initialized"})
		return
	}

	var req struct {
		Labels string `json:"labels"`
	}
	_ = c.ShouldBindJSON(&req)

	// Read current config files
	iniPath := config.ConfigPath()
	iniContent, _ := os.ReadFile(iniPath)
	jsonPath := filepath.Join(filepath.Dir(iniPath), "form-queries.json")
	jsonContent, _ := os.ReadFile(jsonPath)

	hash := sha256.Sum256(append(iniContent, jsonContent...))
	hashHex := hex.EncodeToString(hash[:])

	snap := gormdb.ConfigSnapshot{
		ConfigHash: hashHex,
		IniContent: string(iniContent),
		JsonConfig: string(jsonContent),
		Labels:     req.Labels,
	}
	if err := db.Create(&snap).Error; err != nil {
		WriteProblem(c, http.StatusInternalServerError, Problem{Code: "INTERNAL_ERROR", Message: "failed to create snapshot"})
		return
	}
	WriteData(c, http.StatusCreated, snapshotSummaryOf(snap))
}

func rollbackConfigSnapshot(c *gin.Context) {
	db := gormdb.DB
	if db == nil {
		WriteProblem(c, http.StatusServiceUnavailable, Problem{Code: "INTERNAL_ERROR", Message: "database not initialized"})
		return
	}

	id := c.Param("id")
	var snap gormdb.ConfigSnapshot
	if err := db.First(&snap, id).Error; err != nil {
		WriteProblem(c, http.StatusNotFound, Problem{Code: "SNAPSHOT_NOT_FOUND", Message: "snapshot not found"})
		return
	}

	// Write config files back
	iniPath := config.ConfigPath()
	if iniPath == "" {
		WriteProblem(c, http.StatusInternalServerError, Problem{Code: "INTERNAL_ERROR", Message: "config path not found"})
		return
	}

	// 先留存当前文件内容与权限，供部分失败时真实回滚。
	// （原因：此前 JSON 写失败时把 INI 写成空串，等于亲手让服务无法重启；权限也固定 0644 导致任何本机用户可读密码）
	jsonPath := filepath.Join(filepath.Dir(iniPath), "form-queries.json")
	oldIni, iniReadErr := os.ReadFile(iniPath)
	iniMode := os.FileMode(0600)
	if fi, err := os.Stat(iniPath); err == nil {
		iniMode = fi.Mode().Perm()
	}
	oldJson, _ := os.ReadFile(jsonPath)
	jsonMode := os.FileMode(0600)
	if fi, err := os.Stat(jsonPath); err == nil {
		jsonMode = fi.Mode().Perm()
	}

	if err := os.WriteFile(iniPath, []byte(snap.IniContent), iniMode); err != nil {
		WriteProblem(c, http.StatusInternalServerError, Problem{Code: "INTERNAL_ERROR", Message: "failed to write config: " + err.Error()})
		return
	}

	if snap.JsonConfig != "" {
		if err := os.WriteFile(jsonPath, []byte(snap.JsonConfig), jsonMode); err != nil {
			// 用回滚前的原文恢复 INI 与 form-queries；若原文都读不出来则保持已写入内容并如实报告
			if iniReadErr == nil {
				if restoreErr := os.WriteFile(iniPath, oldIni, iniMode); restoreErr != nil {
					log.Printf("[CONFIG] rollback restore INI failed: %v", restoreErr)
				}
			}
			if oldJson != nil {
				if restoreErr := os.WriteFile(jsonPath, oldJson, jsonMode); restoreErr != nil {
					log.Printf("[CONFIG] rollback restore form-queries failed: %v", restoreErr)
				}
			}
			WriteProblem(c, http.StatusInternalServerError, Problem{Code: "INTERNAL_ERROR", Message: "failed to write form-queries: " + err.Error()})
			return
		}
	}

	// Reload config in memory
	config.Reload(iniPath)

	WriteData(c, http.StatusOK, gin.H{"message": "configuration rolled back to snapshot " + id})
}

// fileHash computes sha256 hex of a file.
func fileHash(path string) string {
	f, err := os.Open(path)
	if err != nil {
		return ""
	}
	defer f.Close()
	h := sha256.New()
	io.Copy(h, f)
	return hex.EncodeToString(h.Sum(nil))
}

// ─── Form Template endpoints ───

func listFormTemplates(c *gin.Context) {
	db := gormdb.DB
	if db == nil {
		WriteData(c, http.StatusOK, []gin.H{})
		return
	}
	var templates []gormdb.FormQueryTemplate
	db.Find(&templates)
	WriteData(c, http.StatusOK, templates)
}

func createFormTemplate(c *gin.Context) {
	db := gormdb.DB
	if db == nil {
		WriteProblem(c, http.StatusServiceUnavailable, Problem{Code: "INTERNAL_ERROR", Message: "database not initialized"})
		return
	}
	var req struct {
		Name        string `json:"name" binding:"required"`
		Description string `json:"description"`
		Queries     string `json:"queries" binding:"required"` // JSON array
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		WriteProblem(c, http.StatusBadRequest, Problem{Code: "INVALID_REQUEST", Message: err.Error()})
		return
	}
	tmpl := gormdb.FormQueryTemplate{
		Name:        req.Name,
		Description: req.Description,
		Queries:     req.Queries,
	}
	if err := db.Create(&tmpl).Error; err != nil {
		WriteProblem(c, http.StatusInternalServerError, Problem{Code: "INTERNAL_ERROR", Message: "failed to create template"})
		return
	}
	WriteData(c, http.StatusCreated, tmpl)
}

func deleteFormTemplate(c *gin.Context) {
	db := gormdb.DB
	if db == nil {
		WriteProblem(c, http.StatusServiceUnavailable, Problem{Code: "INTERNAL_ERROR", Message: "database not initialized"})
		return
	}
	id := c.Param("id")
	if err := db.Delete(&gormdb.FormQueryTemplate{}, id).Error; err != nil {
		WriteProblem(c, http.StatusInternalServerError, Problem{Code: "INTERNAL_ERROR", Message: "failed to delete template"})
		return
	}
	WriteData(c, http.StatusOK, gin.H{"message": "template deleted"})
}
