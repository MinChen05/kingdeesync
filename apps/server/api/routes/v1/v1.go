// Package v1 defines the v1 REST API contract and response writers.
//
// All v1 endpoints return a JSON envelope:
//
//	{"data": T}                          — success
//	{"data": T, "meta": PageMeta}        — paginated success
//	{"error": {"code": "...", "message": "..."}} — problem
package v1

// Envelope wraps a successful response payload.
type Envelope[T any] struct {
	Data T         `json:"data"`
	Meta *PageMeta `json:"meta,omitempty"`
}

// PageMeta carries pagination information.
type PageMeta struct {
	Page     int `json:"page"`
	PageSize int `json:"page_size"`
	Total    int `json:"total"`
}

// Problem describes a structured error response.
type Problem struct {
	Code    string `json:"code"`
	Message string `json:"message"`
	Details any    `json:"details,omitempty"`
}

// --- v1 DTOs ---

// Run is the v1 representation of a sync run.
type Run struct {
	RunID          string     `json:"run_id"`
	Status         string     `json:"status"`
	SyncType       string     `json:"sync_type"`
	StartedAt      string     `json:"started_at,omitempty"`
	FinishedAt     string     `json:"finished_at,omitempty"`
	DurationSec    float64    `json:"duration_seconds"`
	TotalRecords   int        `json:"total_records"`
	SuccessRecords int        `json:"success_records"`
	FailedRecords  int        `json:"failed_records"`
	FormCount      int        `json:"form_count"`
	SuccessForms   int        `json:"success_forms"`
	FailedForms    int        `json:"failed_forms"`
	ErrorMessage   string     `json:"error_message,omitempty"`
	Forms          []RunForm  `json:"forms,omitempty"`
	Errors         []RunError `json:"errors,omitempty"`
}

// RunForm is the per-form result within a sync run.
type RunForm struct {
	FormName     string  `json:"form_name"`
	Status       string  `json:"status"`
	TotalRecords int64   `json:"total_records"`
	Inserted     int64   `json:"inserted"`
	Updated      int64   `json:"updated"`
	Deleted      int64   `json:"deleted"`
	Failed       int64   `json:"failed"`
	Skipped      int64   `json:"skipped"`
	DurationSec  float64 `json:"duration_seconds"`
	ErrorMessage string  `json:"error_message,omitempty"`
}

// RunError is an error entry within a sync run.
type RunError struct {
	FormName  string `json:"form_name"`
	Level     string `json:"level"`
	Message   string `json:"message"`
	Detail    string `json:"detail,omitempty"`
	CreatedAt string `json:"created_at"`
}

// RunEvent is a redacted log entry for a run.
type RunEvent struct {
	CreatedAt string `json:"created_at"`
	FormName  string `json:"form_name"`
	Level     string `json:"level"`
	Message   string `json:"message"`
}

// Overview is the aggregated read model for the overview page.
type Overview struct {
	Today      TodayStats   `json:"today"`
	Health     HealthStatus `json:"health"`
	ActiveRun  *Run         `json:"active_run,omitempty"`
	Trend      []TrendDay   `json:"trend"`
	Risks      []RiskItem   `json:"risks"`
	RecentRuns []Run        `json:"recent_runs"`
}

// TodayStats holds today's sync summary.
type TodayStats struct {
	SyncCount      int     `json:"sync_count"`
	SuccessRate    float64 `json:"success_rate"`
	FailCount      int     `json:"fail_count"`
	AvgDurationSec float64 `json:"avg_duration"`
	LastSyncTime   string  `json:"last_sync_time,omitempty"`
	YesterdayCount int     `json:"yesterday_sync_count"`
	YesterdayRate  float64 `json:"yesterday_success_rate"`
}

// HealthStatus describes the health of each backend service.
type HealthStatus struct {
	KingdeeAPI *HealthItem `json:"kingdee_api"`
	Database   *HealthItem `json:"database"`
	Scheduler  *HealthItem `json:"scheduler"`
	LogService *HealthItem `json:"log_service"`
}

// HealthItem is a single health check result.
type HealthItem struct {
	Status     string `json:"status"`
	ResponseMs *int   `json:"response_ms,omitempty"`
	TodayCalls *int   `json:"today_calls,omitempty"`
	ConnCount  *int   `json:"conn_count,omitempty"`
	Uptime     string `json:"uptime,omitempty"`
	NextExec   string `json:"next_exec,omitempty"`
	WriteSpeed string `json:"write_speed,omitempty"`
	LogSize    string `json:"log_size,omitempty"`
}

// TrendDay is a single day in the 7-day trend.
type TrendDay struct {
	Date        string  `json:"date"`
	SyncCount   int     `json:"sync_count"`
	Records     int     `json:"records"`
	SuccessRate float64 `json:"success_rate"`
}

// RiskItem is a top-error form for the risk section.
type RiskItem struct {
	FormName     string `json:"form_name"`
	FailureCount int    `json:"failure_count"`
	LastError    string `json:"last_error,omitempty"`
}

// Schedule represents a cron job definition.
type Schedule struct {
	ID         int    `json:"id"`
	Name       string `json:"name"`
	CronExpr   string `json:"cron_expr"`
	SyncType   string `json:"sync_type"`
	Forms      string `json:"forms"`
	Enabled    bool   `json:"enabled"`
	CreatedAt  string `json:"created_at,omitempty"`
	UpdatedAt  string `json:"updated_at,omitempty"`
	LastRunAt  string `json:"last_run_at,omitempty"`
	NextRunAt  string `json:"next_run_at,omitempty"`
	LastStatus string `json:"last_status,omitempty"`
}

// SchedulerStatus is the current state of the scheduler.
type SchedulerStatus struct {
	Enabled bool `json:"enabled"`
}

// Form represents a configured form for sync.
type Form struct {
	FormName      string                 `json:"form_name"`
	Enabled       bool                   `json:"enabled"`
	LastSync      string                 `json:"last_sync_time,omitempty"`
	LastStatus    string                 `json:"last_status,omitempty"`
	RecordCount   int                    `json:"record_count"`
	ErrorCount    int                    `json:"error_count"`
	FormID        string                 `json:"form_id,omitempty"`
	FieldKeys     string                 `json:"field_keys,omitempty"`
	FilterString  string                 `json:"filter_string,omitempty"`
	FieldMap      map[string]string      `json:"field_map,omitempty"`
	DefaultValues map[string]interface{} `json:"default_values,omitempty"`
}

// DataSource represents a backend data source.
type DataSource struct {
	ID      string         `json:"id"`
	Name    string         `json:"name"`
	Type    string         `json:"type"`
	Status  string         `json:"status"`
	Latency string         `json:"latency,omitempty"`
	Config  map[string]any `json:"config,omitempty"`
}

// Diagnostics is the combined diagnostic info.
type Diagnostics struct {
	KingdeeAPI DiagService `json:"kingdee_api"`
	Database   DiagService `json:"database"`
	Scheduler  DiagService `json:"scheduler"`
	LogService DiagService `json:"log_service"`
}

// DiagService is a single diagnostic service result.
type DiagService struct {
	Status     string `json:"status"`
	ResponseMs *int   `json:"response_ms,omitempty"`
}

// SystemConfig is the current system configuration (passwords masked).
type SystemConfig map[string]any
