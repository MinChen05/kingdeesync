package dashboard

import (
	"fmt"
	"strings"
	"sync"
	"time"

	"github.com/kingdee-sync/go/internal/db"
	"github.com/kingdee-sync/go/internal/gormdb"
	"github.com/kingdee-sync/go/internal/kind"
)

// Health cache to avoid frequent slow checks
var (
	healthCache     HealthStatus
	healthCacheTime time.Time
	healthMu        sync.RWMutex
	healthTTL       = 5 * time.Second // cache for 5 seconds
)

// TodayStats holds today's dashboard statistics.
type TodayStats struct {
	SyncCount    int     `json:"sync_count"`
	SuccessRate  float64 `json:"success_rate"`
	FailCount    int     `json:"fail_count"`
	PendingCount int     `json:"pending_count"`
	AvgDuration  float64 `json:"avg_duration"`
	LastSyncTime string  `json:"last_sync_time"`
	// Yesterday comparison
	YesterdaySyncCount int     `json:"yesterday_sync_count"`
	YesterdayRate      float64 `json:"yesterday_success_rate"`
}

// TrendDay holds a single day's trend data.
type TrendDay struct {
	Date        string  `json:"date"`
	SyncCount   int     `json:"sync_count"`
	Records     int     `json:"records"`
	SuccessRate float64 `json:"success_rate"`
}

// TopForm holds a form's failure statistics.
type TopForm struct {
	FormName     string `json:"form_name"`
	FailureCount int    `json:"failure_count"`
	LastError    string `json:"last_error"`
}

// HealthStatus holds system health information.
type HealthStatus struct {
	KingdeeAPI struct {
		Status     string `json:"status"`
		ResponseMs int    `json:"response_ms"`
		TodayCalls int    `json:"today_calls"`
	} `json:"kingdee_api"`
	Database struct {
		Status     string `json:"status"`
		ResponseMs int    `json:"response_ms"`
		ConnCount  int    `json:"conn_count"`
	} `json:"database"`
	Scheduler struct {
		Status   string `json:"status"`
		Uptime   string `json:"uptime"`
		NextExec string `json:"next_exec"`
	} `json:"scheduler"`
	LogService struct {
		Status     string `json:"status"`
		WriteSpeed string `json:"write_speed"`
		LogSize    string `json:"log_size"`
	} `json:"log_service"`
}

// RecentRun holds a recent sync run summary.
type RecentRun struct {
	StartTime   string  `json:"start_time"`
	TaskName    string  `json:"task_name"`
	FormName    string  `json:"form_name"`
	FormCount   int     `json:"form_count"`
	Status      string  `json:"status"`
	RecordCount int     `json:"record_count"`
	DurationSec float64 `json:"duration_seconds"`
}

// RiskItem holds a risk alert.
type RiskItem struct {
	Title        string `json:"title"`
	Desc         string `json:"desc"`
	Time         string `json:"time"`
	Severity     string `json:"severity"` // "high", "medium", "low"
	FailureCount int64  `json:"failure_count"`
}

func GetTodayStats() TodayStats {
	db := gormdb.DB
	if db == nil {
		return TodayStats{}
	}

	now := time.Now()
	todayStart := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, now.Location())
	yesterdayStart := todayStart.AddDate(0, 0, -1)
	yesterdayEnd := todayStart

	var stats TodayStats

	// Today stats from go_sync_runs
	var todayCount int64
	db.Model(&gormdb.SyncRun{}).Where("start_time >= ?", todayStart).Count(&todayCount)
	stats.SyncCount = int(todayCount)

	var todaySuccess int64
	db.Model(&gormdb.SyncRun{}).Where("start_time >= ? AND status = 'success'", todayStart).Count(&todaySuccess)

	if todayCount > 0 {
		stats.SuccessRate = float64(todaySuccess) / float64(todayCount) * 100
	}

	var todayFail int64
	db.Model(&gormdb.SyncRun{}).Where("start_time >= ? AND status IN ('failed', 'failed_abnormal_exit')", todayStart).Count(&todayFail)
	stats.FailCount = int(todayFail)

	var avgDur *float64
	db.Model(&gormdb.SyncRun{}).Where("start_time >= ? AND duration_seconds > 0", todayStart).
		Select("AVG(duration_seconds)").Scan(&avgDur)
	if avgDur != nil {
		stats.AvgDuration = *avgDur
	}

	var lastRun gormdb.SyncRun
	result := db.Where("start_time >= ?", todayStart).Order("start_time DESC").First(&lastRun)
	if result.Error == nil && !lastRun.StartTime.IsZero() {
		stats.LastSyncTime = lastRun.StartTime.Format("15:04:05")
	}

	// Yesterday stats
	var yesterdayCount int64
	db.Model(&gormdb.SyncRun{}).Where("start_time >= ? AND start_time < ?", yesterdayStart, yesterdayEnd).Count(&yesterdayCount)
	stats.YesterdaySyncCount = int(yesterdayCount)

	var yesterdaySuccess int64
	db.Model(&gormdb.SyncRun{}).Where("start_time >= ? AND start_time < ? AND status = 'success'", yesterdayStart, yesterdayEnd).Count(&yesterdaySuccess)

	if yesterdayCount > 0 {
		stats.YesterdayRate = float64(yesterdaySuccess) / float64(yesterdayCount) * 100
	}

	// Pending count (running or stuck)
	var pendingCount int64
	db.Model(&gormdb.SyncRun{}).Where("status = 'running'").Count(&pendingCount)
	stats.PendingCount = int(pendingCount)

	return stats
}

