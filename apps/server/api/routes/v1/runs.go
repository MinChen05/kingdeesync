package v1

import (
	"context"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	kingdeeDB "github.com/kingdee-sync/go/internal/db"
	"github.com/kingdee-sync/go/internal/gormdb"
	"github.com/kingdee-sync/go/internal/syncengine"
)

var (
	syncEng              *syncengine.SyncEngine
	activeTask           *activeSyncTask
	syncMutex            sync.Mutex
	lastSyncResult       *syncengine.SyncResult
	syncExecutionTimeout = configuredSyncExecutionTimeout()
	syncStopTimeout      = 30 * time.Second
)

type activeSyncTask struct {
	runID              string
	cancel             context.CancelFunc
	done               chan struct{}
	startedAt          time.Time
	stopWatcherStarted bool
}

func configuredSyncExecutionTimeout() time.Duration {
	const defaultTimeout = 30 * time.Minute
	raw := os.Getenv("SYNC_EXECUTION_TIMEOUT")
	if raw == "" {
		return defaultTimeout
	}
	value, err := time.ParseDuration(raw)
	if err != nil || value <= 0 {
		log.Printf("[Sync] Invalid SYNC_EXECUTION_TIMEOUT=%q; using default %s", raw, defaultTimeout)
	}
	return value
}

// InitRunsRoutes registers the v1 run-related endpoints.
func InitRunsRoutes(r *gin.Engine, engine *syncengine.SyncEngine) {
	syncEng = engine

	group := r.Group("/api/v1/runs")
	group.POST("", createRun)
	group.GET("", listRuns)
	group.GET("/:runId", getRun)
	group.GET("/:runId/events", listRunEvents)

	// Sync status & stop (used by frontend)
	r.GET("/api/v1/sync/status", getSyncStatus)
	r.POST("/api/v1/sync/stop", stopSync)
}

// ─── Create Run (Start Sync) ───

func createRun(c *gin.Context) {
	if syncEng == nil {
		WriteProblem(c, http.StatusServiceUnavailable, Problem{
			Code:    "SYNC_ENGINE_NOT_INITIALIZED",
			Message: "sync engine is not initialized",
		})
		return
	}
	if syncEng.IsShuttingDown() {
		WriteProblem(c, http.StatusServiceUnavailable, Problem{
			Code:    "SHUTTING_DOWN",
			Message: "service is shutting down",
		})
		return
	}
	if gormdb.DB == nil {
		WriteProblem(c, http.StatusServiceUnavailable, Problem{
			Code:    "DB_NOT_INITIALIZED",
			Message: "database is not initialized",
		})
		return
	}

	var req struct {
		Forms    []string `json:"forms"`
		SyncType string   `json:"sync_type"`
		DryRun   *bool    `json:"dry_run"`
	}
	req.SyncType = "incremental"
	if err := c.ShouldBindJSON(&req); err != nil && err != io.EOF {
		WriteProblem(c, http.StatusBadRequest, Problem{
			Code:    "INVALID_REQUEST",
			Message: "invalid sync request",
		})
		return
	}
	if req.SyncType == "" {
		req.SyncType = "incremental"
	}
	dryRun := req.DryRun != nil && *req.DryRun

	syncMutex.Lock()
	defer syncMutex.Unlock()

	currentRunID := ""
	if activeTask != nil {
		currentRunID = activeTask.runID
	} else if syncEng != nil {
		currentRunID = syncEng.CurrentRunID()
	}
	if currentRunID != "" {
		WriteProblem(c, http.StatusConflict, Problem{
			Code:    "ALREADY_RUNNING",
			Message: "a sync task is already running",
			Details: map[string]string{"run_id": currentRunID},
		})
		return
	}

	runID := uuid.NewString()
	if _, err := gormdb.CreateSyncRun(runID, "api", req.SyncType); err != nil {
		WriteProblem(c, http.StatusServiceUnavailable, Problem{
			Code:    "DB_ERROR",
			Message: "failed to persist sync run",
		})
		return
	}
	if err := syncEng.PrepareRun(runID, dryRun); err != nil {
		gormdb.FinishSyncRunWithRetry(runID, string(syncengine.StatusFailed), 0, 0, 0, 0, 0, 0, 0, err.Error())
		if err == syncengine.ErrSyncAlreadyRunning {
			currentRunID := syncEng.CurrentRunID()
			WriteProblem(c, http.StatusConflict, Problem{
				Code:    "ALREADY_RUNNING",
				Message: "a sync task is already running",
				Details: map[string]string{"run_id": currentRunID},
			})
			return
		}
		WriteProblem(c, http.StatusConflict, Problem{
			Code:    "RESERVATION_FAILED",
			Message: "failed to reserve sync engine",
		})
		return
	}

	ctx, cancel := context.WithTimeout(context.Background(), syncExecutionTimeout)
	task := &activeSyncTask{runID: runID, cancel: cancel, done: make(chan struct{}), startedAt: time.Now()}
	activeTask = task
	db := gormdb.DB
	go func() {
		defer cancel()
		defer close(task.done)
		defer func() {
			syncMutex.Lock()
			if activeTask != nil && activeTask.runID == runID {
				activeTask = nil
			}
			syncMutex.Unlock()
		}()

		syncEng.SetLogCallback(func(logRunID, formName, level, message string) {
			if db != nil {
				_ = db.Create(&gormdb.SyncError{RunID: logRunID, FormName: formName, Level: level, Message: message}).Error
			}
		}, runID)

		result, err := syncEng.SyncDataWithRunID(ctx, runID, req.Forms, req.SyncType, dryRun)
		if err != nil {
			finishSyncRunAfterError(runID, ctx, err)
			log.Printf("Sync failed for %s: %v", runID, err)
			return
		}
		syncMutex.Lock()
		lastSyncResult = result
		syncMutex.Unlock()

		for _, fs := range result.FormStats {
			_ = db.Create(&gormdb.SyncRunForm{
				RunID:           result.RunID,
				FormName:        fs.FormName,
				Status:          string(fs.Status),
				TotalRecords:    int64(fs.FetchedCount),
				Inserted:        int64(fs.InsertedCount),
				Failed:          int64(fs.ErrorCount),
				DurationSeconds: fs.DurationSec,
				ErrorMessage:    fs.Error,
			}).Error
			if fs.ErrorCount > 0 && fs.Error != "" {
				_ = db.Create(&gormdb.SyncError{RunID: result.RunID, FormName: fs.FormName, Level: "ERROR", Message: fs.Error}).Error
			}
			if fs.FormName == "即时库存" && fs.Status == syncengine.StatusSuccess && kingdeeDB.DB != nil {
				_, _ = kingdeeDB.DB.Exec("DELETE FROM stk_inventory WHERE FBASEQTY = 0")
			}
		}
		log.Printf("[Sync] Completed run %s: status=%s, forms=%d, duration=%.1fs", result.RunID, result.Status, len(result.FormStats), result.DurationSec)
	}()

	WriteData(c, http.StatusOK, Run{
		RunID:    runID,
		Status:   "running",
		SyncType: req.SyncType,
	})
}

