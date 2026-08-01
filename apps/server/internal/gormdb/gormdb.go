package gormdb

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"time"

	"github.com/glebarez/sqlite"
	"github.com/kingdee-sync/go/internal/api/contract"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

var DB *gorm.DB

func findConfigFile() (string, error) {
	candidates := []string{
		filepath.Join("..", "config.local.ini"),
		filepath.Join("..", "config.ini"),
		"config.local.ini",
		"config.ini",
	}
	for _, p := range candidates {
		if abs, err := filepath.Abs(p); err == nil {
			if _, err := os.Stat(abs); err == nil {
				return abs, nil
			}
		}
	}
	return "", fmt.Errorf("config file not found")
}

// Init initializes the GORM database for Go internal tables.
// Uses a local SQLite file for OLTP workloads (sync_runs, schedule_jobs, etc.).
// The business database (Doris/MySQL/SQLServer) is used only for data sync.
func Init() error {
	// Determine SQLite file path: always place next to config.local.ini (project root)
	// （原因：go run 的 exe 在临时目录，不能把 DB 放在那里，否则每次重启会丢失数据）
	sqlitePath := "go_state.db"
	if configPath, err := findConfigFile(); err == nil {
		dbDir := filepath.Dir(configPath)
		sqlitePath = filepath.Join(dbDir, "go_state.db")
	}
	// Resolve to absolute path to avoid cwd confusion
	if abs, err := filepath.Abs(sqlitePath); err == nil {
		sqlitePath = abs
	}

	dialector := sqlite.Open(sqlitePath + "?_journal_mode=WAL&_busy_timeout=5000")

	var err error
	DB, err = gorm.Open(dialector, &gorm.Config{
		Logger: logger.Default.LogMode(logger.Warn),
	})
	if err != nil {
		return fmt.Errorf("open gorm database (SQLite): %w", err)
	}

	sqlDB, err := DB.DB()
	if err != nil {
		return fmt.Errorf("get sql db: %w", err)
	}
	// SQLite-specific connection pool settings
	sqlDB.SetMaxOpenConns(1) // SQLite uses file-level locking
	sqlDB.SetMaxIdleConns(1)
	sqlDB.SetConnMaxLifetime(30 * time.Minute)

	log.Printf("[GORM] SQLite database initialized: %s", sqlitePath)
	return nil
}

// Close closes the GORM database connection.
func Close() {
	if DB != nil {
		sqlDB, _ := DB.DB()
		if sqlDB != nil {
			sqlDB.Close()
		}
	}
}

// AutoMigrate runs auto migration for all Go internal models.
func AutoMigrate() error {
	if DB == nil {
		return fmt.Errorf("gorm database not initialized")
	}

	return DB.AutoMigrate(
		&SyncRun{},
		&SyncRunForm{},
		&SyncError{},
		&ScheduleJob{},
		&ScheduleRun{},
		&Checkpoint{},
		&SnapshotMeta{},
		&OrphanDeleteApproval{},
		&FormSetting{},
		&FormQueryConfig{},
	)
}

func CreateOrphanDeleteApproval(approval *OrphanDeleteApproval) error {
	if DB == nil {
		return fmt.Errorf("gorm database not initialized")
	}
	if approval == nil || approval.SnapshotID == "" || approval.TargetTable == "" || len(approval.SnapshotHash) != 64 || approval.ExpectedOrphanCount < 0 || approval.Approver == "" || approval.Reason == "" {
		return fmt.Errorf("invalid orphan delete approval")
	}
	if err := DB.Create(approval).Error; err != nil {
		return fmt.Errorf("create orphan delete approval: %w", err)
	}
	return nil
}

