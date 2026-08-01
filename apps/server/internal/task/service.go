package task

import (
	"fmt"
	"log"
	"strings"
	"sync"
	"time"

	"github.com/kingdee-sync/go/internal/config"
	"github.com/kingdee-sync/go/internal/db"
	"github.com/kingdee-sync/go/internal/syncengine"
)

// Task represents a sync task derived from form configuration.
type Task struct {
	// Basic fields
	TaskID      string `json:"task_id"`
	TaskName    string `json:"task_name"`
	FormName    string `json:"form_name"`
	TargetTable string `json:"target_table"`

	// Sync config
	SyncMode       string `json:"sync_mode"` // "incremental" or "complete"
	IncrementField string `json:"increment_field"`
	Schedule       string `json:"schedule"` // "按同步执行配置"

	// Status
	Status      string  `json:"status"` // "enabled", "paused", "failed", "running"
	LastRun     string  `json:"last_run"`
	SuccessRate string  `json:"success_rate"`
	RecordCount int     `json:"record_count"`
	DurationSec float64 `json:"duration_seconds"`

	// Metadata
	CreatedAt string `json:"created_at"`
	Creator   string `json:"creator"`
	UpdatedAt string `json:"updated_at"`

	// Error info
	LastErrorTime    string `json:"last_error_time,omitempty"`
	LastErrorMessage string `json:"last_error_message,omitempty"`
	ErrorCount       string `json:"error_count"` // "X/3" format

	// Runtime snapshot (optional)
	ProgressStage     string `json:"progress_stage,omitempty"`
	ProgressPercent   int    `json:"progress_percent,omitempty"`
	ProgressUpdatedAt string `json:"progress_updated_at,omitempty"`
}

// TaskStats holds summary statistics for the tasks page.
type TaskStats struct {
	EnabledCount  int `json:"enabled_count"`
	PausedCount   int `json:"paused_count"`
	TodayExecuted int `json:"today_executed"`
	FailedToRetry int `json:"failed_to_retry"`
}

// Service manages task operations.
type Service struct {
	mu                   sync.RWMutex
	engine               *syncengine.SyncEngine
	runtimeSnapshots     map[string]*Task // task_id -> runtime snapshot
	defaultForms         map[string]bool  // enabled forms
	lastHistoryCache     []HistoryRecord
	lastHistoryCacheTime time.Time
}

// HistoryRecord represents a single sync history entry.
type HistoryRecord struct {
	RunID         string  `db:"run_id" json:"run_id"`
	FormName      string  `db:"form_name" json:"form_name"`
	SyncType      string  `db:"sync_type" json:"sync_type"`
	Status        string  `db:"status" json:"status"`
	RecordCount   int     `db:"record_count" json:"record_count"`
	DurationSec   float64 `db:"duration_seconds" json:"duration_seconds"`
	StartTime     string  `db:"start_time" json:"start_time"`
	EndTime       string  `db:"end_time" json:"end_time"`
	Message       string  `db:"message" json:"message"`
	LastErrorTime string  `db:"last_error_time" json:"last_error_time,omitempty"`
	LastErrorMsg  string  `db:"last_error_message" json:"last_error_message,omitempty"`
}

var instance *Service

func NewService(engine *syncengine.SyncEngine) *Service {
	if instance != nil {
		return instance
	}
	instance = &Service{
		engine:           engine,
		runtimeSnapshots: make(map[string]*Task),
		defaultForms:     loadDefaultForms(),
	}
	return instance
}

func GetService() *Service {
	return instance
}

// loadDefaultForms reads enabled forms from sync config.
func loadDefaultForms() map[string]bool {
	cfg := config.Get()
	if cfg == nil {
		return make(map[string]bool)
	}
	// default_forms is stored in SYNC section as comma-separated list
	// We'll parse it from the INI file directly via config accessors if available
	// For now, consider all forms in table_mapping as enabled
	result := make(map[string]bool)
	for formName := range getAllFormTableMapping() {
		result[formName] = true
	}
	return result
}

// getAllFormTableMapping returns all form-to-table mappings by reading form queries config.
// config.FormToTableName is a function, so we derive the mapping from form-queries.json.
func getAllFormTableMapping() map[string]string {
	cfg := config.Get()
	if cfg == nil || cfg.FormQueries == nil {
		return make(map[string]string)
	}
	result := make(map[string]string)
	for formName := range cfg.FormQueries {
		result[formName] = config.FormToTableName(formName)
	}
	return result
}

