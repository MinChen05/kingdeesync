package gormdb

import (
	"time"

	"gorm.io/gorm"
)

// SyncRun represents a sync execution run.
type SyncRun struct {
	ID              uint           `gorm:"primaryKey" json:"id"`
	RunID           string         `gorm:"type:varchar(64);uniqueIndex;not null" json:"run_id"`
	ParentRunID     string         `gorm:"type:varchar(64);index" json:"parent_run_id,omitempty"`
	TaskName        string         `gorm:"type:varchar(255)" json:"task_name"`
	SyncType        string         `gorm:"type:varchar(32);not null" json:"sync_type"`    // incremental, full, reset
	Status          string         `gorm:"type:varchar(32);not null;index" json:"status"` // running, stopping, success, partial, failed, stopped, failed_abnormal_exit
	StartTime       time.Time      `gorm:"type:DATETIME;not null;index" json:"start_time"`
	EndTime         *time.Time     `gorm:"type:DATETIME" json:"end_time,omitempty"`
	LastHeartbeat   time.Time      `gorm:"type:DATETIME;not null;index" json:"last_heartbeat"`
	DurationSeconds float64        `gorm:"type:REAL" json:"duration_seconds,omitempty"`
	TotalRecords    int64          `gorm:"not null;default:0" json:"total_records"`
	SuccessRecords  int64          `gorm:"not null;default:0" json:"success_records"`
	FailedRecords   int64          `gorm:"not null;default:0" json:"failed_records"`
	SkippedRecords  int64          `gorm:"not null;default:0" json:"skipped_records"`
	FormCount       int            `gorm:"not null;default:0" json:"form_count"`
	SuccessForms    int            `gorm:"not null;default:0" json:"success_forms"`
	FailedForms     int            `gorm:"not null;default:0" json:"failed_forms"`
	ErrorMessage    string         `gorm:"type:text" json:"error_message,omitempty"`
	CreatedAt       time.Time      `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt       time.Time      `gorm:"autoUpdateTime" json:"updated_at"`
	DeletedAt       gorm.DeletedAt `gorm:"index" json:"-"`

	// Relations
	Forms  []SyncRunForm `gorm:"foreignKey:RunID;references:RunID" json:"forms,omitempty"`
	Errors []SyncError   `gorm:"foreignKey:RunID;references:RunID" json:"errors,omitempty"`
}

// SyncRunForm represents the sync result for a single form within a run.
type SyncRunForm struct {
	ID              uint           `gorm:"primaryKey" json:"id"`
	RunID           string         `gorm:"type:varchar(64);not null;index:idx_run_form,unique" json:"run_id"`
	FormName        string         `gorm:"type:varchar(128);not null;index:idx_run_form,unique" json:"form_name"`
	Status          string         `gorm:"type:varchar(32);not null" json:"status"` // success, failed, skipped, partial
	TotalRecords    int64          `gorm:"not null;default:0" json:"total_records"`
	Inserted        int64          `gorm:"not null;default:0" json:"inserted"`
	Updated         int64          `gorm:"not null;default:0" json:"updated"`
	Deleted         int64          `gorm:"not null;default:0" json:"deleted"`
	Failed          int64          `gorm:"not null;default:0" json:"failed"`
	Skipped         int64          `gorm:"not null;default:0" json:"skipped"`
	StartTime       *time.Time     `gorm:"type:DATETIME" json:"start_time,omitempty"`
	EndTime         *time.Time     `gorm:"type:DATETIME" json:"end_time,omitempty"`
	DurationSeconds float64        `gorm:"type:REAL" json:"duration_seconds,omitempty"`
	ErrorMessage    string         `gorm:"type:text" json:"error_message,omitempty"`
	CreatedAt       time.Time      `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt       time.Time      `gorm:"autoUpdateTime" json:"updated_at"`
	DeletedAt       gorm.DeletedAt `gorm:"index" json:"-"`
}

