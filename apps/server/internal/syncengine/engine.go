package syncengine

import (
	"context"
	"errors"
	"fmt"
	"log"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/kingdee-sync/go/internal/api/contract"
	"github.com/kingdee-sync/go/internal/config"
	"github.com/kingdee-sync/go/internal/db"
	"github.com/kingdee-sync/go/internal/gormdb"
	"github.com/kingdee-sync/go/internal/kind"
)

type SyncStatus string

const (
	StatusIdle               SyncStatus = "idle" // internal compatibility value; never returned by the API
	StatusRunning            SyncStatus = SyncStatus(contract.StatusRunning)
	StatusStopping           SyncStatus = SyncStatus(contract.StatusStopping)
	StatusSuccess            SyncStatus = SyncStatus(contract.StatusSuccess)
	StatusFailed             SyncStatus = SyncStatus(contract.StatusFailed)
	StatusPartial            SyncStatus = SyncStatus(contract.StatusPartial)
	StatusStopped            SyncStatus = SyncStatus(contract.StatusStopped)
	StatusFailedAbnormalExit SyncStatus = SyncStatus(contract.StatusFailedAbnormalExit)
)

var (
	ErrSyncAlreadyRunning   = errors.New("sync engine already has an active run")
	ErrSyncRunNotPrepared   = errors.New("sync run was not prepared")
	ErrSyncRunNotPersistent = errors.New("sync run is not persistent")
	ErrSyncRunNotActive     = errors.New("sync run is not active")
	ErrSyncShuttingDown     = errors.New("sync engine is shutting down")
)

func syncTypeLabel(syncType string) string {
	switch syncType {
	case "incremental":
		return "增量"
	case "full":
		return "全量"
	case "reset":
		return "重置"
	default:
		return syncType
	}
}

type ManualRecoveryNotice struct {
	OriginalRunID string
	FormName      string
	Reason        string
}

type RecoveryPlan struct {
	OriginalRunID string
	RunID         string
	SyncType      string
	Forms         []string
	Notices       []ManualRecoveryNotice
}

type SyncResult struct {
	RunID        string     `json:"run_id"`
	Status       SyncStatus `json:"status"`
	Message      string     `json:"message"`
	StartTime    time.Time  `json:"start_time"`
	EndTime      time.Time  `json:"end_time"`
	DurationSec  float64    `json:"duration_seconds"`
	TotalRecords int        `json:"total_records"`
	FormStats    []FormStat `json:"form_stats"`
	DryRun       bool       `json:"dry_run"`
}

// StatusSnapshot is an atomic status view for one run.
type StatusSnapshot struct {
	RunID       string
	Status      SyncStatus
	Message     string
	Progress    int
	CurrentForm string
	Elapsed     float64
	StartedAt   time.Time
	FormStats   []FormStat
}

type FormStat struct {
	FormName      string     `json:"form_name"`
	TableName     string     `json:"table_name"`
	FetchedCount  int        `json:"fetched_count"`
	InsertedCount int        `json:"inserted_count"`
	ErrorCount    int        `json:"error_count"`
	Status        SyncStatus `json:"status"`
	DurationSec   float64    `json:"duration_seconds"`
	Error         string     `json:"error,omitempty"`
}

// LogCallback is called during sync to record real-time logs.
type LogCallback func(runID, formName, level, message string)

type SyncEngine struct {
	mu                 sync.RWMutex
	current            *SyncResult
	progress           int
	currentForm        string
	startTime          time.Time
	logCallback        LogCallback
	runID              string    // current run ID
	writer             RowWriter // database write abstraction
	active             bool
	executing          bool
	runCancel          context.CancelFunc
	runDone            chan struct{}
	stopRequested      bool
	gracefulStop       bool
	shutdownRequested  bool
	fetchCancel        context.CancelFunc
	stopWatcherStarted bool
	fetchRows          func(context.Context, string, int) (*kind.QueryResult, error)
	writeRowsFunc      func(context.Context, string, []map[string]interface{}, []string, map[string]string) (int, error)
	formQuery          func(string) (config.FormQuery, bool)
}

const stopTimeout = 60 * time.Second

// PriorityMap defines form priority groups (aligned with Python side).
// Group 0: small tables — fast completion, release API bandwidth early.
// Group 1: medium tables — normal data volume.
// Group 2: large tables — exclusive bandwidth, run after smaller groups.
var PriorityMap = map[string]int{
	// Group 0: 小表
	"仓库":     0,
	"物料":     0,
	"客户资料":   0,
	"即时库存":   0,
	"物料清单":   0,
	"物料清单子项": 0,
	"预测订单":   0,
	// Group 1: 中表
	"销售订单":   1,
	"采购订单":   1,
	"应付单":    1,
	"销售出库单":  1,
	"销售退货单":  1,
	"发货通知单":  1,
	"委外订单":   1,
	"科目余额表":  1,
	"生产订单明细": 1,
	"生产入库单":  1,
	"应收单":    1,
	"采购入库单":  1,
	// Group 2: 大表（独占带宽）
	"生产订单主表":    2,
	"生产用料清单主表":  2,
	"生产用料清单明细表": 2,
}

// GetFormPriority returns the priority group for a form. Unknown forms default to group 1.
func GetFormPriority(formName string) int {
	if p, ok := PriorityMap[formName]; ok {
		return p
	}
	return 1
}

func NewSyncEngine() *SyncEngine {
	cfg := config.Get()
	dbType := "mysql" // default to Doris/MySQL
	if cfg != nil {
		effDB := cfg.GetEffectiveDatabase()
		if effDB.Type != "" {
			dbType = effDB.Type
		}
	}

	var writer RowWriter
	switch dbType {
	case "mysql":
		writer = NewDorisWriter()
		log.Printf("[SYNC-ENGINE] Using DorisWriter (Stream Load) for database type=mysql")
	default:
		// Fallback to DorisWriter for now; SQL Server support will be removed in phase 2.
		writer = NewDorisWriter()
		log.Printf("[SYNC-ENGINE] Warning: unknown database type=%s, falling back to DorisWriter", dbType)
	}

	return &SyncEngine{
		writer: writer,
	}
}

// SetLogCallback sets the callback for real-time sync logging.
func (e *SyncEngine) SetLogCallback(cb LogCallback, runID string) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.logCallback = cb
	e.runID = runID
}

// logMsg calls the log callback if set.
func (e *SyncEngine) logMsg(formName, level, message string) {
	e.mu.RLock()
	cb := e.logCallback
	rid := e.runID
	e.mu.RUnlock()
	if cb == nil {
		log.Printf("[LOG-MSG] Skipping: cb is nil, form=%s, msg=%s", formName, message)
		return
	}
	if rid == "" {
		log.Printf("[LOG-MSG] Skipping: rid is empty, form=%s, msg=%s", formName, message)
		return
	}
	cb(rid, formName, level, message)
}

func (e *SyncEngine) GetStatus() (SyncStatus, string, int, string, float64, []FormStat) {
	e.mu.RLock()
	defer e.mu.RUnlock()
	if e.current == nil {
		return StatusIdle, "", 0, "", 0, nil
	}
	var elapsedSeconds float64
	if !e.current.StartTime.IsZero() {
		if !e.current.EndTime.IsZero() {
			elapsedSeconds = e.current.DurationSec
		} else {
			elapsedSeconds = time.Since(e.current.StartTime).Seconds()
		}
	}
	return e.current.Status, e.current.Message, e.progress, e.currentForm, elapsedSeconds, e.current.FormStats
}

// CurrentResult returns a snapshot for runID while it is owned by the engine.
func (e *SyncEngine) CurrentResult(runID string) (*SyncResult, bool) {
	e.mu.RLock()
	defer e.mu.RUnlock()
	if e.current == nil || e.current.RunID != runID {
		return nil, false
	}
	copyResult := *e.current
	copyResult.FormStats = append([]FormStat(nil), e.current.FormStats...)
	return &copyResult, true
}

// GetStatusSnapshot returns all live status fields from the requested run under one lock.
func (e *SyncEngine) GetStatusSnapshot(runID string) (StatusSnapshot, bool) {
	e.mu.RLock()
	defer e.mu.RUnlock()
	if e.current == nil || e.current.RunID != runID {
		return StatusSnapshot{}, false
	}

	elapsed := float64(0)
	if !e.current.StartTime.IsZero() {
		if e.current.EndTime.IsZero() {
			elapsed = time.Since(e.current.StartTime).Seconds()
		} else {
			elapsed = e.current.DurationSec
		}
	}
	return StatusSnapshot{
		RunID:       e.current.RunID,
		Status:      e.current.Status,
		Message:     e.current.Message,
		Progress:    e.progress,
		CurrentForm: e.currentForm,
		Elapsed:     elapsed,
		StartedAt:   e.current.StartTime,
		FormStats:   append([]FormStat(nil), e.current.FormStats...),
	}, true
}

