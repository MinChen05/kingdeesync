package contract

import "time"

// SyncStatus is the public state machine for a sync run.
type SyncStatus string

const (
	StatusRunning            SyncStatus = "running"
	StatusStopping           SyncStatus = "stopping"
	StatusSuccess            SyncStatus = "success"
	StatusPartial            SyncStatus = "partial"
	StatusFailed             SyncStatus = "failed"
	StatusStopped            SyncStatus = "stopped"
	StatusFailedAbnormalExit SyncStatus = "failed_abnormal_exit"
)

var validStatuses = map[SyncStatus]struct{}{
	StatusRunning:            {},
	StatusStopping:           {},
	StatusSuccess:            {},
	StatusPartial:            {},
	StatusFailed:             {},
	StatusStopped:            {},
	StatusFailedAbnormalExit: {},
}

// IsValidStatus reports whether status is part of the public contract.
func IsValidStatus(status SyncStatus) bool {
	_, ok := validStatuses[status]
	return ok
}

// IsTerminalStatus reports whether a run cannot be changed by normal execution.
func IsTerminalStatus(status SyncStatus) bool {
	switch status {
	case StatusSuccess, StatusPartial, StatusFailed, StatusStopped, StatusFailedAbnormalExit:
		return true
	default:
		return false
	}
}

// CanTransition describes transitions that can be caused by a normal run.
// failed_abnormal_exit is deliberately excluded; only recovery may create it.
func CanTransition(from, to SyncStatus) bool {
	if from == to {
		return from == StatusRunning || from == StatusStopping
	}
	switch from {
	case StatusRunning:
		return to == StatusStopping || to == StatusSuccess || to == StatusPartial || to == StatusFailed
	case StatusStopping:
		return to == StatusStopped
	default:
		return false
	}
}

type SyncStartRequest struct {
	Forms    []string `json:"forms"`
	SyncType string   `json:"sync_type"`
	DryRun   *bool    `json:"dry_run"`
}

type SyncStartData struct {
	RunID  string `json:"run_id"`
	DryRun bool   `json:"dry_run"`
}

// SyncStopData is returned after a stop request has been accepted.
type SyncStopData struct {
	RunID  string     `json:"run_id"`
	Status SyncStatus `json:"status"`
}

// SyncLogEntry is one persisted log entry belonging to a synchronization run.
type SyncLogEntry struct {
	CreatedAt time.Time `json:"created_at"`
	FormName  string    `json:"form_name"`
	Level     string    `json:"level"`
	Message   string    `json:"message"`
	Detail    string    `json:"detail"`
}

// SyncLogsData is the successful response payload for one run's logs.
type SyncLogsData struct {
	RunID string         `json:"run_id"`
	Logs  []SyncLogEntry `json:"logs"`
}

type SyncFormStatus struct {
	FormName     string     `json:"form_name"`
	Fetched      int        `json:"fetched"`
	Inserted     int        `json:"inserted"`
	Errors       int        `json:"errors"`
	DurationSec  float64    `json:"duration_sec"`
	Status       SyncStatus `json:"status"`
	ErrorSummary string     `json:"error_summary,omitempty"`
}

type SyncStatusData struct {
	RunID          string           `json:"run_id"`
	Status         SyncStatus       `json:"status"`
	Progress       int              `json:"progress"`
	CurrentForm    string           `json:"current_form"`
	Message        string           `json:"message"`
	ErrorSummary   string           `json:"error_summary"`
	ElapsedSeconds float64          `json:"elapsed_seconds"`
	StartedAt      time.Time        `json:"started_at"`
	FormStats      []SyncFormStatus `json:"form_stats"`
}

type APIResponse struct {
	OK    bool        `json:"ok"`
	Data  interface{} `json:"data"`
	Error string      `json:"error"`
	Code  string      `json:"code"`
}

const (
	CodeSyncAlreadyRunning      = "SYNC_ALREADY_RUNNING"
	CodeSyncRunIDRequired       = "SYNC_RUN_ID_REQUIRED"
	CodeSyncNotFound            = "SYNC_NOT_FOUND"
	CodeSyncNotActive           = "SYNC_NOT_ACTIVE"
	CodeSyncInvalidRequest      = "SYNC_INVALID_REQUEST"
	CodeSyncDatabaseUnavailable = "SYNC_DATABASE_UNAVAILABLE"
	CodeSyncStartFailed         = "SYNC_START_FAILED"
	CodeSyncLogsFailed          = "SYNC_LOGS_FAILED"
)