func finishSyncRunAfterError(runID string, ctx context.Context, runErr error) {
	run, err := gormdb.GetSyncRun(runID)
	if err != nil || run.EndTime != nil {
		if err != nil {
			log.Printf("[Sync] Failed to load run %s after error: %v", runID, err)
			if syncEng != nil {
				syncEng.MarkAbnormalExit(runID, "abnormal exit: failed to load run after execution error")
			}
		}
		return
	}

	status := "failed"
	message := runErr.Error()
	if ctxErr := ctx.Err(); ctxErr != nil {
		if ctxErr == context.Canceled && run.Status == "stopping" {
			status = "stopped"
			message = "sync stopped"
		} else {
			status = "failed_abnormal_exit"
			message = fmt.Sprintf("abnormal exit: sync context ended: %v", ctxErr)
			_ = gormdb.MarkSyncRunAbnormalExitWithRetry(runID, message)
		}
	}
	if status == "failed_abnormal_exit" {
		if syncEng != nil {
			syncEng.MarkAbnormalExit(runID, message)
		}
		return
	}
	_ = gormdb.FinishSyncRunWithRetry(runID, status, 0, 0, 0, 0, 0, 0, 0, message)
}

// ─── Sync Status ───

func getSyncStatus(c *gin.Context) {
	runID := c.Query("run_id")
	if runID == "" {
		syncMutex.Lock()
		if activeTask != nil {
			runID = activeTask.runID
		}
		syncMutex.Unlock()
		if runID == "" && syncEng != nil {
			runID = syncEng.CurrentRunID()
		}
	}
	if runID == "" {
		WriteProblem(c, http.StatusNotFound, Problem{
			Code:    "NOT_FOUND",
			Message: "no active sync run",
		})
		return
	}

	if syncEng != nil {
		if snapshot, ok := syncEng.GetStatusSnapshot(runID); ok {
			returnStatus(c, snapshot)
			return
		}
	}

	run, err := gormdb.GetSyncRunContext(c.Request.Context(), runID)
	if err != nil {
		WriteProblem(c, http.StatusNotFound, Problem{
			Code:    "NOT_FOUND",
			Message: "sync run not found",
		})
		return
	}
	returnStatusFromDB(c, run)
}