// CurrentRunID returns the ID of the engine's active run, if any.
func (e *SyncEngine) CurrentRunID() string {
	e.mu.RLock()
	defer e.mu.RUnlock()
	if !e.active || e.current == nil {
		return ""
	}
	return e.current.RunID
}

// PrepareRun reserves the engine for a caller that already persisted runID.
// The API uses this to make the run ID durable before starting a goroutine.
func (e *SyncEngine) PrepareRun(runID string, dryRun bool) error {
	if runID == "" {
		return fmt.Errorf("run ID is required")
	}
	if gormdb.DB == nil {
		return ErrSyncRunNotPersistent
	}
	e.mu.RLock()
	reject := e.shutdownRequested
	e.mu.RUnlock()
	if reject {
		return ErrSyncShuttingDown
	}
	run, err := gormdb.GetSyncRun(runID)
	if err != nil {
		return fmt.Errorf("sync run %s is not persisted: %w", runID, err)
	}
	if contract.SyncStatus(run.Status) != contract.StatusRunning {
		return fmt.Errorf("sync run %s is not reservable from status %q", runID, run.Status)
	}
	_, err = e.beginRun(runID, dryRun)
	return err
}

func (e *SyncEngine) beginRun(runID string, dryRun bool) (*SyncResult, error) {
	e.mu.Lock()
	defer e.mu.Unlock()
	if e.active {
		return nil, ErrSyncAlreadyRunning
	}
	if e.shutdownRequested {
		return nil, ErrSyncShuttingDown
	}
	if runID == "" {
		runID = "RUN-" + uuid.NewString()
	}
	e.startTime = time.Now()
	e.runID = runID
	e.current = &SyncResult{
		RunID:     runID,
		Status:    StatusRunning,
		StartTime: e.startTime,
		DryRun:    dryRun,
	}
	e.progress = 0
	e.currentForm = ""
	e.active = true
	e.stopRequested = false
	e.gracefulStop = false
	e.stopWatcherStarted = false
	e.runCancel = nil
	e.runDone = nil
	return e.current, nil
}

// SyncData performs Kingdee query + DB upsert for the given forms.
func (e *SyncEngine) SyncData(ctx context.Context, forms []string, syncType string, dryRun bool) (*SyncResult, error) {
	e.mu.RLock()
	shuttingDown := e.shutdownRequested
	e.mu.RUnlock()
	if shuttingDown {
		return nil, ErrSyncShuttingDown
	}
	if gormdb.DB == nil {
		return nil, ErrSyncRunNotPersistent
	}
	runID := "RUN-" + uuid.NewString()
	if _, err := gormdb.CreateSyncRun(runID, "", syncType); err != nil {
		return nil, err
	}
	result, err := e.beginRun(runID, dryRun)
	if err != nil {
		if finishErr := gormdb.FinishSyncRunWithRetry(runID, string(StatusFailed), 0, 0, 0, 0, 0, 0, 0, err.Error()); finishErr != nil {
			log.Printf("[SYNC] Failed to record rejected run %s: %v", runID, finishErr)
		}
		return nil, err
	}
	return e.runSync(ctx, result.RunID, forms, syncType, dryRun)
}

// SyncDataWithRunID runs a previously prepared and persisted API run.
func (e *SyncEngine) SyncDataWithRunID(ctx context.Context, runID string, forms []string, syncType string, dryRun bool) (*SyncResult, error) {
	if ctx == nil {
		ctx = context.Background()
	}
	e.mu.RLock()
	prepared := e.active && e.current != nil && e.current.RunID == runID
	e.mu.RUnlock()
	if !prepared {
		return nil, ErrSyncRunNotPrepared
	}
	if gormdb.DB == nil {
		return nil, ErrSyncRunNotPersistent
	}
	queryCtx := ctx
	if queryCtx.Err() != nil {
		queryCtx = context.Background()
	}
	run, err := gormdb.GetSyncRunContext(queryCtx, runID)
	if err != nil {
		return nil, fmt.Errorf("sync run %s is not persisted: %w", runID, err)
	}
	runStatus := contract.SyncStatus(run.Status)
	if contract.IsTerminalStatus(runStatus) {
		return nil, fmt.Errorf("sync run %s is already complete with status %q", runID, run.Status)
	}
	if runStatus != contract.StatusRunning && runStatus != contract.StatusStopping {
		return nil, fmt.Errorf("sync run %s is not active with status %q", runID, run.Status)
	}
	e.mu.RLock()
	shuttingDown := e.shutdownRequested
	currentStopping := e.current != nil && e.current.Status == StatusStopping
	e.mu.RUnlock()
	if runStatus == contract.StatusStopping || currentStopping || shuttingDown {
		if runStatus == contract.StatusRunning && shuttingDown && !currentStopping {
			if !e.RequestGracefulStop(runID) {
				return nil, ErrSyncShuttingDown
			}
		}
		return e.finishPreparedRunStopped(runID)
	}
	return e.runSync(ctx, runID, forms, syncType, dryRun)
}

// finishPreparedRunStopped closes a run that was stopped after PrepareRun but
// before its asynchronous runner entered runSync.
func (e *SyncEngine) finishPreparedRunStopped(runID string) (*SyncResult, error) {
	e.mu.RLock()
	if !e.active || e.current == nil || e.current.RunID != runID {
		e.mu.RUnlock()
		return nil, ErrSyncRunNotActive
	}
	if e.executing {
		e.mu.RUnlock()
		return nil, ErrSyncAlreadyRunning
	}
	result := e.current
	startTime := result.StartTime
	e.mu.RUnlock()

	duration := time.Since(startTime).Seconds()
	if err := gormdb.FinishSyncRunWithRetry(runID, string(StatusStopped), duration, 0, 0, 0, 0, 0, 0, "sync stopped before runner started"); err != nil {
		return nil, err
	}
	persisted, err := gormdb.GetSyncRun(runID)
	if err != nil {
		return nil, err
	}

	e.mu.Lock()
	result.Status = SyncStatus(persisted.Status)
	result.Message = "sync stopped"
	result.EndTime = time.Now()
	result.DurationSec = duration
	e.progress = 100
	e.active = false
	e.mu.Unlock()
	return result, nil
}

// PrepareRecovery builds and persists a child run for an abnormal parent. It
// only selects large-table checkpoints that belong to that parent; all other
// cases are returned as manual-recovery notices without creating a run.
func (e *SyncEngine) PrepareRecovery(parentRunID string, dryRun bool) (*RecoveryPlan, error) {
	if gormdb.DB == nil {
		return nil, ErrSyncRunNotPersistent
	}
	if e.IsShuttingDown() {
		return nil, ErrSyncShuttingDown
	}
	if e.CurrentRunID() != "" {
		return nil, ErrSyncAlreadyRunning
	}
	parent, err := gormdb.GetSyncRun(parentRunID)
	if err != nil {
		return nil, fmt.Errorf("load abnormal sync run %s: %w", parentRunID, err)
	}
	if parent.Status != string(contract.StatusFailedAbnormalExit) {
		return nil, fmt.Errorf("sync run %s is not failed_abnormal_exit", parentRunID)
	}
	checkpoints, err := gormdb.GetCheckpointsForRun(parentRunID)
	if err != nil {
		return nil, err
	}
	plan := &RecoveryPlan{OriginalRunID: parentRunID, SyncType: parent.SyncType}
	seen := make(map[string]struct{})
	for _, cp := range checkpoints {
		if _, ok := seen[cp.FormName]; ok {
			continue
		}
		seen[cp.FormName] = struct{}{}
		if GetFormPriority(cp.FormName) != 2 {
			plan.Notices = append(plan.Notices, ManualRecoveryNotice{
				OriginalRunID: parentRunID,
				FormName:      cp.FormName,
				Reason:        "checkpoint form is not a large table",
			})
			continue
		}
		if cp.RunID != parentRunID || cp.LastPosition <= 0 {
			reason := "checkpoint validation failed"
			if cp.LastPosition <= 0 {
				reason = "checkpoint position is not positive"
			} else if cp.RunID != parentRunID {
				reason = "checkpoint does not belong to abnormal run"
			}
			plan.Notices = append(plan.Notices, ManualRecoveryNotice{
				OriginalRunID: parentRunID,
				FormName:      cp.FormName,
				Reason:        reason,
			})
			continue
		}
		plan.Forms = append(plan.Forms, cp.FormName)
	}
	if len(checkpoints) == 0 {
		formName := ""
		for _, form := range parent.Forms {
			if GetFormPriority(form.FormName) == 2 {
				formName = form.FormName
				break
			}
		}
		plan.Notices = append(plan.Notices, ManualRecoveryNotice{
			OriginalRunID: parentRunID,
			FormName:      formName,
			Reason:        "no valid checkpoint; manual recovery required",
		})
	}
	for _, notice := range plan.Notices {
		if err := gormdb.SaveRecoveryNotice(notice.OriginalRunID, notice.FormName, notice.Reason); err != nil {
			return nil, err
		}
	}
	if len(plan.Forms) == 0 {
		return plan, nil
	}

	runID := "RUN-RECOVERY-" + uuid.NewString()
	reason := fmt.Sprintf("recovery of abnormal run %s", parentRunID)
	recoveryRun, err := gormdb.CreateRecoverySyncRun(runID, parentRunID, parent.TaskName, parent.SyncType, reason, len(plan.Forms))
	if err != nil {
		return nil, err
	}
	if err := e.PrepareRun(recoveryRun.RunID, dryRun); err != nil {
		_ = gormdb.FinishSyncRunWithRetry(recoveryRun.RunID, string(StatusFailed), 0, 0, 0, 0, 0, 0, 0, err.Error())
		return nil, err
	}
	plan.RunID = recoveryRun.RunID
	return plan, nil
}