func ConsumeOrphanDeleteApproval(snapshotID, targetTable, snapshotHash string, expectedCount int64) error {
	if DB == nil {
		return fmt.Errorf("gorm database not initialized")
	}
	return DB.Transaction(func(tx *gorm.DB) error {
		var approval OrphanDeleteApproval
		if err := tx.Where(
			"snapshot_id = ? AND target_table = ? AND snapshot_hash = ? AND expected_orphan_count = ? AND used_at IS NULL",
			snapshotID, targetTable, snapshotHash, expectedCount,
		).First(&approval).Error; err != nil {
			return fmt.Errorf("load unused orphan delete approval: %w", err)
		}
		now := time.Now()
		result := tx.Model(&OrphanDeleteApproval{}).Where("id = ? AND used_at IS NULL", approval.ID).Update("used_at", now)
		if result.Error != nil {
			return fmt.Errorf("consume orphan delete approval: %w", result.Error)
		}
		if result.RowsAffected != 1 {
			return fmt.Errorf("orphan delete approval already used")
		}
		return nil
	})
}

// CreateSyncRun creates a new sync run record.
func CreateSyncRun(runID, taskName, syncType string) (*SyncRun, error) {
	return createSyncRun(runID, "", taskName, syncType, "")
}

func createSyncRun(runID, parentRunID, taskName, syncType, errorMessage string) (*SyncRun, error) {
	if DB == nil {
		return nil, fmt.Errorf("gorm database not initialized")
	}
	if runID == "" {
		return nil, fmt.Errorf("run ID is required")
	}

	now := time.Now()
	run := &SyncRun{
		RunID:         runID,
		ParentRunID:   parentRunID,
		TaskName:      taskName,
		SyncType:      syncType,
		Status:        string(contract.StatusRunning),
		StartTime:     now,
		LastHeartbeat: now,
		ErrorMessage:  errorMessage,
	}

	if err := DB.Create(run).Error; err != nil {
		return nil, fmt.Errorf("create sync run: %w", err)
	}

	return run, nil
}

// CreateRecoverySyncRun creates a new running child for an abnormal run.
// The parent remains terminal; recovery never transitions it back to running.
func CreateRecoverySyncRun(runID, parentRunID, taskName, syncType, reason string, formCount int) (*SyncRun, error) {
	if DB == nil {
		return nil, fmt.Errorf("gorm database not initialized")
	}
	if parentRunID == "" {
		return nil, fmt.Errorf("parent run ID is required")
	}
	var parent SyncRun
	if err := DB.Where("run_id = ?", parentRunID).First(&parent).Error; err != nil {
		return nil, fmt.Errorf("load parent sync run %s: %w", parentRunID, err)
	}
	if parent.Status != string(contract.StatusFailedAbnormalExit) {
		return nil, fmt.Errorf("parent sync run %s is not failed_abnormal_exit", parentRunID)
	}
	run, err := createSyncRun(runID, parentRunID, taskName, syncType, reason)
	if err != nil {
		return nil, err
	}
	if formCount > 0 {
		if err := DB.Model(&SyncRun{}).Where("run_id = ?", runID).Update("form_count", formCount).Error; err != nil {
			return nil, fmt.Errorf("set recovery form count: %w", err)
		}
		run.FormCount = formCount
	}
	return run, nil
}

// GetSyncRun loads a run and its form-level records for API status queries.
func GetSyncRun(runID string) (*SyncRun, error) {
	return GetSyncRunContext(context.Background(), runID)
}

// GetSyncRunContext loads a run using the caller's cancellation context.
func GetSyncRunContext(ctx context.Context, runID string) (*SyncRun, error) {
	if DB == nil {
		return nil, fmt.Errorf("gorm database not initialized")
	}
	if ctx == nil {
		ctx = context.Background()
	}
	var run SyncRun
	if err := DB.WithContext(ctx).Preload("Forms").Preload("Errors").Where("run_id = ?", runID).First(&run).Error; err != nil {
		return nil, err
	}
	return &run, nil
}

// GetScheduleRun loads the durable state used as the source of truth for job summaries.
func GetScheduleRun(runID string) (*ScheduleRun, error) {
	if DB == nil {
		return nil, fmt.Errorf("gorm database not initialized")
	}
	var run ScheduleRun
	if err := DB.Where("run_id = ?", runID).First(&run).Error; err != nil {
		return nil, err
	}
	return &run, nil
}