func returnStatus(c *gin.Context, snapshot syncengine.StatusSnapshot) {
	WriteData(c, http.StatusOK, gin.H{
		"run_id":          snapshot.RunID,
		"status":          snapshot.Status,
		"progress":        snapshot.Progress,
		"current_form":    snapshot.CurrentForm,
		"message":         snapshot.Message,
		"elapsed_seconds": snapshot.Elapsed,
		"started_at":      snapshot.StartedAt,
	})
}

func returnStatusFromDB(c *gin.Context, run *gormdb.SyncRun) {
	elapsed := run.DurationSeconds
	if run.EndTime == nil {
		elapsed = time.Since(run.StartTime).Seconds()
	}
	progress := 0
	if run.Status != "running" && run.Status != "stopping" {
		progress = 100
	}
	WriteData(c, http.StatusOK, gin.H{
		"run_id":          run.RunID,
		"status":          run.Status,
		"progress":        progress,
		"current_form":    "",
		"message":         run.ErrorMessage,
		"elapsed_seconds": elapsed,
		"started_at":      run.StartTime,
	})
}

// ─── Stop Sync ───

func stopSync(c *gin.Context) {
	runID := c.Query("run_id")
	if runID == "" {
		// Also accept from body
		var body struct {
			RunID string `json:"run_id"`
		}
		_ = c.ShouldBindJSON(&body)
		runID = body.RunID
	}
	if runID == "" {
		WriteProblem(c, http.StatusBadRequest, Problem{
			Code:    "INVALID_PARAMS",
			Message: "run_id is required",
		})
		return
	}

	syncMutex.Lock()
	task := activeTask
	if task == nil || task.runID != runID {
		task = nil
	}
	syncMutex.Unlock()

	if task != nil && task.cancel == nil {
		WriteProblem(c, http.StatusConflict, Problem{
			Code:    "NOT_ACTIVE",
			Message: "sync run cannot be stopped",
		})
		return
	}
	if syncEng == nil || !syncEng.RequestStop(runID) {
		WriteProblem(c, http.StatusConflict, Problem{
			Code:    "NOT_ACTIVE",
			Message: "sync run cannot be stopped",
		})
		return
	}
	if task != nil {
		task.cancel()
		syncMutex.Lock()
		if activeTask == task && task.done != nil && !task.stopWatcherStarted {
			task.stopWatcherStarted = true
			go watchActiveTaskStop(task, syncStopTimeout)
		}
		syncMutex.Unlock()
	}
	WriteData(c, http.StatusOK, gin.H{"run_id": runID, "status": "stopping"})
}

func watchActiveTaskStop(task *activeSyncTask, timeout time.Duration) {
	timer := time.NewTimer(timeout)
	defer timer.Stop()
	select {
	case <-task.done:
		return
	case <-timer.C:
		message := "abnormal exit: stop timeout exceeded"
		_ = gormdb.MarkSyncRunAbnormalExitWithRetry(task.runID, message)
		if syncEng != nil {
			syncEng.MarkAbnormalExit(task.runID, message)
		}
		syncMutex.Lock()
		if activeTask == task {
			activeTask = nil
		}
		syncMutex.Unlock()
	}
}

// ─── List / Get / Events ───

// toV1Run converts a gormdb.SyncRun to the v1 Run DTO.
func toV1Run(r gormdb.SyncRun) Run {
	forms := make([]RunForm, len(r.Forms))
	for i, f := range r.Forms {
		forms[i] = RunForm{
			FormName:     f.FormName,
			Status:       f.Status,
			TotalRecords: f.TotalRecords,
			Inserted:     f.Inserted,
			Updated:      f.Updated,
			Deleted:      f.Deleted,
			Failed:       f.Failed,
			Skipped:      f.Skipped,
			DurationSec:  f.DurationSeconds,
			ErrorMessage: f.ErrorMessage,
		}
	}
	errors := make([]RunError, len(r.Errors))
	for i, e := range r.Errors {
		errors[i] = RunError{
			FormName:  e.FormName,
			Level:     e.Level,
			Message:   redactSyncLog(e.Message),
			Detail:    e.Detail,
			CreatedAt: formatTime(e.CreatedAt),
		}
	}
	return Run{
		RunID:          r.RunID,
		Status:         r.Status,
		SyncType:       r.SyncType,
		StartedAt:      formatTime(r.StartTime),
		FinishedAt:     formatEndTime(r.EndTime),
		DurationSec:    r.DurationSeconds,
		TotalRecords:   int(r.TotalRecords),
		SuccessRecords: int(r.SuccessRecords),
		FailedRecords:  int(r.FailedRecords),
		FormCount:      r.FormCount,
		SuccessForms:   r.SuccessForms,
		FailedForms:    r.FailedForms,
		ErrorMessage:   r.ErrorMessage,
		Forms:          forms,
		Errors:         errors,
	}
}