// SyncError represents an error that occurred during sync.
type SyncError struct {
	ID        uint      `gorm:"primaryKey" json:"id"`
	RunID     string    `gorm:"type:varchar(64);not null;index" json:"run_id"`
	FormName  string    `gorm:"type:varchar(128);not null;index" json:"form_name"`
	Level     string    `gorm:"type:varchar(16);not null;index" json:"level"` // error, warning, info
	Message   string    `gorm:"type:text;not null" json:"message"`
	Detail    string    `gorm:"type:text" json:"detail,omitempty"`
	CreatedAt time.Time `gorm:"autoCreateTime;index" json:"created_at"`
}

// ScheduleJob represents a scheduled sync job.
type ScheduleJob struct {
	ID         uint       `gorm:"primaryKey" json:"id"`
	Name       string     `gorm:"type:varchar(128);uniqueIndex;not null" json:"name"`
	CronExpr   string     `gorm:"type:varchar(64);not null" json:"cron_expr"`
	SyncType   string     `gorm:"type:varchar(32);not null" json:"sync_type"` // incremental, full
	Forms      string     `gorm:"type:text" json:"forms,omitempty"`           // JSON array of form names
	Enabled    bool       `gorm:"not null;default:true;index" json:"enabled"`
	LastRunAt  *time.Time `gorm:"type:DATETIME;index" json:"last_run_at,omitempty"`
	NextRunAt  *time.Time `gorm:"type:DATETIME" json:"next_run_at,omitempty"`
	LastStatus string     `gorm:"type:varchar(32)" json:"last_status,omitempty"`
	LastRunID  string     `gorm:"type:varchar(64)" json:"last_run_id,omitempty"`
	CreatedAt  time.Time  `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt  time.Time  `gorm:"autoUpdateTime" json:"updated_at"`

	// Relations
	Runs []ScheduleRun `gorm:"foreignKey:JobID" json:"runs,omitempty"`
}

// TableName methods to use "go_" prefix for all Go-managed tables
func (SyncRun) TableName() string     { return "go_sync_runs" }
func (SyncRunForm) TableName() string { return "go_sync_run_forms" }
func (SyncError) TableName() string   { return "go_sync_errors" }
func (ScheduleJob) TableName() string { return "go_schedule_jobs" }
func (ScheduleRun) TableName() string { return "go_schedule_runs" }
func (Checkpoint) TableName() string  { return "go_checkpoints" }

// ScheduleRun represents an execution of a scheduled job.
type ScheduleRun struct {
	ID           uint       `gorm:"primaryKey" json:"id"`
	JobID        uint       `gorm:"not null;index" json:"job_id"`
	RunID        string     `gorm:"type:varchar(64);uniqueIndex;not null" json:"run_id"`
	Status       string     `gorm:"type:varchar(32);not null;index" json:"status"` // running, success, failed
	StartTime    time.Time  `gorm:"type:DATETIME;not null;index" json:"start_time"`
	EndTime      *time.Time `gorm:"type:DATETIME" json:"end_time,omitempty"`
	ErrorMessage string     `gorm:"type:text" json:"error_message,omitempty"`
	CreatedAt    time.Time  `gorm:"autoCreateTime" json:"created_at"`
}

// Checkpoint represents a sync checkpoint for large tables (断点续传).
type Checkpoint struct {
	ID           uint      `gorm:"primaryKey" json:"id"`
	FormName     string    `gorm:"type:varchar(128);uniqueIndex;not null" json:"form_name"`
	RunID        string    `gorm:"type:varchar(64);index" json:"run_id,omitempty"`
	LastPosition int64     `gorm:"not null;default:0" json:"last_position"`          // StartRow where sync left off
	LastSyncTime string    `gorm:"type:varchar(64)" json:"last_sync_time,omitempty"` // Last successful sync timestamp from Kingdee
	UpdatedAt    time.Time `gorm:"autoUpdateTime;index" json:"updated_at"`
}

// SnapshotMeta tracks per-form snapshot metadata for full-sync validation.
type SnapshotMeta struct {
	ID            uint      `gorm:"primaryKey" json:"id"`
	SnapshotID    string    `gorm:"type:varchar(64);uniqueIndex:idx_snapshot_form,unique;not null" json:"snapshot_id"`
	RunID         string    `gorm:"type:varchar(64);not null;index" json:"run_id"`
	FormName      string    `gorm:"type:varchar(128);not null;index:idx_snapshot_form,unique;index" json:"form_name"`
	TargetTable   string    `gorm:"column:table_name;type:varchar(128);not null" json:"table_name"`
	Status        string    `gorm:"type:varchar(32);not null;default:writing;index" json:"status"` // writing, validated, reconciled, aborted
	FetchedCount  int64     `gorm:"not null;default:0" json:"fetched_count"`
	WrittenCount  int64     `gorm:"not null;default:0" json:"written_count"`
	DeletedCount  int64     `gorm:"not null;default:0" json:"deleted_count"`
	PkCount       int64     `gorm:"not null;default:0" json:"pk_count"`        // distinct PK count from source
	DbCountBefore int64     `gorm:"not null;default:0" json:"db_count_before"` // rows in DB before snapshot
	DbCountAfter  int64     `gorm:"not null;default:0" json:"db_count_after"`  // rows in DB after snapshot
	ErrorReason   string    `gorm:"type:text" json:"error_reason,omitempty"`
	CreatedAt     time.Time `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt     time.Time `gorm:"autoUpdateTime" json:"updated_at"`
}