// RecoverAbnormalRun is the synchronous recovery entry used by startup and
// tests. The returned plan contains manual notices even when no child run is
// created.
func (e *SyncEngine) RecoverAbnormalRun(ctx context.Context, parentRunID string, dryRun bool) (*RecoveryPlan, *SyncResult, error) {
	plan, err := e.PrepareRecovery(parentRunID, dryRun)
	if err != nil || plan.RunID == "" {
		return plan, nil, err
	}
	result, err := e.SyncDataWithRunID(ctx, plan.RunID, plan.Forms, plan.SyncType, dryRun)
	return plan, result, err
}

// RecoverPendingAbnormalRuns creates and starts all currently recoverable
// abnormal runs. Runs without a valid checkpoint only emit a manual notice.
func (e *SyncEngine) RecoverPendingAbnormalRuns(ctx context.Context, dryRun bool) ([]RecoveryPlan, error) {
	runs, err := gormdb.ListAbnormalSyncRuns()
	if err != nil {
		return nil, err
	}
	plans := make([]RecoveryPlan, 0, len(runs))
	for _, run := range runs {
		hasSuccessfulRecovery, err := gormdb.HasSuccessfulRecovery(run.RunID)
		if err != nil {
			return plans, err
		}
		if hasSuccessfulRecovery {
			continue
		}
		if e.CurrentRunID() != "" {
			break
		}
		plan, err := e.PrepareRecovery(run.RunID, dryRun)
		if err != nil {
			return plans, err
		}
		if len(plan.Notices) > 0 {
			for _, notice := range plan.Notices {
				log.Printf("[RECOVERY] Manual recovery required: run=%s form=%s reason=%s", notice.OriginalRunID, notice.FormName, notice.Reason)
			}
		}
		plans = append(plans, *plan)
		if plan.RunID == "" {
			continue
		}
		go func(plan RecoveryPlan) {
			if _, err := e.SyncDataWithRunID(ctx, plan.RunID, plan.Forms, plan.SyncType, dryRun); err != nil {
				log.Printf("[RECOVERY] Recovery run %s failed: %v", plan.RunID, err)
			}
		}(*plan)
	}
	return plans, nil
}

// SetStopping moves an active run to the stopping state immediately.
func (e *SyncEngine) SetStopping(runID string) bool {
	e.mu.Lock()
	defer e.mu.Unlock()
	if !e.active || e.current == nil || e.current.RunID != runID {
		return false
	}
	e.current.Status = StatusStopping
	e.current.Message = "sync stop requested"
	return true
}

// RequestStop coordinates the in-memory and persisted stopping transition.
func (e *SyncEngine) RequestStop(runID string) bool {
	var cancel context.CancelFunc
	var done chan struct{}
	startWatcher := false
	e.mu.Lock()
	if !e.active || e.current == nil || e.current.RunID != runID || gormdb.DB == nil {
		e.mu.Unlock()
		return false
	}
	run, err := gormdb.GetSyncRun(runID)
	if err != nil {
		e.mu.Unlock()
		return false
	}
	switch contract.SyncStatus(run.Status) {
	case contract.StatusRunning:
		if err := gormdb.UpdateSyncRunStatus(runID, string(contract.StatusStopping), "stop requested"); err != nil {
			e.mu.Unlock()
			return false
		}
	case contract.StatusStopping:
	default:
		e.mu.Unlock()
		return false
	}
	e.current.Status = StatusStopping
	e.current.Message = "sync stop requested"
	e.stopRequested = true
	e.gracefulStop = false
	cancel = e.runCancel
	done = e.runDone
	if done != nil && !e.stopWatcherStarted {
		e.stopWatcherStarted = true
		startWatcher = true
	}
	e.mu.Unlock()
	if cancel != nil {
		cancel()
	}
	if startWatcher {
		go e.watchStopTimeout(runID, done)
	}
	return true
}

// RejectNewRuns closes the admission gate while allowing the current run to
// finish its already submitted database write.
func (e *SyncEngine) RejectNewRuns() {
	e.mu.Lock()
	e.shutdownRequested = true
	e.mu.Unlock()
}

func (e *SyncEngine) IsShuttingDown() bool {
	e.mu.RLock()
	defer e.mu.RUnlock()
	return e.shutdownRequested
}

// RequestGracefulStop enters stopping without canceling the active run. The
// fetch context is canceled so no new Kingdee page is requested; the writer
// keeps the run context until the shutdown deadline.
func (e *SyncEngine) RequestGracefulStop(runID string) bool {
	var fetchCancel context.CancelFunc
	var done chan struct{}
	startWatcher := false
	e.mu.Lock()
	if !e.active || e.current == nil || e.current.RunID != runID || gormdb.DB == nil {
		e.mu.Unlock()
		return false
	}
	run, err := gormdb.GetSyncRun(runID)
	if err != nil {
		e.mu.Unlock()
		return false
	}
	switch contract.SyncStatus(run.Status) {
	case contract.StatusRunning:
		if err := gormdb.UpdateSyncRunStatus(runID, string(contract.StatusStopping), "graceful shutdown requested"); err != nil {
			e.mu.Unlock()
			return false
		}
	case contract.StatusStopping:
	default:
		e.mu.Unlock()
		return false
	}
	e.current.Status = StatusStopping
	e.current.Message = "graceful shutdown requested"
	e.stopRequested = true
	e.gracefulStop = true
	fetchCancel = e.fetchCancel
	done = e.runDone
	if done != nil && !e.stopWatcherStarted {
		e.stopWatcherStarted = true
		startWatcher = true
	}
	e.mu.Unlock()
	if fetchCancel != nil {
		fetchCancel()
	}
	if startWatcher {
		go e.watchStopTimeout(runID, done)
	}
	return true
}

// GracefulStop waits for the active run, then force-cancels and marks it
// abnormal if the caller's deadline expires.
func (e *SyncEngine) GracefulStop(ctx context.Context) error {
	if ctx == nil {
		ctx = context.Background()
	}
	e.RejectNewRuns()
	runID := e.CurrentRunID()
	if runID == "" {
		return nil
	}
	if !e.RequestGracefulStop(runID) {
		return nil
	}
	e.mu.RLock()
	done := e.runDone
	e.mu.RUnlock()
	if done == nil {
		return nil
	}
	select {
	case <-done:
		return nil
	case <-ctx.Done():
		message := "abnormal exit: graceful shutdown timeout exceeded"
		if err := gormdb.MarkSyncRunAbnormalExitWithRetry(runID, message); err != nil {
			log.Printf("[SYNC] Failed to mark shutdown timeout for %s: %v", runID, err)
		}
		e.MarkAbnormalExit(runID, message)
		e.cancelActiveRun(runID)
		return ctx.Err()
	}
}

func (e *SyncEngine) cancelActiveRun(runID string) {
	e.mu.RLock()
	cancel := e.runCancel
	activeID := e.runID
	e.mu.RUnlock()
	if activeID == runID && cancel != nil {
		cancel()
	}
}

func (e *SyncEngine) watchStopTimeout(runID string, done <-chan struct{}) {
	timer := time.NewTimer(stopTimeout)
	defer timer.Stop()
	select {
	case <-done:
		return
	case <-timer.C:
		message := "abnormal exit: stop timeout exceeded"
		if err := gormdb.MarkSyncRunAbnormalExitWithRetry(runID, message); err != nil {
			log.Printf("[SYNC] Failed to mark timed out run %s abnormal: %v", runID, err)
		}
		e.MarkAbnormalExit(runID, message)
		e.cancelActiveRun(runID)
	}
}