// GetTasks returns all tasks with optional filtering.
func (s *Service) GetTasks(filters map[string]string, page, pageSize int) ([]Task, int, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if page <= 0 {
		page = 1
	}
	if pageSize <= 0 || pageSize > 100 {
		pageSize = 50
	}

	tasks := s.buildTasks()

	// Apply filters
	var filtered []Task
	for _, t := range tasks {
		if !matchesFilters(t, filters) {
			continue
		}
		filtered = append(filtered, t)
	}

	total := len(filtered)

	// Pagination
	start := (page - 1) * pageSize
	if start >= total {
		return []Task{}, total, nil
	}
	end := start + pageSize
	if end > total {
		end = total
	}

	return filtered[start:end], total, nil
}

// GetTaskByID returns a single task by its ID.
func (s *Service) GetTaskByID(taskID string) (*Task, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	tasks := s.buildTasks()
	for _, t := range tasks {
		if t.TaskID == taskID {
			return &t, nil
		}
	}
	return nil, fmt.Errorf("task not found: %s", taskID)
}

// GetTaskStats returns summary statistics.
func (s *Service) GetTaskStats() TaskStats {
	s.mu.RLock()
	defer s.mu.RUnlock()

	tasks := s.buildTasks()
	stats := TaskStats{}

	now := time.Now()
	todayStart := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, now.Location())

	for _, t := range tasks {
		switch t.Status {
		case "enabled", "running":
			stats.EnabledCount++
		case "paused":
			stats.PausedCount++
		case "failed":
			stats.FailedToRetry++
		}

		// Count today executions
		if t.LastRun != "" {
			if t, err := time.Parse("2006-01-02T15:04:05", t.LastRun); err == nil && !t.Before(todayStart) {
				stats.TodayExecuted++
			}
		}
	}

	return stats
}

// EnableTask enables a task by adding its form to default_forms.
func (s *Service) EnableTask(taskID string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	tasks := s.buildTasks()
	var target *Task
	for i := range tasks {
		if tasks[i].TaskID == taskID {
			target = &tasks[i]
			break
		}
	}
	if target == nil {
		return fmt.Errorf("task not found: %s", taskID)
	}

	s.defaultForms[target.FormName] = true
	log.Printf("[TASK] Enabled task: %s (form: %s)", taskID, target.FormName)
	return nil
}

// PauseTask pauses a task by removing its form from default_forms.
func (s *Service) PauseTask(taskID string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	tasks := s.buildTasks()
	var target *Task
	for i := range tasks {
		if tasks[i].TaskID == taskID {
			target = &tasks[i]
			break
		}
	}
	if target == nil {
		return fmt.Errorf("task not found: %s", taskID)
	}

	delete(s.defaultForms, target.FormName)
	log.Printf("[TASK] Paused task: %s (form: %s)", taskID, target.FormName)
	return nil
}

// RunTask triggers a sync for a single task's form.
func (s *Service) RunTask(taskID string, syncType string) error {
	s.mu.RLock()
	tasks := s.buildTasks()
	var target *Task
	for i := range tasks {
		if tasks[i].TaskID == taskID {
			target = &tasks[i]
			break
		}
	}
	s.mu.RUnlock()

	if target == nil {
		return fmt.Errorf("task not found: %s", taskID)
	}

	if syncType == "" {
		syncType = "incremental"
	}

	log.Printf("[TASK] Running task: %s (form: %s, type: %s)", taskID, target.FormName, syncType)

	// Mark as running
	s.mu.Lock()
	s.runtimeSnapshots[target.TaskID] = &Task{
		TaskID:          target.TaskID,
		Status:          "running",
		ProgressStage:   "starting",
		ProgressPercent: 0,
	}
	s.mu.Unlock()

	// Trigger sync
	go func() {
		syncTypeFinal := syncType
		forms := []string{target.FormName}
		_, err := s.engine.SyncData(nil, forms, syncTypeFinal, false)
		s.mu.Lock()
		delete(s.runtimeSnapshots, target.TaskID)
		s.mu.Unlock()
		if err != nil {
			log.Printf("[TASK] Task %s failed: %v", taskID, err)
		}
	}()

	return nil
}

// BatchEnable enables multiple tasks.
func (s *Service) BatchEnable(taskIDs []string) (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	tasks := s.buildTasks()
	count := 0
	for _, id := range taskIDs {
		for _, t := range tasks {
			if t.TaskID == id {
				s.defaultForms[t.FormName] = true
				count++
				break
			}
		}
	}
	log.Printf("[TASK] Batch enabled %d tasks", count)
	return count, nil
}

