package v1

import (
	"github.com/gin-gonic/gin"
	"github.com/kingdee-sync/go/internal/syncengine"
)

// InitRoutes registers all v1 endpoints on the given router group.
func InitRoutes(r *gin.Engine, engine *syncengine.SyncEngine) {
	group := r.Group("/api/v1")

	initOverviewRoutes(group)
	initScheduleRoutes(group)
	initResourceRoutes(group)
	initSystemRoutes(group)

	// Runs are registered via InitRunsRoutes which adds to /api/v1/runs
	InitRunsRoutes(r, engine)
}
