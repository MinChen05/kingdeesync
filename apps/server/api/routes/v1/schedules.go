package v1

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/kingdee-sync/go/internal/gormdb"
	"github.com/kingdee-sync/go/internal/schedule"
)

func initScheduleRoutes(group *gin.RouterGroup) {
	group.GET("/schedules", listSchedules)
	group.GET("/schedules/status", getSchedulerStatus)
	group.POST("/schedules", createSchedule)
	group.POST("/schedules/batch", batchScheduleAction)
	group.PUT("/schedules/:id", updateSchedule)
	group.DELETE("/schedules/:id", deleteSchedule)
	group.POST("/scheduler/start", startScheduler)
	group.POST("/scheduler/stop", stopScheduler)
}

func listSchedules(c *gin.Context) {
	db := gormdb.DB
	if db == nil {
		WriteData(c, http.StatusOK, []Schedule{})
		return
	}

	var jobs []gormdb.ScheduleJob
	db.Find(&jobs)

	result := make([]Schedule, len(jobs))
	for i, j := range jobs {
		result[i] = toV1Schedule(j)
	}

	WriteData(c, http.StatusOK, result)
}

func getSchedulerStatus(c *gin.Context) {
	cron := schedule.GetCron()
	// 原因：cron.Stop() 不清空 entries，仅看 entries 数量会让 stop 之后仍报 enabled=true；
	// 叠加 IsPaused 才能反映"调度是否真的会触发"
	enabled := cron != nil && !schedule.IsPaused() && len(cron.Entries()) > 0

	WriteData(c, http.StatusOK, SchedulerStatus{Enabled: enabled})
}

func createSchedule(c *gin.Context) {
	db := gormdb.DB
	if db == nil {
		WriteProblem(c, http.StatusServiceUnavailable, Problem{
			Code:    "INTERNAL_ERROR",
			Message: "database not initialized",
		})
		return
	}

	var req struct {
		Name     string `json:"name" binding:"required"`
		CronExpr string `json:"cron_expr" binding:"required"`
		SyncType string `json:"sync_type" binding:"required"`
		Forms    string `json:"forms"`
		Enabled  *bool  `json:"enabled"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		WriteProblem(c, http.StatusBadRequest, Problem{
			Code:    "INVALID_REQUEST",
			Message: "invalid request: " + err.Error(),
		})
		return
	}

	if req.SyncType != "incremental" && req.SyncType != "full" {
		WriteProblem(c, http.StatusBadRequest, Problem{
			Code:    "INVALID_REQUEST",
			Message: "sync_type must be 'incremental' or 'full'",
		})
		return
	}

	job := gormdb.ScheduleJob{
		Name:     req.Name,
		CronExpr: req.CronExpr,
		SyncType: req.SyncType,
		Forms:    req.Forms,
		Enabled:  req.Enabled != nil && *req.Enabled,
	}
	if err := db.Create(&job).Error; err != nil {
		WriteProblem(c, http.StatusInternalServerError, Problem{
			Code:    "INTERNAL_ERROR",
			Message: "failed to create schedule",
		})
		return
	}

	schedule.ReloadJobs()
	WriteData(c, http.StatusCreated, toV1Schedule(job))
}

func updateSchedule(c *gin.Context) {
	db := gormdb.DB
	if db == nil {
		WriteProblem(c, http.StatusServiceUnavailable, Problem{
			Code:    "INTERNAL_ERROR",
			Message: "database not initialized",
		})
		return
	}

	id := c.Param("id")
	var job gormdb.ScheduleJob
	if err := db.First(&job, id).Error; err != nil {
		WriteProblem(c, http.StatusNotFound, Problem{
			Code:    "SCHEDULE_NOT_FOUND",
			Message: "schedule not found",
		})
		return
	}

	var req struct {
		Name     *string `json:"name"`
		CronExpr *string `json:"cron_expr"`
		SyncType *string `json:"sync_type"`
		Forms    *string `json:"forms"`
		Enabled  *bool   `json:"enabled"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		WriteProblem(c, http.StatusBadRequest, Problem{
			Code:    "INVALID_REQUEST",
			Message: "invalid request: " + err.Error(),
		})
		return
	}

	if req.Name != nil {
		job.Name = *req.Name
	}
	if req.CronExpr != nil {
		job.CronExpr = *req.CronExpr
	}
	if req.SyncType != nil {
		job.SyncType = *req.SyncType
	}
	if req.Forms != nil {
		job.Forms = *req.Forms
	}
	if req.Enabled != nil {
		job.Enabled = *req.Enabled
	}

	if err := db.Save(&job).Error; err != nil {
		WriteProblem(c, http.StatusInternalServerError, Problem{
			Code:    "INTERNAL_ERROR",
			Message: "failed to update schedule",
		})
		return
	}

	schedule.ReloadJobs()
	WriteData(c, http.StatusOK, toV1Schedule(job))
}

