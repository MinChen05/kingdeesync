package schedule

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/kingdee-sync/go/internal/config"
	"github.com/kingdee-sync/go/internal/gormdb"
	"github.com/kingdee-sync/go/internal/syncengine"
	"github.com/robfig/cron/v3"
)

var (
	cronInstance        *cron.Cron
	engine              *syncengine.SyncEngine
	once                sync.Once
	mu                  sync.Mutex
	paused              bool
	schedulerRunTimeout = 30 * time.Minute
	scheduledSyncRunner = func(ctx context.Context, engine *syncengine.SyncEngine, runID string, forms []string, syncType string) (*syncengine.SyncResult, error) {
		return engine.SyncDataWithRunID(ctx, runID, forms, syncType, false)
	}
	scheduleRunCompletionHook func(runID string)
)

// Init initializes the scheduler with default jobs.
func Init(engine *syncengine.SyncEngine) error {
	var initErr error
	once.Do(func() {
		cronInstance = cron.New(cron.WithSeconds(), cron.WithChain(cron.Recover(cron.DefaultLogger)))

		// Create default jobs if not exist
		initErr = ensureDefaultJobs(engine)
		if initErr != nil {
			log.Printf("[Schedule] Failed to ensure default jobs: %v", initErr)
			return
		}

		// Load and register jobs
		initErr = loadJobs(engine)
		if initErr != nil {
			log.Printf("[Schedule] Failed to load jobs: %v", initErr)
			return
		}

		cronInstance.Start()
		log.Println("[Schedule] Scheduler started")
	})
	return initErr
}

// ensureDefaultJobs creates the default incremental and weekly full jobs.
func ensureDefaultJobs(engine *syncengine.SyncEngine) error {
	db := gormdb.DB
	if db == nil {
		return fmt.Errorf("gorm db not initialized")
	}

	cfg := config.Get()
	if cfg == nil {
		return fmt.Errorf("config not loaded")
	}

	// Use all configured form names from form-queries.json as default sync forms
	allForms := make([]string, 0, len(cfg.FormQueries))
	for name := range cfg.FormQueries {
		allForms = append(allForms, name)
	}

	// Default incremental job: every 20 minutes
	var incJob gormdb.ScheduleJob
	result := db.Where("name = ?", "default_incremental").First(&incJob)
	if result.Error != nil {
		// Create default incremental job
		formsJSON, _ := json.Marshal(allForms)

		incJob = gormdb.ScheduleJob{
			Name:     "default_incremental",
			CronExpr: "0 */20 * * * *",
			SyncType: "incremental",
			Forms:    string(formsJSON),
			Enabled:  false, // Disabled by default, user enables via UI
		}
		if err := db.Create(&incJob).Error; err != nil {
			return fmt.Errorf("create incremental job: %w", err)
		}
		log.Printf("[Schedule] Created default incremental job: %s with %d forms", incJob.CronExpr, len(allForms))
	} else if incJob.Forms == "" || incJob.Forms == "[]" {
		// Update existing job with empty forms
		formsJSON, _ := json.Marshal(allForms)
		incJob.Forms = string(formsJSON)
		db.Save(&incJob)
		log.Printf("[Schedule] Updated default incremental job with %d forms", len(allForms))
	}

	// Weekly full sync job: Sunday 2:00 AM
	var fullJob gormdb.ScheduleJob
	result = db.Where("name = ?", "weekly_full").First(&fullJob)
	if result.Error != nil {
		formsJSON, _ := json.Marshal(allForms)
		fullJob = gormdb.ScheduleJob{
			Name:     "weekly_full",
			CronExpr: "0 0 2 * * 0",
			SyncType: "full",
			Forms:    string(formsJSON),
			Enabled:  false,
		}
		if err := db.Create(&fullJob).Error; err != nil {
			return fmt.Errorf("create weekly full job: %w", err)
		}
		log.Printf("[Schedule] Created weekly full job: %s with %d forms", fullJob.CronExpr, len(allForms))
	} else if fullJob.Forms == "" || fullJob.Forms == "[]" {
		formsJSON, _ := json.Marshal(allForms)
		fullJob.Forms = string(formsJSON)
		db.Save(&fullJob)
		log.Printf("[Schedule] Updated weekly full job with %d forms", len(allForms))
	}

	return nil
}