// UpdateSyncRunStatus applies a normal state-machine transition.
// failed_abnormal_exit is intentionally available only through recovery.
func UpdateSyncRunStatus(runID string, status string, errorMessage string) error {
	if DB == nil {
		return fmt.Errorf("gorm database not initialized")
	}
	to := contract.SyncStatus(status)
	if !contract.IsValidStatus(to) || to == contract.StatusFailedAbnormalExit {
		return fmt.Errorf("invalid normal sync status %q", status)
	}
	allowedFrom := []string{}
	switch to {
	case contract.StatusRunning:
		allowedFrom = []string{string(contract.StatusRunning)}
	case contract.StatusStopping:
		allowedFrom = []string{string(contract.StatusRunning), string(contract.StatusStopping)}
	case contract.StatusStopped:
		allowedFrom = []string{string(contract.StatusStopping)}
	case contract.StatusSuccess, contract.StatusPartial, contract.StatusFailed:
		allowedFrom = []string{string(contract.StatusRunning)}
	default:
		return fmt.Errorf("invalid normal sync status %q", status)
	}
	updates := map[string]interface{}{"status": status}
	if errorMessage != "" {
		updates["error_message"] = errorMessage
	}
	result := DB.Model(&SyncRun{}).
		Where("run_id = ? AND status IN ?", runID, allowedFrom).
		Updates(updates)
	if result.Error != nil {
		return result.Error
	}
	if result.RowsAffected == 1 {
		return nil
	}
	return fmt.Errorf("sync run %s cannot transition to %q", runID, status)
}

// MarkSyncRunAbnormalExit atomically marks an active run abnormal after a timeout.
// It is intentionally separate from normal state transitions.
func MarkSyncRunAbnormalExit(runID, errorMessage string) error {
	if DB == nil {
		return fmt.Errorf("gorm database not initialized")
	}
	if errorMessage == "" {
		errorMessage = "abnormal exit: stop timeout exceeded"
	}
	result := DB.Model(&SyncRun{}).
		Where("run_id = ? AND status IN ?", runID, []string{string(contract.StatusRunning), string(contract.StatusStopping)}).
		Updates(map[string]interface{}{
			"status":        string(contract.StatusFailedAbnormalExit),
			"end_time":      time.Now(),
			"error_message": errorMessage,
		})
	if result.Error != nil {
		return result.Error
	}
	return nil
}

// MarkSyncRunAbnormalExitWithRetry retries the abnormal marker so a transient
// SQLite lock does not silently turn a terminal execution into a stale run.
func MarkSyncRunAbnormalExitWithRetry(runID, errorMessage string) error {
	return retryStateWrite("mark sync run abnormal", func() error {
		return MarkSyncRunAbnormalExit(runID, errorMessage)
	})
}

// UpdateSyncRunHeartbeat updates the heartbeat timestamp for a running sync.
func UpdateSyncRunHeartbeat(runID string) error {
	if DB == nil {
		return fmt.Errorf("gorm database not initialized")
	}

	return DB.Model(&SyncRun{}).
		Where("run_id = ? AND status = ?", runID, string(contract.StatusRunning)).
		Update("last_heartbeat", time.Now()).Error
}