func deleteSchedule(c *gin.Context) {
	db := gormdb.DB
	if db == nil {
		WriteProblem(c, http.StatusServiceUnavailable, Problem{
			Code:    "INTERNAL_ERROR",
			Message: "database not initialized",
		})
		return
	}

	id := c.Param("id")
	var job gormdb.ScheduleJob
	if err := db.First(&job, id).Error; err != nil {
		WriteProblem(c, http.StatusNotFound, Problem{
			Code:    "SCHEDULE_NOT_FOUND",
			Message: "schedule not found",
		})
		return
	}

	if err := db.Delete(&job).Error; err != nil {
		WriteProblem(c, http.StatusInternalServerError, Problem{
			Code:    "INTERNAL_ERROR",
			Message: "failed to delete schedule",
		})
		return
	}

	schedule.ReloadJobs()
	WriteData(c, http.StatusOK, gin.H{"message": "schedule deleted"})
}

func startScheduler(c *gin.Context) {
	// 原因：Resume 会清 paused、重启 cron 并重注册任务；旧实现只 ReloadJobs，
	// stop（cron.Stop）之后启动的条目不会再触发
	if err := schedule.Resume(); err != nil {
		WriteProblem(c, http.StatusInternalServerError, Problem{
			Code:    "INTERNAL_ERROR",
			Message: "failed to start scheduler: " + err.Error(),
		})
		return
	}
	WriteData(c, http.StatusOK, gin.H{"message": "scheduler started"})
}

func stopScheduler(c *gin.Context) {
	// 原因：Pause 同时置 paused 并 cron.Stop()；旧实现只 Stop，
	// 状态接口仍报 enabled=true，且重启前 reload 类操作可能带着半停状态运行
	schedule.Pause()
	WriteData(c, http.StatusOK, gin.H{"message": "scheduler stopped"})
}

func batchScheduleAction(c *gin.Context) {
	db := gormdb.DB
	if db == nil {
		WriteProblem(c, http.StatusServiceUnavailable, Problem{
			Code:    "INTERNAL_ERROR",
			Message: "database not initialized",
		})
		return
	}

	var req struct {
		Action string   `json:"action" binding:"required"` // enable, disable, delete
		IDs    []uint   `json:"ids" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		WriteProblem(c, http.StatusBadRequest, Problem{
			Code:    "INVALID_REQUEST",
			Message: "invalid request: " + err.Error(),
		})
		return
	}

	switch req.Action {
	case "enable":
		db.Model(&gormdb.ScheduleJob{}).Where("id IN ?", req.IDs).Update("enabled", true)
	case "disable":
		db.Model(&gormdb.ScheduleJob{}).Where("id IN ?", req.IDs).Update("enabled", false)
	case "delete":
		db.Delete(&gormdb.ScheduleJob{}, "id IN ?", req.IDs)
	default:
		WriteProblem(c, http.StatusBadRequest, Problem{
			Code:    "INVALID_REQUEST",
			Message: "action must be 'enable', 'disable', or 'delete'",
		})
		return
	}

	schedule.ReloadJobs()
	WriteData(c, http.StatusOK, gin.H{"message": "batch action completed", "action": req.Action})
}

func toV1Schedule(j gormdb.ScheduleJob) Schedule {
	return Schedule{
		ID:         int(j.ID),
		Name:       j.Name,
		CronExpr:   j.CronExpr,
		SyncType:   j.SyncType,
		Forms:      j.Forms,
		Enabled:    j.Enabled,
		CreatedAt:  formatTime(j.CreatedAt),
		UpdatedAt:  formatTime(j.UpdatedAt),
		LastRunAt:  formatEndTime(j.LastRunAt),
		NextRunAt:  formatEndTime(j.NextRunAt),
		LastStatus: j.LastStatus,
	}
}