// loadJobs loads all enabled jobs from database and registers them.
func loadJobs(engine *syncengine.SyncEngine) error {
	db := gormdb.DB
	if db == nil {
		return fmt.Errorf("gorm db not initialized")
	}

	var jobs []gormdb.ScheduleJob
	if err := db.Where("enabled = ?", true).Find(&jobs).Error; err != nil {
		return fmt.Errorf("query jobs: %w", err)
	}

	for _, job := range jobs {
		if err := registerJob(&job, engine); err != nil {
			log.Printf("[Schedule] Failed to register job %s: %v", job.Name, err)
			continue
		}
		log.Printf("[Schedule] Registered job: %s (%s)", job.Name, job.CronExpr)
	}

	return nil
}

// registerJob registers a single job to the cron scheduler.
func registerJob(job *gormdb.ScheduleJob, engine *syncengine.SyncEngine) error {
	if cronInstance == nil {
		return fmt.Errorf("cron not initialized")
	}

	entryID, err := cronInstance.AddFunc(job.CronExpr, func() {
		runJob(job, engine)
	})
	if err != nil {
		return fmt.Errorf("add cron job: %w", err)
	}

	// Update next run time
	next := cronInstance.Entry(entryID).Next
	mu.Lock()
	job.NextRunAt = &next
	gormdb.DB.Save(job)
	mu.Unlock()

	return nil
}