func GetTrend7d() []TrendDay {
	gdb := gormdb.DB
	if gdb == nil {
		return []TrendDay{}
	}

	var days []TrendDay
	now := time.Now()

	for i := 6; i >= 0; i-- {
		day := now.AddDate(0, 0, -i)
		dayStart := time.Date(day.Year(), day.Month(), day.Day(), 0, 0, 0, 0, day.Location())
		dayEnd := dayStart.AddDate(0, 0, 1)

		trend := TrendDay{
			Date: day.Format("2006-01-02"),
		}

		var count int64
		gdb.Model(&gormdb.SyncRun{}).Where("start_time >= ? AND start_time < ?", dayStart, dayEnd).Count(&count)
		trend.SyncCount = int(count)

		var totalRecords int64
		gdb.Model(&gormdb.SyncRun{}).Where("start_time >= ? AND start_time < ?", dayStart, dayEnd).
			Select("COALESCE(SUM(total_records), 0)").Scan(&totalRecords)
		trend.Records = int(totalRecords)

		var successCount int64
		gdb.Model(&gormdb.SyncRun{}).Where("start_time >= ? AND start_time < ? AND status = 'success'", dayStart, dayEnd).Count(&successCount)

		if trend.SyncCount > 0 {
			trend.SuccessRate = float64(successCount) / float64(trend.SyncCount) * 100
		}

		days = append(days, trend)
	}

	return days
}

func GetTopForms7d(limit int) []TopForm {
	gdb := gormdb.DB
	if gdb == nil {
		return []TopForm{}
	}

	if limit <= 0 || limit > 20 {
		limit = 5
	}

	now := time.Now()
	weekAgo := now.AddDate(0, 0, -7)

	type Row struct {
		FormName     string `gorm:"column:form_name"`
		FailureCount int64  `gorm:"column:failure_count"`
		LastError    string `gorm:"column:last_error"`
	}

	var rows []Row
	gdb.Table("go_sync_errors").
		Where("created_at >= ?", weekAgo.Format("2006-01-02 15:04:05")).
		Where("level IN ?", []string{"ERROR", "WARNING"}).
		Select("form_name, COUNT(*) as failure_count, MAX(message) as last_error").
		Group("form_name").
		Order("failure_count DESC").
		Limit(limit).
		Scan(&rows)

	var result []TopForm
	for _, r := range rows {
		result = append(result, TopForm{
			FormName:     r.FormName,
			FailureCount: int(r.FailureCount),
			LastError:    truncateString(r.LastError, 100),
		})
	}

	return result
}

func GetHealthStatus() HealthStatus {
	// Return cached result if still valid
	healthMu.RLock()
	if time.Since(healthCacheTime) < healthTTL {
		cached := healthCache
		healthMu.RUnlock()
		return cached
	}
	healthMu.RUnlock()

	healthMu.Lock()
	defer healthMu.Unlock()

	// Double-check after acquiring write lock
	if time.Since(healthCacheTime) < healthTTL {
		return healthCache
	}

	var health HealthStatus

	// Kingdee API health with timeout
	done := make(chan struct{})
	var ok bool
	var duration int64
	go func() {
		start := time.Now()
		client := kind.NewKingdeeClient()
		ok = client.TestConnection()
		duration = time.Since(start).Milliseconds()
		close(done)
	}()

	select {
	case <-done:
		// completed
	case <-time.After(5 * time.Second):
		// timeout
		ok = false
		duration = 5000
	}

	health.KingdeeAPI.Status = map[bool]string{true: "ok", false: "error"}[ok]
	health.KingdeeAPI.ResponseMs = int(duration)
	health.KingdeeAPI.TodayCalls = 0 // Would need to track from logs

	// Database health
	if db.DB != nil {
		start := time.Now()
		err := db.DB.Ping()
		duration := time.Since(start).Milliseconds()

		health.Database.Status = map[bool]string{true: "ok", false: "error"}[err == nil]
		health.Database.ResponseMs = int(duration)

		stats := db.DB.Stats()
		health.Database.ConnCount = int(stats.InUse)
	} else {
		health.Database.Status = "error"
	}

	// Scheduler health
	health.Scheduler.Status = "ok"
	health.Scheduler.Uptime = "运行中"
	health.Scheduler.NextExec = "已配置"

	// Log service health
	health.LogService.Status = "ok"
	health.LogService.WriteSpeed = "正常"
	health.LogService.LogSize = "正常"

	// Cache result
	healthCache = health
	healthCacheTime = time.Now()

	return health
}

