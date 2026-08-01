package v1

import (
	"encoding/json"
	"net/http"
	"sort"

	"github.com/gin-gonic/gin"
	"github.com/kingdee-sync/go/internal/config"
	"github.com/kingdee-sync/go/internal/datasource"
	"github.com/kingdee-sync/go/internal/gormdb"
	"gorm.io/gorm"
)

func initResourceRoutes(group *gin.RouterGroup) {
	group.GET("/forms", listForms)
	group.PUT("/forms/:name", updateForm)
	group.GET("/datasources", listDataSources)
}

func listForms(c *gin.Context) {
	db := gormdb.DB
	if db == nil {
		WriteProblem(c, http.StatusServiceUnavailable, Problem{
			Code:    "INTERNAL_ERROR",
			Message: "database not initialized",
		})
		return
	}

	// Load form query configs from DB
	var configs []gormdb.FormQueryConfig
	if err := db.Find(&configs).Error; err != nil {
		WriteProblem(c, http.StatusInternalServerError, Problem{
			Code:    "INTERNAL_ERROR",
			Message: "failed to load form configs",
		})
		return
	}

	disabled := gormdb.GetDisabledFormNames()
	statsMap := loadFormStats()

	forms := make([]Form, 0, len(configs))
	for _, cfg := range configs {
		stat := statsMap[cfg.FormName]

		var fieldMap map[string]string
		if cfg.FieldMap != "" {
			_ = json.Unmarshal([]byte(cfg.FieldMap), &fieldMap)
		}
		var defaultValues map[string]interface{}
		if cfg.DefaultValues != "" {
			_ = json.Unmarshal([]byte(cfg.DefaultValues), &defaultValues)
		}

		forms = append(forms, Form{
			FormName:      cfg.FormName,
			Enabled:       !disabled[cfg.FormName],
			LastSync:      stat.lastSync,
			LastStatus:    stat.lastStatus,
			RecordCount:   int(stat.totalRecords),
			ErrorCount:    int(stat.failedRecords),
			FormID:        cfg.FormID,
			FieldKeys:     cfg.FieldKeys,
			FilterString:  cfg.FilterString,
			FieldMap:      fieldMap,
			DefaultValues: defaultValues,
		})
	}

	// Also include forms from JSON config that are not yet in DB
	cfg := config.Get()
	if cfg != nil && cfg.FormQueries != nil {
		dbNames := make(map[string]bool)
		for _, f := range forms {
			dbNames[f.FormName] = true
		}
		for formName := range cfg.FormQueries {
			if !dbNames[formName] {
				stat := statsMap[formName]
				fq, _ := cfg.FormQueries[formName]
				forms = append(forms, Form{
					FormName:     formName,
					Enabled:      !disabled[formName],
					LastSync:     stat.lastSync,
					LastStatus:   stat.lastStatus,
					RecordCount:  int(stat.totalRecords),
					ErrorCount:   int(stat.failedRecords),
					FormID:       fq.FormID,
					FieldKeys:    fq.FieldKeys,
					FilterString: fq.GetFilter(),
					FieldMap:     fq.FieldMap,
				})
			}
		}
	}

	sort.Slice(forms, func(i, j int) bool {
		return forms[i].FormName < forms[j].FormName
	})

	if forms == nil {
		forms = []Form{}
	}

	WriteData(c, http.StatusOK, forms)
}

type formStat struct {
	lastSync      string
	lastStatus    string
	totalRecords  int64
	failedRecords int64
}

// loadFormStats queries go_sync_run_forms for the latest sync result per form.
func loadFormStats() map[string]formStat {
	result := make(map[string]formStat)
	db := gormdb.DB
	if db == nil {
		return result
	}

	// Find the latest SyncRunForm row per form_name (subquery on MAX created_at)
	type row struct {
		FormName     string `json:"form_name"`
		Status       string `json:"status"`
		TotalRecords int64  `json:"total_records"`
		Failed       int64  `json:"failed"`
		RunID        string `json:"run_id"`
	}
	var rows []row
	err := db.Table("go_sync_run_forms").
		Select("form_name, status, total_records, failed, run_id").
		Where("(form_name, created_at) IN (?)",
			db.Table("go_sync_run_forms").
				Select("form_name, MAX(created_at)").
				Group("form_name"),
		).
		Find(&rows).Error
	if err != nil {
		return result
	}

	// Collect run_ids to batch-load start_time from go_sync_runs
	runIDs := make([]string, 0, len(rows))
	runIDSet := make(map[string]bool)
	for _, r := range rows {
		if !runIDSet[r.RunID] {
			runIDs = append(runIDs, r.RunID)
			runIDSet[r.RunID] = true
		}
	}

	runTimeMap := make(map[string]string)
	if len(runIDs) > 0 {
		var runs []struct {
			RunID     string `json:"run_id"`
			StartTime string `json:"start_time"`
		}
		if err := db.Table("go_sync_runs").
			Select("run_id, start_time").
			Where("run_id IN ?", runIDs).
			Find(&runs).Error; err == nil {
			for _, r := range runs {
				runTimeMap[r.RunID] = r.StartTime
			}
		}
	}

	for _, r := range rows {
		result[r.FormName] = formStat{
			lastSync:      runTimeMap[r.RunID],
			lastStatus:    r.Status,
			totalRecords:  r.TotalRecords,
			failedRecords: r.Failed,
		}
	}
	return result
}