// runJob executes a scheduled sync job.
func runJob(job *gormdb.ScheduleJob, engine *syncengine.SyncEngine) {
	mu.Lock()
	isPaused := paused
	mu.Unlock()
	if isPaused {
		log.Printf("[Schedule] Skipping job %s because scheduler is paused", job.Name)
		return
	}
	log.Printf("[Schedule] Running job: %s (type=%s)", job.Name, job.SyncType)

	db := gormdb.DB
	if db == nil {
		log.Printf("[Schedule] Error: gorm db not initialized for job %s", job.Name)
		return
	}

	runID := uuid.New().String()

	// Create schedule run record
	scheduleRun := gormdb.ScheduleRun{
		JobID:     job.ID,
		RunID:     runID,
		Status:    "running",
		StartTime: time.Now(),
	}
	if err := db.Create(&scheduleRun).Error; err != nil {
		log.Printf("[Schedule] Failed to create schedule run for job %s: %v", job.Name, err)
		return
	}

	// Parse forms - if empty, use all configured forms
	var forms []string
	if job.Forms != "" && job.Forms != "[]" {
		json.Unmarshal([]byte(job.Forms), &forms)
	}
	if len(forms) == 0 {
		forms = config.GetConfiguredFormNames()
	}

	// Create sync run record
	now := time.Now()
	syncRun := &gormdb.SyncRun{
		RunID:     runID,
		TaskName:  job.Name,
		SyncType:  job.SyncType,
		Status:    "running",
		StartTime: now,
		FormCount: len(forms),
	}
	if err := db.Create(syncRun).Error; err != nil {
		log.Printf("[Schedule] Failed to create sync run: %v", err)
		failScheduleRun(&scheduleRun, fmt.Sprintf("failed to create sync run: %v", err))
		return
	}
	if err := engine.PrepareRun(runID, false); err != nil {
		log.Printf("[Schedule] Failed to reserve sync run %s: %v", runID, err)
		failSyncRun(syncRun, err.Error())
		failScheduleRun(&scheduleRun, err.Error())
		return
	}

	// Update job last run
	mu.Lock()
	job.LastRunAt = &now
	job.LastRunID = runID
	db.Save(job)
	mu.Unlock()

	// Trigger sync (non-blocking)
	go func() {
		defer notifyScheduleRunComplete(runID)
		ctx, cancel := context.WithTimeout(context.Background(), schedulerRunTimeout)
		defer cancel()
		done := make(chan struct{})
		var timeoutOnce sync.Once
		markTimeout := func() {
			timeoutOnce.Do(func() {
				message := "abnormal exit: scheduled sync timeout exceeded"
				if err := gormdb.MarkSyncRunAbnormalExitWithRetry(runID, message); err != nil {
					log.Printf("[Schedule] Failed to mark sync run %s abnormal after timeout: %v", runID, err)
				}
				if err := gormdb.MarkScheduleRunAbnormalExitWithRetry(runID, message); err != nil {
					log.Printf("[Schedule] Failed to finish schedule run %s after timeout: %v", runID, err)
				}
			})
		}
		go func() {
			timer := time.NewTimer(schedulerRunTimeout)
			defer timer.Stop()
			select {
			case <-done:
				return
			case <-timer.C:
				markTimeout()
			}
		}()
		defer close(done)
		defer func() {
			if r := recover(); r != nil {
				log.Printf("[Schedule] Panic in job %s: %v", job.Name, r)
				failSyncRun(syncRun, fmt.Sprintf("panic: %v", r))
				failScheduleRun(&scheduleRun, fmt.Sprintf("panic: %v", r))
			}
		}()

		// Execute sync via the pre-created run with a cancellable context. The
		// engine also keeps the child cancel function so API stop can cancel it.
		result, err := scheduledSyncRunner(ctx, engine, runID, forms, job.SyncType)
		if err != nil {
			log.Printf("[Schedule] Sync error for job %s: %v", job.Name, err)
			if ctx.Err() == context.DeadlineExceeded {
				markTimeout()
				return
			}
			if ctx.Err() == context.Canceled {
				failSyncRun(syncRun, err.Error())
				if finishErr := gormdb.FinishScheduleRunWithRetry(runID, "stopped", "scheduled sync stopped"); finishErr != nil {
					log.Printf("[Schedule] Failed to finish stopped schedule run %s: %v", runID, finishErr)
				}
				return
			}
			failSyncRun(syncRun, err.Error())
			failScheduleRun(&scheduleRun, err.Error())
			return
		}

		endTime := time.Now()
		duration := result.DurationSec

		// Aggregate stats from form results and write form-level records
		for _, fs := range result.FormStats {
			// Write form-level record
			if err := db.Create(&gormdb.SyncRunForm{
				RunID:           runID,
				FormName:        fs.FormName,
				Status:          string(fs.Status),
				TotalRecords:    int64(fs.FetchedCount),
				Inserted:        int64(fs.InsertedCount),
				Updated:         0,
				Failed:          int64(fs.ErrorCount),
				DurationSeconds: fs.DurationSec,
				ErrorMessage:    fs.Error,
			}).Error; err != nil {
				log.Printf("[Schedule] Failed to persist form result for run %s form %s: %v", runID, fs.FormName, err)
			}

			// Write errors if any
			if fs.ErrorCount > 0 && fs.Error != "" {
				if err := db.Create(&gormdb.SyncError{
					RunID:    runID,
					FormName: fs.FormName,
					Level:    "ERROR",
					Message:  fs.Error,
				}).Error; err != nil {
					log.Printf("[Schedule] Failed to persist form error for run %s form %s: %v", runID, fs.FormName, err)
				}
			}
		}

		// Update schedule run
		scheduleRun.EndTime = &endTime
		scheduleRun.Status = string(result.Status)
		if scheduleRun.Status == "" {
			scheduleRun.Status = string(syncengine.StatusFailed)
		}
		if result.Message != "" && result.Status != syncengine.StatusSuccess {
			scheduleRun.ErrorMessage = result.Message
		}
		if err := gormdb.FinishScheduleRunWithRetry(runID, scheduleRun.Status, scheduleRun.ErrorMessage); err != nil {
			log.Printf("[Schedule] Failed to finish schedule run %s: %v", runID, err)
		}

		finalStatus, summaryUpdated := updateJobSummaryFromScheduleRun(job, runID)
		if !summaryUpdated {
			finalStatus = scheduleRun.Status
		}

		log.Printf("[Schedule] Job %s completed: status=%s, duration=%.1fs", job.Name, finalStatus, duration)
	}()
}