func (SnapshotMeta) TableName() string { return "go_snapshot_meta" }

// OrphanDeleteApproval is a one-time local approval bound to one immutable snapshot.
type OrphanDeleteApproval struct {
	ID                  uint       `gorm:"primaryKey" json:"id"`
	SnapshotID          string     `gorm:"type:varchar(64);not null;uniqueIndex:idx_orphan_approval" json:"snapshot_id"`
	TargetTable         string     `gorm:"type:varchar(128);not null;uniqueIndex:idx_orphan_approval" json:"target_table"`
	SnapshotHash        string     `gorm:"type:char(64);not null;uniqueIndex:idx_orphan_approval" json:"snapshot_hash"`
	ExpectedOrphanCount int64      `gorm:"not null" json:"expected_orphan_count"`
	Approver            string     `gorm:"type:varchar(128);not null" json:"approver"`
	Reason              string     `gorm:"type:text;not null" json:"reason"`
	UsedAt              *time.Time `gorm:"index" json:"used_at,omitempty"`
	CreatedAt           time.Time  `gorm:"autoCreateTime" json:"created_at"`
}

func (OrphanDeleteApproval) TableName() string { return "go_orphan_delete_approvals" }

// FormSetting stores per-form override settings (e.g. enabled/disabled).
type FormSetting struct {
	ID        uint      `gorm:"primaryKey" json:"id"`
	FormName  string    `gorm:"type:varchar(128);uniqueIndex;not null" json:"form_name"`
	Enabled   bool      `gorm:"not null;default:true" json:"enabled"`
	UpdatedAt time.Time `gorm:"autoUpdateTime" json:"updated_at"`
}

func (FormSetting) TableName() string { return "go_form_settings" }

// FormQueryConfig stores the Kingdee form query configuration (migrated from form-queries.json).
type FormQueryConfig struct {
	ID            uint      `gorm:"primaryKey" json:"id"`
	FormName      string    `gorm:"type:varchar(128);uniqueIndex;not null" json:"form_name"`
	FormID        string    `gorm:"type:varchar(128)" json:"form_id"`
	FieldKeys     string    `gorm:"type:text" json:"field_keys"`
	FilterString  string    `gorm:"type:text" json:"filter_string"`
	FieldMap      string    `gorm:"type:text" json:"field_map"`      // JSON map[string]string
	DefaultValues string    `gorm:"type:text" json:"default_values"` // JSON map[string]interface{}
	CreatedAt     time.Time `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt     time.Time `gorm:"autoUpdateTime" json:"updated_at"`
}

func (FormQueryConfig) TableName() string { return "go_form_queries" }