func (e *SyncEngine) isFetchStopped() bool {
	e.mu.RLock()
	defer e.mu.RUnlock()
	return e.gracefulStop
}

func (e *SyncEngine) isCleanupDisabled() bool {
	e.mu.RLock()
	defer e.mu.RUnlock()
	return e.shutdownRequested || e.stopRequested || e.gracefulStop ||
		(e.current != nil && e.current.Status == StatusStopping)
}

func (e *SyncEngine) isRecoveryRun(runID string) (bool, error) {
	if gormdb.DB == nil {
		return false, fmt.Errorf("gorm database not initialized")
	}
	var run gormdb.SyncRun
	if err := gormdb.DB.Select("parent_run_id").Where("run_id = ?", runID).First(&run).Error; err != nil {
		return false, fmt.Errorf("load sync run identity %s: %w", runID, err)
	}
	if run.ParentRunID == "" {
		return false, nil
	}
	var parent gormdb.SyncRun
	if err := gormdb.DB.Select("status").Where("run_id = ?", run.ParentRunID).First(&parent).Error; err != nil {
		return false, fmt.Errorf("load recovery parent identity %s: %w", run.ParentRunID, err)
	}
	if parent.Status != string(contract.StatusFailedAbnormalExit) {
		return false, fmt.Errorf("recovery parent %s is not failed_abnormal_exit", run.ParentRunID)
	}
	return true, nil
}

func (e *SyncEngine) checkpointBelongsToRun(cp *gormdb.Checkpoint, runID string) (bool, error) {
	if cp == nil {
		return false, nil
	}
	isRecovery, err := e.isRecoveryRun(runID)
	if err != nil {
		return false, err
	}
	if cp.RunID == runID {
		return true, nil
	}
	if !isRecovery {
		// Keep legacy checkpoints usable for the first post-migration run. New
		// checkpoints always carry a run owner.
		return cp.RunID == "", nil
	}
	var run gormdb.SyncRun
	if gormdb.DB == nil || gormdb.DB.Select("parent_run_id").Where("run_id = ?", runID).First(&run).Error != nil {
		return false, fmt.Errorf("load recovery run parent %s", runID)
	}
	return cp.RunID == run.ParentRunID, nil
}

// MarkAbnormalExit updates the live result when persistence or execution
// timeout makes normal completion unsafe. Terminal success is never replaced.
func (e *SyncEngine) MarkAbnormalExit(runID, message string) bool {
	e.mu.Lock()
	defer e.mu.Unlock()
	if e.current == nil || e.current.RunID != runID || contract.IsTerminalStatus(contract.SyncStatus(e.current.Status)) {
		return false
	}
	now := time.Now()
	e.current.Status = StatusFailedAbnormalExit
	e.current.Message = message
	e.current.EndTime = now
	e.current.DurationSec = now.Sub(e.current.StartTime).Seconds()
	e.progress = 100
	return true
}