func GetRecentRuns(limit int) []RecentRun {
	gdb := gormdb.DB
	if gdb == nil {
		return []RecentRun{}
	}

	if limit <= 0 || limit > 50 {
		limit = 10
	}

	// 使用 GORM ORM 查询，保证跨数据库兼容（内部状态库为 SQLite）。
	// 原先的 SQL Server 专用写法（SELECT TOP / CONVERT / ISNULL）在 SQLite 下会直接报错，
	// 导致返回 nil 切片、接口序列化为 data:null。（原因：修复最近同步为空的问题）
	var runs []gormdb.SyncRun
	gdb.Order("start_time DESC").Limit(limit).Find(&runs)

	// 用 make 初始化为空切片而非 nil，确保无数据时接口返回 [] 而不是 null。
	result := make([]RecentRun, 0, len(runs))
	for _, r := range runs {
		// Get form names
		var formNames []string
		gdb.Model(&gormdb.SyncRunForm{}).Where("run_id = ?", r.RunID).
			Pluck("form_name", &formNames)

		var displayForms string
		if len(formNames) == 0 {
			displayForms = "全部"
		} else if len(formNames) <= 3 {
			displayForms = joinStrings(formNames, "、")
		} else {
			displayForms = formNames[0] + "等" + fmt.Sprintf("%d个表单", len(formNames))
		}

		// Convert task name to Chinese
		taskName := map[string]string{
			"api":                 "手动同步",
			"manual_sync":         "手动同步",
			"default_incremental": "定时增量同步",
			"weekly_full":         "每周全量同步",
		}[r.TaskName]
		if taskName == "" {
			taskName = r.TaskName
		}

		// Format start_time to "MM-DD HH:MM"
		startTimeStr := ""
		if !r.StartTime.IsZero() {
			startTimeStr = r.StartTime.Format("01-02 15:04")
		}

		result = append(result, RecentRun{
			StartTime:   startTimeStr,
			TaskName:    taskName,
			FormName:    displayForms,
			FormCount:   r.FormCount,
			Status:      r.Status,
			RecordCount: int(r.TotalRecords),
			DurationSec: r.DurationSeconds,
		})
	}

	return result
}

func GetRiskItems(limit int) []RiskItem {
	gdb := gormdb.DB
	if gdb == nil {
		return []RiskItem{}
	}

	if limit <= 0 || limit > 10 {
		limit = 3
	}

	var risks []RiskItem

	// Get forms with most errors in last 7 days
	now := time.Now()
	weekAgo := now.AddDate(0, 0, -7)

	type FailRow struct {
		FormName     string `gorm:"column:form_name"`
		FailureCount int64  `gorm:"column:failure_count"`
		LastError    string `gorm:"column:last_error"`
		LastTime     string `gorm:"column:last_time"`
	}

	// Use strftime to force SQLite to return a plain string for created_at.
	// （原因：SQLite 中 created_at 存储格式含纳秒和时区，GORM Scan 到 time.Time 会报
	// "unsupported Scan, storing driver.Value type string into type *time.Time"）
	var failRows []FailRow
	gdb.Table("go_sync_errors").
		Where("created_at >= ?", weekAgo.Format("2006-01-02 15:04:05")).
		Select("form_name, COUNT(*) as failure_count, MAX(message) as last_error, " +
			"strftime('%Y-%m-%d %H:%M:%S', MAX(created_at)) as last_time").
		Group("form_name").
		Order("failure_count DESC").
		Limit(limit).
		Scan(&failRows)

	for _, r := range failRows {
		timeStr := ""
		if t, err := time.Parse("2006-01-02 15:04:05", r.LastTime); err == nil {
			timeStr = t.Format("01-02 15:04")
		} else if t, err := time.Parse("2006-01-02T15:04:05", r.LastTime); err == nil {
			timeStr = t.Format("01-02 15:04")
		} else {
			timeStr = r.LastTime
		}
		risks = append(risks, RiskItem{
			Title:        r.FormName,
			Desc:         "近期失败次数较多，请检查该表单同步日志",
			Time:         timeStr,
			Severity:     "high",
			FailureCount: r.FailureCount,
		})
	}

	// Add recent failed runs
	if len(risks) < limit {
		var recentRuns []gormdb.SyncRun
		gdb.Where("status IN ?", []string{"failed", "failed_abnormal_exit"}).
			Order("start_time DESC").
			Limit(limit - len(risks)).
			Find(&recentRuns)

		for _, r := range recentRuns {
			risks = append(risks, RiskItem{
				Title:    r.TaskName,
				Desc:     truncateString(r.ErrorMessage, 80),
				Time:     r.StartTime.Format("01-02 15:04"),
				Severity: "medium",
			})
		}
	}

	return risks
}

func formatTime(t string) string {
	if t == "" {
		return "--"
	}
	if parsed, err := time.Parse("2006-01-02T15:04:05", t); err == nil {
		return parsed.Format("15:04")
	}
	if parsed, err := time.Parse("2006-01-02 15:04:05", t); err == nil {
		return parsed.Format("15:04")
	}
	if len(t) >= 5 {
		return t[len(t)-5:]
	}
	return t
}

func truncateString(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen] + "..."
}

func joinStrings(slice []string, sep string) string {
	return strings.Join(slice, sep)
}