// BatchPause pauses multiple tasks.
func (s *Service) BatchPause(taskIDs []string) (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	tasks := s.buildTasks()
	count := 0
	for _, id := range taskIDs {
		for _, t := range tasks {
			if t.TaskID == id {
				delete(s.defaultForms, t.FormName)
				count++
				break
			}
		}
	}
	log.Printf("[TASK] Batch paused %d tasks", count)
	return count, nil
}

// BatchRun runs multiple tasks sequentially.
func (s *Service) BatchRun(taskIDs []string, syncType string) error {
	if syncType == "" {
		syncType = "incremental"
	}

	s.mu.RLock()
	tasks := s.buildTasks()
	var forms []string
	for _, id := range taskIDs {
		for _, t := range tasks {
			if t.TaskID == id {
				forms = append(forms, t.FormName)
				break
			}
		}
	}
	s.mu.RUnlock()

	if len(forms) == 0 {
		return fmt.Errorf("no valid tasks found")
	}

	log.Printf("[TASK] Batch running %d tasks: %v", len(forms), forms)

	_, err := s.engine.SyncData(nil, forms, syncType, false)
	return err
}

// buildTasks constructs the task list from config and history.
func (s *Service) buildTasks() []Task {
	tableMapping := getAllFormTableMapping()

	history := s.getHistoryCache()
	historyByForm := buildHistoryByForm(history)

	var tasks []Task
	for formName, tableName := range tableMapping {
		taskID := fmt.Sprintf("task_%s", strings.ToLower(strings.ReplaceAll(formName, " ", "")))

		// Check runtime snapshot first
		snapshot, hasSnapshot := s.runtimeSnapshots[taskID]
		if hasSnapshot {
			t := Task{
				TaskID:            taskID,
				TaskName:          formName + "同步",
				FormName:          formName,
				TargetTable:       tableName,
				SyncMode:          "增量同步",
				IncrementField:    config.GetIncrementField(tableName, formName),
				Schedule:          "按同步执行配置",
				Status:            snapshot.Status,
				ProgressStage:     snapshot.ProgressStage,
				ProgressPercent:   snapshot.ProgressPercent,
				ProgressUpdatedAt: time.Now().Format("2006-01-02T15:04:05"),
				Creator:           "配置文件",
			}
			// Merge history info
			if h, ok := historyByForm[formName]; ok {
				t.LastRun = formatTime(h[0].StartTime)
				t.RecordCount = h[0].RecordCount
				t.DurationSec = h[0].DurationSec
				t.SuccessRate = calcSuccessRate(h)
			}
			tasks = append(tasks, t)
			continue
		}

		// Determine status
		status := "enabled"
		if !s.defaultForms[formName] {
			status = "paused"
		}

		t := Task{
			TaskID:         taskID,
			TaskName:       formName + "同步",
			FormName:       formName,
			TargetTable:    tableName,
			SyncMode:       "增量同步",
			IncrementField: config.GetIncrementField(tableName, formName),
			Schedule:       "按同步执行配置",
			Status:         status,
			Creator:        "配置文件",
			ErrorCount:     "0/3",
		}

		// Merge history info
		if h, ok := historyByForm[formName]; ok {
			t.LastRun = formatTime(h[0].StartTime)
			t.RecordCount = h[0].RecordCount
			t.DurationSec = h[0].DurationSec
			t.SuccessRate = calcSuccessRate(h)
			if h[0].Status == "failed" || h[0].Status == "failed_abnormal_exit" {
				t.Status = "failed"
				t.LastErrorTime = formatTime(h[0].StartTime)
				t.LastErrorMessage = truncateString(h[0].Message, 100)
				t.ErrorCount = fmt.Sprintf("1/3")
			}
		}

		tasks = append(tasks, t)
	}

	return tasks
}

// getHistoryCache returns recent history, cached for 30 seconds.
func (s *Service) getHistoryCache() []HistoryRecord {
	now := time.Now()
	if s.lastHistoryCacheTime.Add(30 * time.Second).After(now) {
		return s.lastHistoryCache
	}

	records := fetchHistoryFromDB(50)
	s.lastHistoryCache = records
	s.lastHistoryCacheTime = now
	return records
}