func updateForm(c *gin.Context) {
	db := gormdb.DB
	if db == nil {
		WriteProblem(c, http.StatusServiceUnavailable, Problem{
			Code:    "INTERNAL_ERROR",
			Message: "database not initialized",
		})
		return
	}

	formName := c.Param("name")
	if formName == "" {
		WriteProblem(c, http.StatusBadRequest, Problem{
			Code:    "INVALID_REQUEST",
			Message: "form name is required",
		})
		return
	}

	var req struct {
		Enabled       *bool                   `json:"enabled"`
		FormID        *string                 `json:"form_id"`
		FieldKeys     *string                 `json:"field_keys"`
		FilterString  *string                 `json:"filter_string"`
		FieldMap      *map[string]string      `json:"field_map"`
		DefaultValues *map[string]interface{} `json:"default_values"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		WriteProblem(c, http.StatusBadRequest, Problem{
			Code:    "INVALID_REQUEST",
			Message: "invalid request: " + err.Error(),
		})
		return
	}

	// Update FormQueryConfig
	var cfg gormdb.FormQueryConfig
	result := db.Where("form_name = ?", formName).First(&cfg)
	if result.Error != nil {
		if result.Error == gorm.ErrRecordNotFound {
			// Create new config entry
			cfg = gormdb.FormQueryConfig{FormName: formName}
		} else {
			WriteProblem(c, http.StatusInternalServerError, Problem{
				Code:    "INTERNAL_ERROR",
				Message: "failed to query form config",
			})
			return
		}
	}

	if req.FormID != nil {
		cfg.FormID = *req.FormID
	}
	if req.FieldKeys != nil {
		cfg.FieldKeys = *req.FieldKeys
	}
	if req.FilterString != nil {
		cfg.FilterString = *req.FilterString
	}
	if req.FieldMap != nil {
		data, _ := json.Marshal(*req.FieldMap)
		cfg.FieldMap = string(data)
	}
	if req.DefaultValues != nil {
		data, _ := json.Marshal(*req.DefaultValues)
		cfg.DefaultValues = string(data)
	}

	if cfg.ID == 0 {
		if err := db.Create(&cfg).Error; err != nil {
			WriteProblem(c, http.StatusInternalServerError, Problem{
				Code:    "INTERNAL_ERROR",
				Message: "failed to create form config",
			})
			return
		}
	} else {
		if err := db.Save(&cfg).Error; err != nil {
			WriteProblem(c, http.StatusInternalServerError, Problem{
				Code:    "INTERNAL_ERROR",
				Message: "failed to update form config",
			})
			return
		}
	}

	// Update enabled status separately
	if req.Enabled != nil {
		var setting gormdb.FormSetting
		res := db.Where("form_name = ?", formName).First(&setting)
		if res.Error != nil {
			if res.Error == gorm.ErrRecordNotFound {
				setting = gormdb.FormSetting{
					FormName: formName,
					Enabled:  *req.Enabled,
				}
				db.Create(&setting)
			}
		} else {
			setting.Enabled = *req.Enabled
			db.Save(&setting)
		}
	}

	WriteData(c, http.StatusOK, gin.H{
		"form_name":  formName,
		"form_id":    cfg.FormID,
		"field_keys": cfg.FieldKeys,
	})
}

func listDataSources(c *gin.Context) {
	svc := datasource.GetService()
	sources := svc.GetDataSources()

	// Convert to v1 format
	result := make([]DataSource, 0, len(sources))
	for _, src := range sources {
		result = append(result, DataSource{
			ID:     src.ID,
			Name:   src.Name,
			Type:   src.Type,
			Status: src.Status,
		})
	}

	WriteData(c, http.StatusOK, result)
}

func toString(v any) string {
	if v == nil {
		return ""
	}
	if s, ok := v.(string); ok {
		return s
	}
	return ""
}