// FinishSyncRun marks a sync run as completed.
func FinishSyncRun(runID string, status string, durationSec float64, totalRecords, successRecords, failedRecords int64, formCount, successForms, failedForms int, errorMsg string) error {
	if DB == nil {
		return fmt.Errorf("gorm database not initialized")
	}
	to := contract.SyncStatus(status)
	if !contract.IsValidStatus(to) || to == contract.StatusFailedAbnormalExit {
		return fmt.Errorf("invalid final sync status %q", status)
	}
	if to == contract.StatusStopping {
		return fmt.Errorf("stopping is not a final sync status")
	}

	return DB.Transaction(func(tx *gorm.DB) error {
		var run SyncRun
		if err := tx.Where("run_id = ?", runID).First(&run).Error; err != nil {
			return err
		}

		from := contract.SyncStatus(run.Status)
		if contract.IsTerminalStatus(from) {
			return nil
		}
		finalStatus := to
		if from == contract.StatusStopping && to != contract.StatusStopped {
			finalStatus = contract.StatusStopped
		}
		if !contract.CanTransition(from, finalStatus) {
			return fmt.Errorf("invalid sync status transition %q -> %q", run.Status, finalStatus)
		}

		now := time.Now()
		updates := map[string]interface{}{
			"status":           string(finalStatus),
			"end_time":         &now,
			"duration_seconds": durationSec,
			"total_records":    totalRecords,
			"success_records":  successRecords,
			"failed_records":   failedRecords,
			"form_count":       formCount,
			"success_forms":    successForms,
			"failed_forms":     failedForms,
		}
		if errorMsg != "" {
			updates["error_message"] = errorMsg
		}

		result := tx.Model(&SyncRun{}).
			Where("run_id = ? AND status = ?", runID, run.Status).
			Updates(updates)
		if result.Error != nil {
			return result.Error
		}
		if result.RowsAffected != 1 {
			return fmt.Errorf("sync run %s changed before finalization", runID)
		}
		return nil
	})
}

// FinishSyncRunWithRetry retries final state persistence and reports the
// failure to the caller after bounded attempts.
func FinishSyncRunWithRetry(runID string, status string, durationSec float64, totalRecords, successRecords, failedRecords int64, formCount, successForms, failedForms int, errorMsg string) error {
	return retryStateWrite("finish sync run", func() error {
		return FinishSyncRun(runID, status, durationSec, totalRecords, successRecords, failedRecords, formCount, successForms, failedForms, errorMsg)
	})
}

// FinishScheduleRun atomically finishes a schedule run that is still running.
// A prior timeout or recovery is terminal and therefore cannot be overwritten.
func FinishScheduleRun(runID, status, errorMessage string) error {
	if DB == nil {
		return fmt.Errorf("gorm database not initialized")
	}
	if status == "" {
		return fmt.Errorf("schedule run status is required")
	}
	now := time.Now()
	updates := map[string]interface{}{"status": status, "end_time": &now}
	if errorMessage != "" {
		updates["error_message"] = errorMessage
	}
	result := DB.Model(&ScheduleRun{}).
		Where("run_id = ? AND status = ?", runID, "running").
		Updates(updates)
	if result.Error != nil {
		return result.Error
	}
	return nil
}

// MarkScheduleRunAbnormalExit atomically closes a running schedule run after
// its watchdog deadline.
func MarkScheduleRunAbnormalExit(runID, errorMessage string) error {
	return FinishScheduleRun(runID, string(contract.StatusFailedAbnormalExit), errorMessage)
}

func FinishScheduleRunWithRetry(runID, status, errorMessage string) error {
	return retryStateWrite("finish schedule run", func() error {
		return FinishScheduleRun(runID, status, errorMessage)
	})
}

func MarkScheduleRunAbnormalExitWithRetry(runID, errorMessage string) error {
	return retryStateWrite("mark schedule run abnormal", func() error {
		return MarkScheduleRunAbnormalExit(runID, errorMessage)
	})
}

func retryStateWrite(operation string, write func() error) error {
	const attempts = 3
	var lastErr error
	for attempt := 1; attempt <= attempts; attempt++ {
		if err := write(); err == nil {
			return nil
		} else {
			lastErr = err
			log.Printf("[SYNC-STATE] %s failed attempt %d/%d: %v", operation, attempt, attempts, err)
		}
		if attempt < attempts {
			time.Sleep(10 * time.Millisecond)
		}
	}
	return fmt.Errorf("%s failed after retries: %w", operation, lastErr)
}