// updateJobSummaryFromScheduleRun uses the durable ScheduleRun as the source
// of truth and only updates a job that still points at this run.
func updateJobSummaryFromScheduleRun(job *gormdb.ScheduleJob, runID string) (string, bool) {
	if job == nil {
		return "", false
	}
	persisted, err := gormdb.GetScheduleRun(runID)
	if err != nil {
		log.Printf("[Schedule] Failed to reload schedule run %s: %v", runID, err)
		return "", false
	}
	if persisted.JobID != job.ID || gormdb.DB == nil {
		return persisted.Status, false
	}
	result := gormdb.DB.Model(&gormdb.ScheduleJob{}).
		Where("id = ? AND last_run_id = ?", job.ID, runID).
		Update("last_status", persisted.Status)
	if result.Error != nil {
		log.Printf("[Schedule] Failed to update job summary for run %s: %v", runID, result.Error)
		return persisted.Status, false
	}
	if result.RowsAffected != 1 {
		return persisted.Status, false
	}
	mu.Lock()
	if job.LastRunID == runID {
		job.LastStatus = persisted.Status
	}
	mu.Unlock()
	return persisted.Status, true
}

func notifyScheduleRunComplete(runID string) {
	mu.Lock()
	hook := scheduleRunCompletionHook
	mu.Unlock()
	if hook != nil {
		hook(runID)
	}
}

func failSyncRun(run *gormdb.SyncRun, errMsg string) {
	if run == nil {
		return
	}
	if err := gormdb.FinishSyncRunWithRetry(run.RunID, string(syncengine.StatusFailed), 0, 0, 0, 0, 0, 0, 0, errMsg); err != nil {
		log.Printf("[Schedule] Failed to finish sync run %s: %v", run.RunID, err)
	}
}

func failScheduleRun(run *gormdb.ScheduleRun, errMsg string) {
	if run == nil {
		return
	}
	if err := gormdb.FinishScheduleRunWithRetry(run.RunID, "failed", errMsg); err != nil {
		log.Printf("[Schedule] Failed to finish schedule run %s: %v", run.RunID, err)
	}
}

// GetCron returns the cron instance for management.
func GetCron() *cron.Cron {
	return cronInstance
}

// Pause stops future cron dispatches. An already running job is coordinated by
// the shared SyncEngine shutdown controller.
func Pause() {
	mu.Lock()
	paused = true
	c := cronInstance
	mu.Unlock()
	if c != nil {
		c.Stop()
	}
}

func IsPaused() bool {
	mu.Lock()
	defer mu.Unlock()
	return paused
}

// SetEngine stores the sync engine reference for use by ReloadJobs.
func SetEngine(e *syncengine.SyncEngine) {
	engine = e
}

// ReloadJobs reloads all enabled jobs from database and updates cron.
func ReloadJobs() error {
	if cronInstance == nil || engine == nil {
		return fmt.Errorf("cron or engine not initialized")
	}

	db := gormdb.DB
	if db == nil {
		return fmt.Errorf("gorm db not initialized")
	}

	// Remove all existing entries
	entries := cronInstance.Entries()
	for i := len(entries) - 1; i >= 0; i-- {
		cronInstance.Remove(entries[i].ID)
	}

	// Load and register enabled jobs
	var jobs []gormdb.ScheduleJob
	if err := db.Where("enabled = ?", true).Find(&jobs).Error; err != nil {
		return fmt.Errorf("query jobs: %w", err)
	}

	for _, job := range jobs {
		if err := registerJob(&job, engine); err != nil {
			log.Printf("[Schedule] Failed to register job %s: %v", job.Name, err)
		} else {
			log.Printf("[Schedule] Registered job: %s (%s)", job.Name, job.CronExpr)
		}
	}

	return nil
}
