package v1

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/kingdee-sync/go/internal/dashboard"
)

func initOverviewRoutes(group *gin.RouterGroup) {
	group.GET("/overview", getOverview)
}

func getOverview(c *gin.Context) {
	today := dashboard.GetTodayStats()
	health := dashboard.GetHealthStatus()
	trend := dashboard.GetTrend7d()
	risks := dashboard.GetRiskItems(3)
	recent := dashboard.GetRecentRuns(10)

	overview := Overview{
		Today: TodayStats{
			SyncCount:      today.SyncCount,
			SuccessRate:    today.SuccessRate,
			FailCount:      today.FailCount,
			AvgDurationSec: today.AvgDuration,
			LastSyncTime:   today.LastSyncTime,
			YesterdayCount: today.YesterdaySyncCount,
			YesterdayRate:  today.YesterdayRate,
		},
		Health: HealthStatus{
			KingdeeAPI: &HealthItem{
				Status:     health.KingdeeAPI.Status,
				ResponseMs: &health.KingdeeAPI.ResponseMs,
				TodayCalls: &health.KingdeeAPI.TodayCalls,
			},
			Database: &HealthItem{
				Status:     health.Database.Status,
				ResponseMs: &health.Database.ResponseMs,
				ConnCount:  &health.Database.ConnCount,
			},
			Scheduler: &HealthItem{
				Status:   health.Scheduler.Status,
				Uptime:   health.Scheduler.Uptime,
				NextExec: health.Scheduler.NextExec,
			},
			LogService: &HealthItem{
				Status:     health.LogService.Status,
				WriteSpeed: health.LogService.WriteSpeed,
				LogSize:    health.LogService.LogSize,
			},
		},
		Trend:      toV1TrendDays(trend),
		Risks:      toV1RiskItems(risks),
		RecentRuns: toV1RunsFromRecent(recent),
	}

	WriteData(c, http.StatusOK, overview)
}

func toV1TrendDays(trend []dashboard.TrendDay) []TrendDay {
	if len(trend) == 0 {
		return []TrendDay{}
	}
	result := make([]TrendDay, len(trend))
	for i, t := range trend {
		result[i] = TrendDay{
			Date:        t.Date,
			SyncCount:   t.SyncCount,
			Records:     t.Records,
			SuccessRate: t.SuccessRate,
		}
	}
	return result
}

func toV1RiskItems(risks []dashboard.RiskItem) []RiskItem {
	if len(risks) == 0 {
		return []RiskItem{}
	}
	result := make([]RiskItem, len(risks))
	for i, r := range risks {
		result[i] = RiskItem{
			FormName:     r.Title,
			FailureCount: int(r.FailureCount),
			LastError:    r.Desc,
		}
	}
	return result
}

func toV1RunsFromRecent(recent []dashboard.RecentRun) []Run {
	if len(recent) == 0 {
		return []Run{}
	}
	result := make([]Run, len(recent))
	for i, r := range recent {
		result[i] = Run{
			Status:       r.Status,
			SyncType:     r.TaskName,
			StartedAt:    r.StartTime,
			DurationSec:  r.DurationSec,
			TotalRecords: r.RecordCount,
			FormCount:    r.FormCount,
		}
	}
	return result
}