// RecoverAbnormalRuns marks stale running or stopping syncs as failed_abnormal_exit.
// heartbeatTimeout: max allowed time since last heartbeat (e.g., 5 minutes).
func RecoverAbnormalRuns(heartbeatTimeout time.Duration) (int, error) {
	if DB == nil {
		return 0, fmt.Errorf("gorm database not initialized")
	}

	cutoff := time.Now().Add(-heartbeatTimeout)
	result := DB.Model(&SyncRun{}).
		Where("status IN ? AND last_heartbeat < ?", []string{string(contract.StatusRunning), string(contract.StatusStopping)}, cutoff).
		Updates(map[string]interface{}{
			"status":        string(contract.StatusFailedAbnormalExit),
			"end_time":      time.Now(),
			"error_message": "abnormal exit: heartbeat timeout exceeded",
		})

	if result.Error != nil {
		return 0, fmt.Errorf("recover abnormal runs: %w", result.Error)
	}

	log.Printf("[RECOVERY] Recovered %d abnormal sync runs", result.RowsAffected)
	return int(result.RowsAffected), nil
}

// ListAbnormalSyncRuns returns terminal abnormal runs eligible for a recovery
// plan. The caller decides whether a checkpoint is valid for each form.
func ListAbnormalSyncRuns() ([]SyncRun, error) {
	if DB == nil {
		return nil, fmt.Errorf("gorm database not initialized")
	}
	var runs []SyncRun
	if err := DB.Preload("Forms").Where("status = ?", string(contract.StatusFailedAbnormalExit)).Order("start_time ASC").Find(&runs).Error; err != nil {
		return nil, fmt.Errorf("list abnormal sync runs: %w", err)
	}
	return runs, nil
}

func HasSuccessfulRecovery(parentRunID string) (bool, error) {
	if DB == nil {
		return false, fmt.Errorf("gorm database not initialized")
	}
	var count int64
	if err := DB.Model(&SyncRun{}).Where("parent_run_id = ? AND status = ?", parentRunID, string(contract.StatusSuccess)).Count(&count).Error; err != nil {
		return false, fmt.Errorf("check successful recovery for %s: %w", parentRunID, err)
	}
	return count > 0, nil
}

// GetCheckpoint retrieves the checkpoint for a form.
func GetCheckpoint(formName string) (*Checkpoint, error) {
	if DB == nil {
		return nil, fmt.Errorf("gorm database not initialized")
	}

	var cp Checkpoint
	if err := DB.Where("form_name = ?", formName).First(&cp).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, nil // no checkpoint exists
		}
		return nil, fmt.Errorf("get checkpoint for %s: %w", formName, err)
	}
	return &cp, nil
}

// SaveCheckpoint saves or updates the checkpoint for a form.
func SaveCheckpoint(formName string, position int64, lastSyncTime string) error {
	return SaveCheckpointForRun(formName, "", position, lastSyncTime)
}

// SaveCheckpointForRun persists the last durably written position and its run
// owner. A legacy checkpoint may have an empty RunID and remains readable.
func SaveCheckpointForRun(formName, runID string, position int64, lastSyncTime string) error {
	if DB == nil {
		return fmt.Errorf("gorm database not initialized")
	}

	cp := Checkpoint{FormName: formName}
	if err := DB.Where("form_name = ?", formName).First(&cp).Error; err != nil && err != gorm.ErrRecordNotFound {
		return fmt.Errorf("save checkpoint for %s: %w", formName, err)
	}

	cp.LastPosition = position
	cp.LastSyncTime = lastSyncTime
	cp.RunID = runID

	if cp.ID == 0 {
		return DB.Create(&cp).Error
	}
	return DB.Save(&cp).Error
}

// GetCheckpointsForRun returns checkpoints written by one run.
func GetCheckpointsForRun(runID string) ([]Checkpoint, error) {
	if DB == nil {
		return nil, fmt.Errorf("gorm database not initialized")
	}
	var checkpoints []Checkpoint
	if err := DB.Where("run_id = ?", runID).Order("form_name ASC").Find(&checkpoints).Error; err != nil {
		return nil, fmt.Errorf("get checkpoints for run %s: %w", runID, err)
	}
	return checkpoints, nil
}