func (e *SyncEngine) runSync(ctx context.Context, runID string, forms []string, syncType string, dryRun bool) (result *SyncResult, err error) {
	if ctx == nil {
		ctx = context.Background()
	}
	e.mu.Lock()
	if !e.active || e.current == nil || e.current.RunID != runID {
		e.mu.Unlock()
		return nil, ErrSyncRunNotActive
	}
	if e.executing {
		e.mu.Unlock()
		return nil, ErrSyncAlreadyRunning
	}
	e.executing = true
	result = e.current
	runCtx, cancel := context.WithCancel(ctx)
	fetchCtx, fetchCancel := context.WithCancel(runCtx)
	done := make(chan struct{})
	e.runCancel = cancel
	e.runDone = done
	e.fetchCancel = fetchCancel
	stopRequested := e.stopRequested
	gracefulStop := e.gracefulStop
	watchStop := stopRequested && !e.stopWatcherStarted
	if watchStop {
		e.stopWatcherStarted = true
	}
	e.mu.Unlock()
	ctx = runCtx
	if stopRequested && !gracefulStop {
		cancel()
	}
	if watchStop {
		go e.watchStopTimeout(runID, done)
	}
	defer func() {
		close(done)
		cancel()
		e.mu.Lock()
		e.executing = false
		e.active = false
		e.runCancel = nil
		e.runDone = nil
		e.fetchCancel = nil
		e.mu.Unlock()
	}()

	mode := "live"
	if dryRun {
		mode = "DRY-RUN"
	}
	log.Printf("[%s] Starting sync: forms=%v, type=%s", mode, forms, syncType)
	e.logMsg("", "INFO", fmt.Sprintf("开始同步: %d 个表单, 模式=%s", len(forms), syncTypeLabel(syncType)))

	if len(forms) == 0 {
		forms = config.GetConfiguredFormNames()
		if len(forms) == 0 {
			return nil, fmt.Errorf("no configured forms available for sync")
		}
	}

	// Both API and legacy callers persist the run before entering runSync.
	if gormdb.DB == nil {
		return nil, ErrSyncRunNotPersistent
	}
	var syncRun gormdb.SyncRun
	dbCtx := ctx
	if dbCtx.Err() != nil {
		dbCtx = context.Background()
	}
	if findErr := gormdb.DB.WithContext(dbCtx).Where("run_id = ?", runID).First(&syncRun).Error; findErr != nil {
		return nil, fmt.Errorf("sync run %s is not persisted: %w", runID, findErr)
	}
	heartbeatDone := make(chan struct{})
	var heartbeatWG sync.WaitGroup
	heartbeatWG.Add(1)
	go func() {
		defer heartbeatWG.Done()
		ticker := time.NewTicker(30 * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				if err := gormdb.UpdateSyncRunHeartbeat(runID); err != nil {
					log.Printf("[HEARTBEAT] Failed to update heartbeat for %s: %v", runID, err)
				}
			case <-heartbeatDone:
				return
			}
		}
	}()
	defer func() {
		close(heartbeatDone)
		heartbeatWG.Wait()
	}()

	// Group forms by priority
	grouped := make(map[int][]string)
	for _, f := range forms {
		p := GetFormPriority(f)
		grouped[p] = append(grouped[p], f)
	}

	// Get sorted priority list
	var priorities []int
	for p := range grouped {
		priorities = append(priorities, p)
	}
	sort.Ints(priorities)

	log.Printf("[SYNC] Priority groups: %v", priorities)
	for _, p := range priorities {
		log.Printf("[SYNC] Group %d: %v", p, grouped[p])
	}

	// Get table concurrency from config
	cfg := config.Get()
	tableConcurrency := 8 // default
	if cfg != nil && cfg.Sync.TableConcurrency > 0 {
		tableConcurrency = cfg.Sync.TableConcurrency
	}

	var mu sync.Mutex
	var results []FormStat

	// Process each priority group sequentially
	for _, priority := range priorities {
		groupForms := grouped[priority]

		// Group 2 (large tables) runs serially; others use semaphore
		concurrency := tableConcurrency
		if priority == 2 {
			concurrency = 1
		}

		log.Printf("[SYNC] Processing group %d with concurrency=%d: %v", priority, concurrency, groupForms)

		// Semaphore for this group
		sem := make(chan struct{}, concurrency)
		var wg sync.WaitGroup

		for _, form := range groupForms {
			wg.Add(1)
			go func(formName string) {
				defer wg.Done()
				select {
				case sem <- struct{}{}: // acquire
				case <-ctx.Done():
					return
				}
				defer func() {
					<-sem // release
				}()

				start := time.Now()
				stat := FormStat{
					FormName:  formName,
					TableName: config.FormToTableName(formName),
				}
				if ctx.Err() != nil || e.isFetchStopped() {
					stat.Status = StatusStopped
					stat.Error = "sync stopped"
					mu.Lock()
					results = append(results, stat)
					mu.Unlock()
					return
				}
				_, identityErr := e.isRecoveryRun(runID)
				if identityErr != nil {
					stat.Status = StatusFailed
					stat.ErrorCount = 1
					stat.Error = fmt.Sprintf("sync run identity validation failed: %v", identityErr)
					stat.DurationSec = time.Since(start).Seconds()
					mu.Lock()
					results = append(results, stat)
					mu.Unlock()
					return
				}

				e.mu.Lock()
				e.currentForm = formName
				e.mu.Unlock()

				e.logMsg(formName, "INFO", "开始同步")

				// 1. Load form query config
				getFormQuery := config.GetFormQuery
				if e.formQuery != nil {
					getFormQuery = e.formQuery
				}
				formQuery, ok := getFormQuery(formName)
				if !ok {
					log.Printf("No form query config for %s, skipping", formName)
					e.logMsg(formName, "ERROR", "无表单查询配置，跳过")
					stat.Status = StatusFailed
					stat.Error = "no form query config"
					stat.DurationSec = time.Since(start).Seconds()
					mu.Lock()
					results = append(results, stat)
					mu.Unlock()
					return
				}

				// 2. Parse field keys for row mapping
				var fieldKeyList []string
				if formQuery.FieldKeys != "" {
					for _, k := range strings.Split(formQuery.FieldKeys, ",") {
						if k := strings.TrimSpace(k); k != "" {
							fieldKeyList = append(fieldKeyList, k)
						}
					}
				}

				// 3. Build filter (add incremental time filter if needed)
				baseFilter := formQuery.GetFilter()
				effectiveFilter := baseFilter

				if syncType == "incremental" {
					// Get increment field for this table/form
					incField := config.GetIncrementField(stat.TableName, formName)

					// Get last sync time from DB
					lastTime, err := db.GetLastSyncTime(stat.TableName)
					if err != nil {
						log.Printf("Warning: failed to get last sync time for %s: %v, falling back to full sync", stat.TableName, err)
					} else if lastTime != "" {
						timeFilter := fmt.Sprintf("%s > '%s'", incField, lastTime)
						if baseFilter != "" {
							effectiveFilter = baseFilter + " AND " + timeFilter
						} else {
							effectiveFilter = timeFilter
						}
						log.Printf("[INCREMENTAL] %s: using filter '%s' (last sync: %s)", formName, effectiveFilter, lastTime)
					} else {
						log.Printf("[INCREMENTAL] %s: no last sync time found, doing full sync", formName)
					}
				}

				if e.fetchRows == nil && formName != "科目余额表" && formName != "即时库存" && len(cursorKeysForForm(formName)) > 0 {
					e.syncCursorForm(ctx, fetchCtx, formName, stat.TableName, formQuery, fieldKeyList, effectiveFilter, syncType, dryRun, &stat)
					if stat.Status == StatusSuccess && GetFormPriority(formName) == 2 && !dryRun {
						if err := gormdb.ClearCheckpoint(formName); err != nil {
							log.Printf("[CHECKPOINT] Warning: failed to clear cursor checkpoint for %s: %v", formName, err)
						}
					}
					stat.DurationSec = time.Since(start).Seconds()
					if stat.Status == "" {
						stat.Status = StatusSuccess
					}
					mu.Lock()
					results = append(results, stat)
					e.mu.Lock()
					e.progress = len(results) * 100 / len(forms)
					e.mu.Unlock()
					mu.Unlock()
					// 不在此输出单个表单完成日志，等所有表单完成后统一汇总（原因：避免中途刷屏）
					return
				}

				// 4. Check checkpoint for large tables (Group 2) - 断点续传
				startRow := 0
				priority := GetFormPriority(formName)
				if priority == 2 {
					cp, checkpointErr := gormdb.GetCheckpoint(formName)
					if checkpointErr != nil {
						stat.Status = StatusFailed
						stat.ErrorCount = 1
						stat.Error = fmt.Sprintf("checkpoint load failed: %v", checkpointErr)
						stat.DurationSec = time.Since(start).Seconds()
						mu.Lock()
						results = append(results, stat)
						mu.Unlock()
						return
					}
					if cp != nil && cp.LastPosition > 0 {
						belongs, belongsErr := e.checkpointBelongsToRun(cp, runID)
						if belongsErr != nil {
							stat.Status = StatusFailed
							stat.ErrorCount = 1
							stat.Error = fmt.Sprintf("checkpoint identity validation failed: %v", belongsErr)
							stat.DurationSec = time.Since(start).Seconds()
							mu.Lock()
							results = append(results, stat)
							mu.Unlock()
							return
						}
						if belongs {
							startRow = int(cp.LastPosition)
							log.Printf("[CHECKPOINT] Resuming %s from position %d", formName, startRow)
							e.logMsg(formName, "INFO", fmt.Sprintf("从断点继续: position=%d", startRow))
						}
					}
				}

				// 5. Query from Kingdee
				// 科目余额表走专用 GetSysReportData API（按月同步）
				var result *kind.QueryResult
				var err error

				if e.fetchRows != nil {
					result, err = e.fetchRows(fetchCtx, formName, startRow)
				} else if formName == "科目余额表" {
					e.logMsg(formName, "INFO", "使用 GetSysReportData API 按月同步...")
					client := kind.NewKingdeeClient()
					endYear, endPeriod := accountBalanceEndPeriod(time.Now())
					abParams := kind.AccountBalanceParams{
						AcctBookID:    "002",
						Currency:      "1",
						StartYear:     2025,
						StartPeriod:   1,
						EndYear:       endYear,
						EndPeriod:     endPeriod,
						BalanceLevel:  4,
						ShowDetail:    true,
						ShowForbidden: true,
						ShowZero:      true,
						OnMonthFetched: func(year, period, rowsInMonth, totalRows int) {
							msg := fmt.Sprintf("月 %d-%02d: %d 条 (累计 %d 条)", year, period, rowsInMonth, totalRows)
							e.logMsg(formName, "INFO", msg)
						},
					}
					result, err = client.QueryAccountBalanceContext(fetchCtx, abParams)
				} else {
					queryParams := kind.QueryParams{
						FormID:       formQuery.FormID,
						FieldKeys:    formQuery.FieldKeys,
						Filter:       effectiveFilter,
						Limit:        0,
						StartRow:     startRow,
						FieldKeyList: fieldKeyList,
					}

					e.logMsg(formName, "INFO", "正在查询金蝶 API...")

					queryParams.ProgressCallback = func(total int, page int) {
						msg := fmt.Sprintf("拉取进度: %d 条 (第 %d 页)", total, page)
						e.logMsg(formName, "INFO", msg)
					}

					client := kind.NewKingdeeClient()
					result, err = client.QueryDataContext(fetchCtx, queryParams)
				}
				if err != nil {
					log.Printf("Failed to query %s: %v", formName, err)
					if ctx.Err() != nil || fetchCtx.Err() != nil || e.isFetchStopped() {
						stat.Status = StatusStopped
						stat.Error = "sync stopped"
					} else {
						e.logMsg(formName, "ERROR", "查询失败: "+err.Error())
						stat.Status = StatusFailed
						stat.ErrorCount = 1
						stat.Error = err.Error()
					}
					stat.DurationSec = time.Since(start).Seconds()
					mu.Lock()
					results = append(results, stat)
					mu.Unlock()
					return
				}
				if ctx.Err() != nil {
					stat.Status = StatusStopped
					stat.Error = "sync stopped"
					stat.DurationSec = time.Since(start).Seconds()
					mu.Lock()
					results = append(results, stat)
					mu.Unlock()
					return
				}

				if len(result.Rows) == 0 {
					log.Printf("No data returned for %s", formName)
					e.logMsg(formName, "WARN", "源端返回空结果")
					// Full sync with empty source: mark as failed to prevent
					// accidental target table clearing. Only explicit reset mode
					// or manually confirmed empty source should clear targets.
					if syncType == "full" {
						stat.Status = StatusFailed
						stat.Error = "full sync returned empty source; skipped to prevent accidental data loss"
						stat.ErrorCount = 1
						e.logMsg(formName, "WARN", "全量同步源端为空，已跳过以防止数据丢失")
						// Do NOT clear checkpoint on failure — preserve recovery state.
					} else {
						stat.Status = StatusSuccess
						if priority == 2 && !dryRun {
							if err := gormdb.ClearCheckpoint(formName); err != nil {
								log.Printf("[CHECKPOINT] Warning: failed to clear checkpoint for %s: %v", formName, err)
							}
						}
					}
					stat.DurationSec = time.Since(start).Seconds()
					mu.Lock()
					results = append(results, stat)
					e.mu.Lock()
					e.progress = len(results) * 100 / len(forms)
					e.mu.Unlock()
					mu.Unlock()
					return
				}

				stat.FetchedCount = len(result.Rows)
				fieldKeyList = appendDerivedWriteFields(formName, fieldKeyList)
				e.logMsg(formName, "INFO", fmt.Sprintf("查询到 %d 条数据", len(result.Rows)))

				log.Printf("[SYNC] %s: fetched %d rows", formName, len(result.Rows))

				// 4. Upsert to DB (or dry-run)
				if dryRun {
					// Dry-run logs only aggregate counts; row values may contain business data.
					log.Printf("[DRY-RUN] Simulated write for %s: rows=%d", formName, stat.FetchedCount)
					e.logMsg(formName, "INFO", fmt.Sprintf("模拟写入 %d 条数据", stat.FetchedCount))
					stat.InsertedCount = stat.FetchedCount
				} else {
					// Reset mode and snapshot forms (科目余额表/即时库存): truncate before write.
					// （原因：快照表每次都需要全量覆盖，无论同步模式）
					isSnapshot := formName == "科目余额表" || formName == "即时库存"
					if (syncType == "reset" || isSnapshot) && len(result.Rows) > 0 {
						TableName := stat.TableName
						if isSnapshot {
							log.Printf("[TRUNCATE] snapshot form: truncating %s before write", TableName)
							e.logMsg(formName, "INFO", fmt.Sprintf("快照表：清空表 %s 后写入", TableName))
						} else {
							log.Printf("[TRUNCATE] reset mode: truncating %s after fetch, before write", TableName)
							e.logMsg(formName, "INFO", fmt.Sprintf("重置模式：清空表 %s", TableName))
						}
						if db.DB == nil {
							log.Printf("[TRUNCATE] Error: db.DB is nil, cannot truncate %s; aborting form", TableName)
							e.logMsg(formName, "ERROR", "数据库未连接，无法清空表，跳过此表单")
							stat.Status = StatusFailed
							stat.ErrorCount = 1
							stat.Error = "db.DB is nil, cannot truncate"
						} else if _, err := db.DB.Exec("TRUNCATE TABLE `" + TableName + "`"); err != nil {
							log.Printf("[TRUNCATE] Error: failed to truncate %s: %v; aborting form", TableName, err)
							e.logMsg(formName, "ERROR", "清空表失败: "+err.Error())
							stat.Status = StatusFailed
							stat.ErrorCount = 1
							stat.Error = "truncate failed: " + err.Error()
						} else {
							e.logMsg(formName, "INFO", "表已清空")
						}
					}
					// Skip write if truncate failed
					if stat.Status == StatusFailed {
						// already marked above
					} else {
						e.logMsg(formName, "INFO", "正在写入数据库...")
						// Aggregate snapshot forms by PK before write to deduplicate rows.
						// （原因：金蝶即时库存 API 可能返回同一物料+仓库的多行碎片化数据，需聚合）
						writeRows := result.Rows
						// （原因：聚合逻辑仅适用于即时库存，科目余额表是报表数据，每行已是完整记录，不应聚合）
						if formName == "即时库存" {
							writeRows = aggregateRowsByKey(result.Rows, fieldKeyList, formQuery.FieldMap)
							if len(writeRows) < len(result.Rows) {
								log.Printf("[AGGREGATE] %s: %d rows aggregated to %d rows", formName, len(result.Rows), len(writeRows))
							}
						}
						inserted, err := e.writeRowsWithContext(ctx, stat.TableName, writeRows, fieldKeyList, formQuery.FieldMap)
						if err != nil {
							log.Printf("Failed to upsert %s: %v", formName, err)
							e.logMsg(formName, "ERROR", "写入失败: "+err.Error())
							stat.Status = StatusFailed
							stat.ErrorCount = 1
							stat.Error = err.Error()
						} else if ctx.Err() != nil {
							// A shutdown deadline may cancel the run context while a
							// writer returns successfully after its request was submitted.
							// Do not advance or clear the checkpoint in that case.
							stat.Status = StatusStopped
							stat.Error = "sync stopped"
						} else {
							stat.InsertedCount = inserted
							e.logMsg(formName, "INFO", fmt.Sprintf("写入完成: %d 条", inserted))

							// Save checkpoint for large tables after successful write
							if priority == 2 && !dryRun {
								newPosition := int64(startRow + len(result.Rows))
								if err := gormdb.SaveCheckpointForRun(formName, runID, newPosition, ""); err != nil {
									log.Printf("[CHECKPOINT] Warning: failed to save checkpoint for %s: %v", formName, err)
								} else {
									log.Printf("[CHECKPOINT] Saved checkpoint for %s: position=%d", formName, newPosition)
								}
							}

							// Full sync: delete rows that exist in DB but not in Kingdee.
							// Uses SnapshotManager for validation and safe deletion.
							currentRecovery, currentRecoveryErr := e.isRecoveryRun(runID)
							if currentRecoveryErr != nil {
								stat.Status = StatusFailed
								stat.ErrorCount = 1
								stat.Error = fmt.Sprintf("sync run identity validation failed before cleanup: %v", currentRecoveryErr)
							} else if syncType == "full" && !currentRecovery && !e.isCleanupDisabled() && len(result.Rows) > 0 {
								deleted, delErr := e.deleteOrphanedWithSnapshot(ctx, runID, formName, stat.TableName, result.Rows, fieldKeyList, formQuery.FieldMap, inserted)
								if delErr != nil {
									log.Printf("Warning: failed to delete orphaned rows for %s: %v", formName, delErr)
									e.logMsg(formName, "WARN", "孤儿删除失败: "+delErr.Error())
									// Orphan deletion failure means the snapshot is incomplete;
									// mark the form as failed so the run status reflects it.
									stat.Status = StatusFailed
									stat.ErrorCount = 1
									stat.Error = "orphan deletion failed: " + delErr.Error()
								} else if deleted > 0 {
									log.Printf("[FULL-SYNC] Deleted %d orphaned rows from %s (removed in Kingdee)", deleted, stat.TableName)
									e.logMsg(formName, "INFO", fmt.Sprintf("删除 %d 条孤儿记录", deleted))
								}
							}
						}
					}
				}

				if stat.Status == "" {
					stat.Status = StatusSuccess
				}

				// Clear checkpoint on successful completion
				if priority == 2 && stat.Status == StatusSuccess && !dryRun {
					if err := gormdb.ClearCheckpoint(formName); err != nil {
						log.Printf("[CHECKPOINT] Warning: failed to clear checkpoint for %s: %v", formName, err)
					} else {
						log.Printf("[CHECKPOINT] Cleared checkpoint for completed form %s", formName)
					}
				}

				stat.DurationSec = time.Since(start).Seconds()

				mu.Lock()
				results = append(results, stat)
				e.mu.Lock()
				e.progress = len(results) * 100 / len(forms)
				e.mu.Unlock()
				mu.Unlock()

				log.Printf("[%s] Synced %s: fetched=%d, inserted=%d, errors=%d, duration=%.2fs",
					mode, formName, stat.FetchedCount, stat.InsertedCount, stat.ErrorCount, stat.DurationSec)
				// 不在此输出单个表单完成日志，等所有表单完成后统一汇总（原因：避免中途刷屏，用户更关心最终汇总）
			}(form)
		}

		wg.Wait()
	}

	var totalRecords, totalInserted, totalErrors int
	status := StatusSuccess
	failedForms := 0
	successForms := 0
	for _, r := range results {
		totalRecords += r.FetchedCount
		totalInserted += r.InsertedCount
		totalErrors += r.ErrorCount
		if r.Status == StatusSuccess {
			successForms++
		} else {
			failedForms++
		}
	}
	// 统一输出汇总日志（原因：避免中途刷屏，用户更关心最终汇总）
	e.logMsg("", "INFO", fmt.Sprintf("=== 同步完成 ==="))
	for _, r := range results {
		icon := "✅"
		if r.Status != StatusSuccess {
			icon = "❌"
		}
		e.logMsg(r.FormName, "INFO", fmt.Sprintf("%s 拉取 %d, 写入 %d, 错误 %d, 耗时 %.1fs",
			icon, r.FetchedCount, r.InsertedCount, r.ErrorCount, r.DurationSec))
	}
	e.logMsg("", "INFO", fmt.Sprintf("总计: %d 个表单, 拉取 %d, 写入 %d, 错误 %d",
		len(results), totalRecords, totalInserted, totalErrors))
	if failedForms > 0 && successForms == 0 {
		status = StatusFailed
	} else if failedForms > 0 {
		status = StatusPartial
	}

	e.mu.Lock()
	var currentRun gormdb.SyncRun
	var abnormalPersistErr error
	if err := gormdb.DB.Where("run_id = ?", runID).First(&currentRun).Error; err == nil {
		currentStatus := contract.SyncStatus(currentRun.Status)
		ctxErr := ctx.Err()
		if ctxErr != nil && !e.stopRequested {
			message := fmt.Sprintf("abnormal exit: sync context ended: %v", ctxErr)
			if err := gormdb.MarkSyncRunAbnormalExitWithRetry(runID, message); err != nil {
				abnormalPersistErr = err
				log.Printf("[SYNC] Failed to mark context-ended run %s abnormal: %v", runID, err)
			}
			currentStatus = contract.StatusFailedAbnormalExit
		} else if ctxErr != nil && e.stopRequested && currentStatus == contract.StatusRunning {
			if err := gormdb.UpdateSyncRunStatus(runID, string(contract.StatusStopping), "sync context canceled by user"); err != nil {
				log.Printf("[SYNC] Failed to enter stopping for %s: %v", runID, err)
			} else {
				currentStatus = contract.StatusStopping
			}
		}
		if currentStatus == contract.StatusStopping {
			if e.stopRequested || ctxErr == nil {
				status = StatusStopped
			} else {
				status = StatusFailedAbnormalExit
			}
		} else if contract.IsTerminalStatus(currentStatus) {
			status = SyncStatus(currentStatus)
		}
	}

	result.Status = status
	result.EndTime = time.Now()
	result.DurationSec = time.Since(result.StartTime).Seconds()
	result.TotalRecords = totalInserted
	result.FormStats = results
	if status == StatusStopped {
		result.Message = "同步已停止"
	} else if status == StatusFailedAbnormalExit {
		result.Message = fmt.Sprintf("异常退出: 同步上下文结束: %v", ctx.Err())
	} else {
		result.Message = fmt.Sprintf("[%s] 同步完成: %d 个表单共 %d 条记录 (拉取 %d 条, 错误 %d 条)",
			syncTypeLabel(syncType), len(forms), totalInserted, totalRecords, totalErrors)
	}
	e.progress = 100

	// RequestStop and this block share e.mu, so the first finalization decision wins.
	dbStatus := string(status)
	var finishErr error
	if status != StatusFailedAbnormalExit {
		finishErr = gormdb.FinishSyncRunWithRetry(runID, dbStatus, result.DurationSec,
			int64(totalRecords), int64(totalInserted), int64(totalErrors),
			len(forms), successForms, failedForms, "")
	} else {
		finishErr = abnormalPersistErr
	}
	if finishErr != nil {
		log.Printf("[SYNC] Failed to finish sync_run %s after retries: %v", runID, finishErr)
		result.Status = StatusFailedAbnormalExit
		result.Message = fmt.Sprintf("abnormal exit: failed to persist final state: %v", finishErr)
		e.current.Status = StatusFailedAbnormalExit
		e.current.Message = result.Message
	} else {
		log.Printf("[SYNC] Finished sync_run %s: status=%s", runID, dbStatus)
		if persisted, err := gormdb.GetSyncRun(runID); err == nil {
			result.Status = SyncStatus(persisted.Status)
		} else {
			log.Printf("[SYNC] Failed to reload finished sync_run %s: %v", runID, err)
		}
	}
	e.mu.Unlock()

	log.Printf("[%s] Sync completed: status=%s, fetched=%d, inserted=%d, errors=%d, duration=%.2fs",
		mode, status, totalRecords, totalInserted, totalErrors, result.DurationSec)
	return result, nil
}