// toV1RunEvent converts a gormdb.SyncError to a redacted v1 RunEvent.
func toV1RunEvent(e gormdb.SyncError) RunEvent {
	return RunEvent{
		CreatedAt: formatTime(e.CreatedAt),
		FormName:  e.FormName,
		Level:     e.Level,
		Message:   redactSyncLog(e.Message),
	}
}

func formatTime(t time.Time) string {
	if t.IsZero() {
		return ""
	}
	return t.Local().Format("2006-01-02 15:04:05")
}

func formatEndTime(t *time.Time) string {
	if t == nil {
		return ""
	}
	return formatTime(*t)
}

func listRuns(c *gin.Context) {
	db := gormdb.DB
	if db == nil {
		WriteDataWithMeta(c, http.StatusOK, []Run{}, PageMeta{Total: 0})
		return
	}

	status := c.Query("status")
	syncType := c.Query("sync_type")
	fromDate := c.Query("from_date")
	toDate := c.Query("to_date")
	pageStr := c.DefaultQuery("page", "1")
	pageSizeStr := c.DefaultQuery("page_size", "20")

	page, _ := strconv.Atoi(pageStr)
	pageSize, _ := strconv.Atoi(pageSizeStr)
	if page < 1 {
		page = 1
	}
	if pageSize < 1 || pageSize > 100 {
		pageSize = 20
	}
	offset := (page - 1) * pageSize

	query := db.Model(&gormdb.SyncRun{}).Order("start_time DESC")

	if status != "" {
		query = query.Where("status = ?", status)
	}
	if syncType != "" {
		query = query.Where("sync_type = ?", syncType)
	}
	if fromDate != "" {
		if t, err := time.Parse("2006-01-02", fromDate); err == nil {
			query = query.Where("start_time >= ?", t)
		}
	}
	if toDate != "" {
		if t, err := time.Parse("2006-01-02", toDate); err == nil {
			query = query.Where("start_time < ?", t.Add(24*time.Hour))
		}
	}

	var total int64
	query.Count(&total)

	var runs []gormdb.SyncRun
	query.Offset(offset).Limit(pageSize).Find(&runs)

	result := make([]Run, len(runs))
	for i, r := range runs {
		result[i] = toV1Run(r)
	}

	WriteDataWithMeta(c, http.StatusOK, result, PageMeta{
		Page: page, PageSize: pageSize, Total: int(total),
	})
}

func getRun(c *gin.Context) {
	runID := c.Param("runId")
	db := gormdb.DB
	if db == nil {
		WriteProblem(c, http.StatusNotFound, Problem{
			Code:    "RUN_NOT_FOUND",
			Message: "run not found",
		})
		return
	}

	var run gormdb.SyncRun
	if err := db.Preload("Forms").Preload("Errors").Where("run_id = ?", runID).First(&run).Error; err != nil {
		WriteProblem(c, http.StatusNotFound, Problem{
			Code:    "RUN_NOT_FOUND",
			Message: "run not found",
		})
		return
	}

	WriteData(c, http.StatusOK, toV1Run(run))
}

func listRunEvents(c *gin.Context) {
	runID := c.Param("runId")
	db := gormdb.DB
	if db == nil {
		WriteData(c, http.StatusOK, []RunEvent{})
		return
	}

	// Verify run exists
	if _, err := gormdb.GetSyncRun(runID); err != nil {
		WriteProblem(c, http.StatusNotFound, Problem{
			Code:    "RUN_NOT_FOUND",
			Message: "run not found",
		})
		return
	}

	var logs []gormdb.SyncError
	if err := db.Where("run_id = ?", runID).Order("created_at ASC").Find(&logs).Error; err != nil {
		WriteProblem(c, http.StatusInternalServerError, Problem{
			Code:    "INTERNAL_ERROR",
			Message: "failed to load run events",
		})
		return
	}

	events := make([]RunEvent, len(logs))
	for i, e := range logs {
		events[i] = toV1RunEvent(e)
	}

	WriteData(c, http.StatusOK, events)
}