// fetchHistoryFromDB queries sync history from the database.
func fetchHistoryFromDB(limit int) []HistoryRecord {
	if db.DB == nil {
		return []HistoryRecord{}
	}

	var records []HistoryRecord
	query := `
		SELECT TOP (?) run_id, form_name, sync_type, status, record_count,
		       duration_seconds, start_time, end_time, message
		FROM sync_logs
		ORDER BY start_time DESC
	`
	rows, err := db.DB.Queryx(query, limit)
	if err != nil {
		log.Printf("[TASK] Failed to fetch history: %v", err)
		return []HistoryRecord{}
	}
	defer rows.Close()

	for rows.Next() {
		var r HistoryRecord
		if err := rows.StructScan(&r); err != nil {
			log.Printf("[TASK] Failed to scan history row: %v", err)
			continue
		}
		records = append(records, r)
	}

	// Also try sync_runs table if sync_logs is empty
	if len(records) == 0 {
		queryRuns := `
			SELECT TOP (?) run_id, forms, sync_type, status, total_records,
			       duration_seconds, start_time, end_time, message
			FROM sync_runs
			ORDER BY start_time DESC
		`
		type RunRecord struct {
			RunID        string  `db:"run_id"`
			Forms        string  `db:"forms"`
			SyncType     string  `db:"sync_type"`
			Status       string  `db:"status"`
			TotalRecords int     `db:"total_records"`
			DurationSec  float64 `db:"duration_seconds"`
			StartTime    string  `db:"start_time"`
			EndTime      string  `db:"end_time"`
			Message      string  `db:"message"`
		}
		rows2, err := db.DB.Queryx(queryRuns, limit)
		if err != nil {
			return []HistoryRecord{}
		}
		defer rows2.Close()

		for rows2.Next() {
			var r RunRecord
			if err := rows2.StructScan(&r); err != nil {
				continue
			}
			// Parse forms (stored as JSON array string)
			formNames := parseFormsString(r.Forms)
			for _, fn := range formNames {
				records = append(records, HistoryRecord{
					RunID:       r.RunID,
					FormName:    fn,
					SyncType:    r.SyncType,
					Status:      r.Status,
					RecordCount: r.TotalRecords / max(len(formNames), 1),
					DurationSec: r.DurationSec,
					StartTime:   r.StartTime,
					EndTime:     r.EndTime,
					Message:     r.Message,
				})
			}
		}
	}

	return records
}

// parseFormsString parses a JSON array string like '["form1","form2"]' into a slice.
func parseFormsString(s string) []string {
	s = strings.TrimSpace(s)
	if len(s) < 2 || s[0] != '[' || s[len(s)-1] != ']' {
		return []string{s}
	}
	s = s[1 : len(s)-1]
	parts := strings.Split(s, ",")
	var result []string
	for _, p := range parts {
		p = strings.TrimSpace(p)
		p = strings.Trim(p, "\"")
		if p != "" {
			result = append(result, p)
		}
	}
	return result
}

// buildHistoryByForm groups history records by form name.
func buildHistoryByForm(records []HistoryRecord) map[string][]HistoryRecord {
	result := make(map[string][]HistoryRecord)
	for _, r := range records {
		result[r.FormName] = append(result[r.FormName], r)
	}
	return result
}

// calcSuccessRate calculates success rate from history records.
func calcSuccessRate(records []HistoryRecord) string {
	if len(records) == 0 {
		return "--"
	}
	success := 0
	for _, r := range records {
		if r.Status == "success" {
			success++
		}
	}
	rate := float64(success) / float64(len(records)) * 100
	if rate == 100 {
		return "100%"
	}
	if rate == 0 {
		return "0%"
	}
	return fmt.Sprintf("%.0f%%", rate)
}

// formatTime formats a time string for display.
func formatTime(t string) string {
	if t == "" {
		return "--"
	}
	// Try parsing ISO format
	if parsed, err := time.Parse("2006-01-02T15:04:05", t); err == nil {
		return parsed.Format("2006-01-02 15:04:05")
	}
	// Try parsing datetime format
	if parsed, err := time.Parse("2006-01-02 15:04:05", t); err == nil {
		return parsed.Format("2006-01-02 15:04:05")
	}
	// Return as-is, truncated
	if len(t) > 19 {
		return t[:19]
	}
	return t
}

// truncateString truncates a string to maxLen characters.
func truncateString(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen] + "..."
}

// matchesFilters checks if a task matches the given filters.
func matchesFilters(t Task, filters map[string]string) bool {
	// Status filter
	if status, ok := filters["status"]; ok && status != "" {
		if t.Status != status {
			return false
		}
	}

	// Search filter (keyword)
	if keyword, ok := filters["search"]; ok && keyword != "" {
		keywordLower := strings.ToLower(keyword)
		searchFields := []string{t.TaskName, t.FormName, t.TargetTable}
		matched := false
		for _, field := range searchFields {
			if strings.Contains(strings.ToLower(field), keywordLower) {
				matched = true
				break
			}
		}
		if !matched {
			return false
		}
	}

	return true
}