func (e *SyncEngine) syncCursorForm(ctx, fetchCtx context.Context, formName, tableName string, formQuery config.FormQuery, fieldKeys []string, baseFilter, syncType string, dryRun bool, stat *FormStat) {
	cursorKeys := cursorKeysForForm(formName)
	if err := ValidateCursorKeyFields(fieldKeys, cursorKeys); err != nil {
		stat.Status, stat.ErrorCount, stat.Error = StatusFailed, 1, err.Error()
		return
	}
	pageSize := config.Get().Kingdee.PageSize
	if pageSize <= 0 || pageSize > 10000 {
		pageSize = 10000
	}
	client := kind.NewKingdeeClient()
	var previous []interface{}
	truncated := false
	for page := 1; ; page++ {
		filter := baseFilter
		if len(previous) > 0 {
			var err error
			filter, err = BuildCursorFilter(baseFilter, cursorKeys, previous)
			if err != nil {
				stat.Status, stat.ErrorCount, stat.Error = StatusFailed, 1, fmt.Sprintf("cursor page %d filter: %v", page, err)
				return
			}
		}
		result, err := client.QueryDataContext(fetchCtx, kind.QueryParams{FormID: formQuery.FormID, FieldKeys: formQuery.FieldKeys, FieldKeyList: fieldKeys, Filter: filter, Limit: pageSize, SinglePage: true, OrderString: CursorOrderString(cursorKeys)})
		if err != nil {
			// Retry up to 3 times for network errors (connection reset, timeout, etc.)
			retried := false
			for attempt := 0; attempt < 3 && !retried; attempt++ {
				backoff := time.Duration(attempt+1) * time.Second
				e.logMsg(formName, "WARNING", fmt.Sprintf("cursor page %d error: %v, retrying in %v (attempt %d/3)", page, err, backoff, attempt+1))
				time.Sleep(backoff)
				result, err = client.QueryDataContext(fetchCtx, kind.QueryParams{FormID: formQuery.FormID, FieldKeys: formQuery.FieldKeys, FieldKeyList: fieldKeys, Filter: filter, Limit: pageSize, SinglePage: true, OrderString: CursorOrderString(cursorKeys)})
				if err == nil {
					retried = true
					e.logMsg(formName, "INFO", fmt.Sprintf("cursor page %d retry successful after %d attempts", page, attempt+1))
					break
				}
			}
			if err != nil {
				stat.Status, stat.ErrorCount, stat.Error = StatusFailed, 1, fmt.Sprintf("cursor page %d: %v", page, err)
				return
			}
		}
		if len(result.Rows) == 0 {
			break
		}
		current, err := ValidateCursorPage(result.Rows, cursorKeys, previous)
		if err != nil {
			stat.Status, stat.ErrorCount, stat.Error = StatusFailed, 1, fmt.Sprintf("cursor page %d: %v", page, err)
			return
		}
		if !truncated && syncType == "reset" && !dryRun {
			if db.DB == nil {
				stat.Status, stat.ErrorCount, stat.Error = StatusFailed, 1, "database not initialized"
				return
			}
			if _, err := db.DB.Exec("TRUNCATE TABLE `" + tableName + "`"); err != nil {
				stat.Status, stat.ErrorCount, stat.Error = StatusFailed, 1, "truncate failed: "+err.Error()
				return
			}
			truncated = true
		}
		stat.FetchedCount += len(result.Rows)
		if dryRun {
			stat.InsertedCount += len(result.Rows)
		} else {
			inserted, err := e.writeRowsWithContext(ctx, tableName, result.Rows, appendDerivedWriteFields(formName, fieldKeys), formQuery.FieldMap)
			if err != nil {
				stat.Status, stat.ErrorCount = StatusFailed, 1
				stat.Error = fmt.Sprintf("cursor page %d write: inserted=%d err=%v", page, inserted, err)
				return
			}
			stat.InsertedCount += inserted
		}
		previous = current
		e.logMsg(formName, "INFO", fmt.Sprintf("同步进度: %d 条 (第 %d 页)", stat.FetchedCount, page))
		if len(result.Rows) < pageSize {
			break
		}
	}
	if stat.FetchedCount == 0 && syncType == "full" {
		stat.Status, stat.ErrorCount, stat.Error = StatusFailed, 1, "full sync returned empty source"
		return
	}
	if stat.InsertedCount < stat.FetchedCount {
		log.Printf("[SYNC] Warning: fetched/inserted mismatch for %s: fetched=%d inserted=%d (minor Doris filtering)", formName, stat.FetchedCount, stat.InsertedCount)
		return
	}
	if !dryRun && syncType == "reset" && stat.FetchedCount > 0 {
		if db.DB == nil {
			stat.Status, stat.ErrorCount, stat.Error = StatusFailed, 1, "database not initialized"
			return
		}
		var targetCount int
		if err := db.DB.QueryRowContext(ctx, "SELECT COUNT(*) FROM `"+tableName+"`").Scan(&targetCount); err != nil {
			stat.Status, stat.ErrorCount, stat.Error = StatusFailed, 1, "target count failed: "+err.Error()
			return
		}
		if targetCount != stat.FetchedCount {
			stat.Status, stat.ErrorCount, stat.Error = StatusFailed, 1, fmt.Sprintf("cursor target count mismatch: fetched=%d target=%d", stat.FetchedCount, targetCount)
			return
		}
	}
	stat.Status = StatusSuccess
}