// SaveRecoveryNotice persists a manual-recovery warning once per run/form/reason.
func SaveRecoveryNotice(runID, formName, reason string) error {
	if DB == nil {
		return fmt.Errorf("gorm database not initialized")
	}
	var existing SyncError
	query := DB.Where("run_id = ? AND form_name = ? AND level = ? AND message = ?", runID, formName, "warning", reason).First(&existing)
	if query.Error == nil {
		return nil
	}
	if query.Error != gorm.ErrRecordNotFound {
		return fmt.Errorf("check recovery notice: %w", query.Error)
	}
	if err := DB.Create(&SyncError{
		RunID:    runID,
		FormName: formName,
		Level:    "warning",
		Message:  reason,
		Detail:   "manual recovery required",
	}).Error; err != nil {
		return fmt.Errorf("save recovery notice: %w", err)
	}
	return nil
}

func ListRecoveryNotices(runID string) ([]SyncError, error) {
	if DB == nil {
		return nil, fmt.Errorf("gorm database not initialized")
	}
	var notices []SyncError
	if err := DB.Where("run_id = ? AND level = ?", runID, "warning").Order("created_at ASC").Find(&notices).Error; err != nil {
		return nil, fmt.Errorf("list recovery notices: %w", err)
	}
	return notices, nil
}

// ClearCheckpoint removes the checkpoint for a form.
func ClearCheckpoint(formName string) error {
	if DB == nil {
		return fmt.Errorf("gorm database not initialized")
	}

	return DB.Where("form_name = ?", formName).Delete(&Checkpoint{}).Error
}

// GetDisabledFormNames returns a set of form names that are explicitly disabled.
func GetDisabledFormNames() map[string]bool {
	disabled := make(map[string]bool)
	if DB == nil {
		return disabled
	}
	var settings []FormSetting
	if err := DB.Where("enabled = ?", false).Find(&settings).Error; err != nil {
		return disabled
	}
	for _, s := range settings {
		disabled[s.FormName] = true
	}
	return disabled
}

// MigrateFormQueriesFromJSON seeds go_form_queries from form-queries.json if empty.
// Returns the number of rows inserted.
func MigrateFormQueriesFromJSON() int {
	if DB == nil {
		return 0
	}

	// Skip if data already exists
	var count int64
	DB.Model(&FormQueryConfig{}).Count(&count)
	if count > 0 {
		return 0
	}

	configPath, err := findConfigFile()
	if err != nil {
		return 0
	}
	configDir := filepath.Dir(configPath)
	candidates := []string{
		filepath.Join(configDir, "packages", "sync-config", "form-queries.json"),
		filepath.Join(configDir, "form-queries.json"),
	}

	for _, p := range candidates {
		data, err := os.ReadFile(p)
		if err != nil {
			continue
		}
		type rawEntry struct {
			FormID        string                 `json:"FormId"`
			FieldKeys     string                 `json:"FieldKeys"`
			FilterString  interface{}            `json:"FilterString"`
			FieldMap      map[string]string      `json:"FieldMap,omitempty"`
			DefaultValues map[string]interface{} `json:"DefaultValues,omitempty"`
		}
		var raw map[string]rawEntry
		if err := json.Unmarshal(data, &raw); err != nil {
			continue
		}

		for formName, entry := range raw {
			filterStr := ""
			if s, ok := entry.FilterString.(string); ok {
				filterStr = s
			}
			fieldMapJSON, _ := json.Marshal(entry.FieldMap)
			defaultValsJSON, _ := json.Marshal(entry.DefaultValues)

			DB.Create(&FormQueryConfig{
				FormName:      formName,
				FormID:        entry.FormID,
				FieldKeys:     entry.FieldKeys,
				FilterString:  filterStr,
				FieldMap:      string(fieldMapJSON),
				DefaultValues: string(defaultValsJSON),
			})
		}
		log.Printf("[GORM] Migrated %d form queries from %s", len(raw), p)
		return len(raw)
	}
	return 0
}