// aggregateRowsByKey deduplicates rows by primary key, summing numeric columns.
// Used for snapshot forms (即时库存) where the Kingdee API may return multiple
// fragment rows for the same (material, warehouse) combination.
func aggregateRowsByKey(rows []map[string]interface{}, fieldKeys []string, fieldMap map[string]string) []map[string]interface{} {
	if len(rows) <= 1 {
		return rows
	}

	// Determine the aggregate key columns (PK columns from fieldKeys).
	// For 即时库存: FMATERIALID, FSTOCKID
	// The key columns are the first 2 fields that map to PK columns.
	keyCols := []string{"FMATERIALID", "FSTOCKID"}
	// Numeric columns to sum
	sumCols := []string{"FBASEQTY"}

	// Build key -> aggregated row map
	agg := make(map[string]map[string]interface{})
	order := []string{}
	for _, row := range rows {
		keyParts := make([]string, 0, len(keyCols))
		for _, kc := range keyCols {
			val := row[kc]
			if val == nil {
				keyParts = append(keyParts, "<nil>")
			} else {
				keyParts = append(keyParts, fmt.Sprintf("%v", val))
			}
		}
		key := strings.Join(keyParts, "|")
		if _, exists := agg[key]; !exists {
			agg[key] = make(map[string]interface{})
			// Copy all fields from first row
			for k, v := range row {
				agg[key][k] = v
			}
			order = append(order, key)
		} else {
			// Sum numeric columns
			for _, sc := range sumCols {
				existing := toFloat(agg[key][sc])
				newVal := toFloat(row[sc])
				agg[key][sc] = existing + newVal
			}
		}
	}

	result := make([]map[string]interface{}, 0, len(agg))
	for _, key := range order {
		result = append(result, agg[key])
	}
	return result
}

func toFloat(v interface{}) float64 {
	if v == nil {
		return 0
	}
	switch val := v.(type) {
	case float64:
		return val
	case float32:
		return float64(val)
	case int:
		return float64(val)
	case int64:
		return float64(val)
	default:
		return 0
	}
}

func accountBalanceEndPeriod(now time.Time) (int, int) {
	if now.Month() == time.January {
		return now.Year() - 1, 12
	}
	return now.Year(), int(now.Month()) - 1
}

// writeRows maps Kingdee fields to DB columns and delegates to the configured RowWriter.
// （原因：将列映射逻辑与具体写入实现解耦，通过 RowWriter 接口支持 Doris Stream Load）
func (e *SyncEngine) writeRows(tableName string, rows []map[string]interface{}, fieldKeys []string, fieldMap map[string]string) (int, error) {
	return e.writeRowsWithContext(context.Background(), tableName, rows, fieldKeys, fieldMap)
}

func (e *SyncEngine) writeRowsWithContext(ctx context.Context, tableName string, rows []map[string]interface{}, fieldKeys []string, fieldMap map[string]string) (int, error) {
	if e.writeRowsFunc != nil {
		return e.writeRowsFunc(ctx, tableName, rows, fieldKeys, fieldMap)
	}
	if db.DB == nil {
		return 0, fmt.Errorf("database not initialized")
	}

	if len(rows) == 0 {
		return 0, nil
	}

	// Get PK for this table
	pkStr := db.GetPrimaryKey(tableName)
	if pkStr == "" {
		return 0, fmt.Errorf("no primary key defined for table %s", tableName)
	}
	pkCols := strings.Split(pkStr, ",")
	for i := range pkCols {
		pkCols[i] = strings.TrimSpace(pkCols[i])
	}

	// Get existing columns in target table
	existingCols, err := e.getTableColumns(tableName)
	if err != nil {
		return 0, fmt.Errorf("failed to get table columns for %s: %w", tableName, err)
	}

	// Build Kingdee field -> DB column mapping (considering FieldMap config)
	// （原因：金蝶 API 返回的字段名如 "FGROUP.FNAME" 需要映射到数据库列 "FGROUP"）
	kingdeeToDB := make(map[string]string)
	for _, fk := range fieldKeys {
		fk = strings.TrimSpace(fk)
		if fk == "" {
			continue
		}
		// First check explicit field map
		if dbCol, ok := fieldMap[fk]; ok {
			if _, exists := existingCols[strings.ToUpper(dbCol)]; exists {
				kingdeeToDB[fk] = dbCol
				continue
			}
		}
		// Fallback: direct match by uppercase
		fkUpper := strings.ToUpper(fk)
		if actualName, ok := existingCols[fkUpper]; ok {
			kingdeeToDB[fk] = actualName
			continue
		}
		// For composite fields like "FMATERIALGROUP.fname", use the part before "." as DB column name.
		// （原因：金蝶 API 返回的关联字段如 FMATERIALGROUP.fname，Doris 中只存 FMATERIALGROUP 列）
		if dotIdx := strings.Index(fk, "."); dotIdx != -1 {
			baseField := strings.ToUpper(fk[:dotIdx])
			if actualName, ok := existingCols[baseField]; ok {
				kingdeeToDB[fk] = actualName
			}
		}
	}

	// Build ordered list of DB columns
	var cols []string
	for _, fk := range fieldKeys {
		fk = strings.TrimSpace(fk)
		if dbCol, ok := kingdeeToDB[fk]; ok {
			cols = append(cols, dbCol)
		}
	}

	if len(cols) == 0 {
		return 0, fmt.Errorf("no matching columns between Kingdee fields and table %s", tableName)
	}

	log.Printf("[SYNC-ENGINE] writeRows: table=%s, rows=%d, cols=%d, pkCols=%v", tableName, len(rows), len(cols), pkCols)

	// Delegate to the configured RowWriter (DorisWriter for mysql/Doris).
	// Pass kingdeeToDB so DorisWriter can look up values using Kingdee field names.
	return e.writer.Upsert(ctx, tableName, rows, cols, pkCols, kingdeeToDB)
}

// getTableColumns returns a map of column names (upper) to their actual stored names.
// This is used to normalize Kingdee field names (mixed case) to DB column names.
func (e *SyncEngine) getTableColumns(tableName string) (map[string]string, error) {
	if db.DB == nil {
		return nil, fmt.Errorf("database not initialized")
	}

	cols := make(map[string]string)
	// Use positional parameter (?) for MySQL/Doris compatibility
	rows, err := db.DB.Queryx(`
		SELECT COLUMN_NAME
		FROM INFORMATION_SCHEMA.COLUMNS
		WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ?
		ORDER BY ORDINAL_POSITION
	`, tableName)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	for rows.Next() {
		var colName string
		if err := rows.Scan(&colName); err != nil {
			return nil, err
		}
		// Map uppercase -> actual stored name
		cols[strings.ToUpper(colName)] = colName
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	return cols, nil
}

// deleteOrphanedWithSnapshot performs full-sync orphan deletion through the
// SnapshotManager, which validates the snapshot completeness before allowing
// any deletion. Recovery runs and cleanup-disabled states are explicitly skipped.
func (e *SyncEngine) deleteOrphanedWithSnapshot(
	ctx context.Context,
	runID, formName, tableName string,
	rows []map[string]interface{},
	fieldKeys []string,
	fieldMap map[string]string,
	inserted int,
) (int, error) {
	if e.writer == nil {
		return 0, fmt.Errorf("no writer configured")
	}

	// Get PK columns
	pkStr := db.GetPrimaryKey(tableName)
	if pkStr == "" {
		log.Printf("[SNAPSHOT] Skipping orphan delete for %s: no PK configured", tableName)
		return 0, nil
	}
	pkCols := strings.Split(pkStr, ",")
	for i := range pkCols {
		pkCols[i] = strings.TrimSpace(pkCols[i])
	}

	// Validate source data has valid PKs
	if err := ValidateSnapshotData(rows, pkCols, formName, fieldMap); err != nil {
		return 0, fmt.Errorf("snapshot data validation failed: %w", err)
	}

	// Create snapshot metadata — if this fails, refuse to delete.
	// We cannot prove write completeness without persisted snapshot state.
	mgr := NewSnapshotManager(runID, formName, tableName, e.writer)
	if err := mgr.Create(); err != nil {
		return 0, fmt.Errorf("snapshot creation failed, orphan deletion blocked: %w", err)
	}

	mgr.UpdateFetched(len(rows))
	mgr.UpdateWritten(inserted)
	mgr.UpdatePkCount(rows, pkCols)

	// Block deletion if actual write count differs from source count.
	// PartialSuccess from Doris means some rows were filtered; we cannot
	// safely assume the snapshot is complete.
	if inserted != len(rows) {
		log.Printf("[FULL-SYNC] Warning: partial write for %s: fetched=%d written=%d, skipping orphan deletion", tableName, len(rows), inserted)
		_ = mgr.Abort(fmt.Sprintf("partial write: fetched=%d written=%d", len(rows), inserted))
		return 0, nil
	}

	// Validate before deletion
	if err := mgr.Validate(rows, pkCols); err != nil {
		return 0, fmt.Errorf("snapshot validation failed, deletion blocked: %w", err)
	}

	// Safe to delete
	deleted, err := mgr.DeleteOrphaned(ctx, rows, pkCols)
	if err != nil {
		log.Printf("[FULL-SYNC] Warning: orphan deletion failed for %s: %v (data already synced, skipping)", tableName, err)
		return 0, nil
	}

	return deleted, nil
}
