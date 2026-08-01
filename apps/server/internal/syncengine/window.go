package syncengine

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/kingdee-sync/go/internal/config"
	"github.com/kingdee-sync/go/internal/db"
	"github.com/kingdee-sync/go/internal/kind"
)

// Window 表示左闭右开 [Start, End) 的 FModifyDate 范围。
type Window struct {
	Start time.Time `json:"start"`
	End   time.Time `json:"end"`
}

// BuildWindowFilter 将基础 SQL 过滤器与左闭右开 FModifyDate 窗口合并。
func BuildWindowFilter(base string, window Window) (string, error) {
	if !window.Start.Before(window.End) {
		return "", fmt.Errorf("window start must be before end")
	}
	format := "2006-01-02 15:04:05"
	timeFilter := fmt.Sprintf("FModifyDate >= '%s' AND FModifyDate < '%s'",
		window.Start.Format(format), window.End.Format(format))
	base = strings.TrimSpace(base)
	if base == "" {
		return "(" + timeFilter + ")", nil
	}
	return "(" + base + ") AND (" + timeFilter + ")", nil
}

// WindowFetch 抽象金蝶查询调用，便于测试注入。
type WindowFetch func(context.Context, kind.QueryParams) (*kind.QueryResult, error)

// WindowColumns resolves target columns for a table.
type WindowColumns func(string) (map[string]string, error)

// WindowRunner 执行隔离的窗口同步，不触碰 checkpoint 或孤儿删除。
// （原因：验收专用——隔离运行语义，不影响正常同步流程）
type WindowRunner struct {
	Fetch     WindowFetch
	Writer    RowWriter
	FormQuery func(string) (config.FormQuery, bool)
	Columns   WindowColumns
}

// WindowFormSummary 记录单表同步结果，供验收使用。
type WindowFormSummary struct {
	FormName  string `json:"form_name"`
	TableName string `json:"table_name"`
	Fetched   int    `json:"fetched"`
	Inserted  int    `json:"inserted"`
	Filter    string `json:"filter"`
	Error     string `json:"error,omitempty"`
}

// NewWindowRunner 创建窗口同步运行器。
func NewWindowRunner(fetch WindowFetch, writer RowWriter, formQuery func(string) (config.FormQuery, bool), columns WindowColumns) *WindowRunner {
	return &WindowRunner{Fetch: fetch, Writer: writer, FormQuery: formQuery, Columns: columns}
}

// SyncForm 对单个表单执行窗口同步：查询金蝶 -> 写入目标库。
// 不更新 checkpoint，不执行孤儿删除。
func (r *WindowRunner) SyncForm(ctx context.Context, formName string, window Window) (WindowFormSummary, error) {
	// 1. 加载表单配置
	fq, ok := r.FormQuery(formName)
	if !ok {
		return WindowFormSummary{FormName: formName, Error: "form not found in config"}, nil
	}

	// 2. 构建窗口过滤器
	filter, err := BuildWindowFilter(fq.GetFilter(), window)
	if err != nil {
		return WindowFormSummary{FormName: formName, Error: err.Error()}, nil
	}

	tableName := config.FormToTableName(formName)
	return r.syncFormWithFilter(ctx, formName, tableName, tableName, fq, filter)
}

// SyncFormWithFilter runs one form using the immutable filter and target table
// stored in the acceptance manifest.
func (r *WindowRunner) SyncFormWithFilter(ctx context.Context, formName, tableName, filter string) (WindowFormSummary, error) {
	fq, ok := r.FormQuery(formName)
	if !ok {
		return WindowFormSummary{FormName: formName, TableName: tableName, Error: "form not found in config"}, nil
	}
	return r.syncFormWithFilter(ctx, formName, tableName, tableName, fq, filter)
}

// SyncManifestMapping executes one immutable manifest mapping, including its
// shadow target and MSSQL contract defaults.
func (r *WindowRunner) SyncManifestMapping(ctx context.Context, mapping WindowTableMapping, filter string) (WindowFormSummary, error) {
	fq, ok := r.FormQuery(mapping.Form)
	if !ok {
		return WindowFormSummary{FormName: mapping.Form, TableName: mapping.TargetTable, Error: "form not found in config"}, nil
	}
	mergedDefaults := make(map[string]interface{}, len(mapping.DefaultValues)+len(fq.DefaultValues))
	for column, value := range mapping.DefaultValues {
		mergedDefaults[column] = value
	}
	for column, value := range fq.DefaultValues {
		mergedDefaults[column] = value
	}
	fq.DefaultValues = mergedDefaults
	return r.syncFormWithFilter(ctx, mapping.Form, mapping.TargetTable, mapping.Table, fq, filter)
}

func (r *WindowRunner) syncFormWithFilter(ctx context.Context, formName, tableName, primaryKeyTable string, fq config.FormQuery, filter string) (WindowFormSummary, error) {
	// 3. 解析字段列表
	var fieldKeyList []string
	if fq.FieldKeys != "" {
		for _, k := range strings.Split(fq.FieldKeys, ",") {
			if k := strings.TrimSpace(k); k != "" {
				fieldKeyList = append(fieldKeyList, k)
			}
		}
	}

	// 4. 查询金蝶
	params := kind.QueryParams{
		FormID:       fq.FormID,
		FieldKeys:    fq.FieldKeys,
		Filter:       filter,
		StartRow:     0,
		Limit:        0,
		FieldKeyList: fieldKeyList,
	}
	result, err := r.Fetch(ctx, params)
	if err != nil {
		return WindowFormSummary{FormName: formName, Filter: filter, Error: err.Error()}, nil
	}
	return r.SyncManifestRows(ctx, WindowTableMapping{
		Form: formName, Table: primaryKeyTable, TargetTable: tableName,
	}, fq, filter, result)
}

// SyncManifestRows writes an already-fetched immutable result without querying
// Kingdee again. Cutover invokes it only after source validation succeeds.
func (r *WindowRunner) SyncManifestRows(ctx context.Context, mapping WindowTableMapping, fq config.FormQuery, filter string, result *kind.QueryResult) (WindowFormSummary, error) {
	if result == nil {
		return WindowFormSummary{FormName: mapping.Form, TableName: mapping.TargetTable, Filter: filter, Error: "query result is nil"}, nil
	}
	fieldKeyList := make([]string, 0)
	for _, key := range strings.Split(fq.FieldKeys, ",") {
		if key = strings.TrimSpace(key); key != "" {
			fieldKeyList = append(fieldKeyList, key)
		}
	}
	fieldKeyList = appendDerivedWriteFields(mapping.Form, fieldKeyList)
	fetched := len(result.Rows)

	// 5. 写入目标库（空结果不写入）
	var inserted int
	if fetched > 0 {
		if r.Columns == nil {
			return WindowFormSummary{FormName: mapping.Form, TableName: mapping.TargetTable, Filter: filter, Fetched: fetched, Error: "target column provider is not configured"}, nil
		}
		existingCols, columnErr := r.Columns(mapping.TargetTable)
		if columnErr != nil {
			return WindowFormSummary{FormName: mapping.Form, TableName: mapping.TargetTable, Filter: filter, Fetched: fetched, Error: fmt.Sprintf("load target columns: %v", columnErr)}, nil
		}
		cols, fieldMap := buildWindowColumnMapping(fieldKeyList, fq.FieldMap, existingCols)
		cols = appendWindowDefaultColumns(cols, fq.DefaultValues, existingCols)
		if len(cols) == 0 {
			return WindowFormSummary{FormName: mapping.Form, TableName: mapping.TargetTable, Filter: filter, Fetched: fetched, Error: "no matching target columns"}, nil
		}
		pk := append([]string{}, mapping.PrimaryKey...)
		if len(pk) == 0 {
			pk = strings.Split(db.GetPrimaryKey(mapping.Table), ",")
		}
		for i := range pk {
			pk[i] = strings.TrimSpace(pk[i])
		}
		rows := applyWindowDefaults(result.Rows, fq.DefaultValues, existingCols, fieldMap)
		var writeErr error
		inserted, writeErr = r.Writer.Upsert(ctx, mapping.TargetTable, rows, cols, pk, fieldMap)
		if writeErr != nil {
			return WindowFormSummary{FormName: mapping.Form, TableName: mapping.TargetTable, Filter: filter, Fetched: fetched, Error: writeErr.Error()}, nil
		}
	}

	return WindowFormSummary{
		FormName:  mapping.Form,
		TableName: mapping.TargetTable,
		Fetched:   fetched,
		Inserted:  inserted,
		Filter:    filter,
	}, nil
}

func appendDerivedWriteFields(formName string, fields []string) []string {
	if formName != "科目余额表" {
		return fields
	}

	seen := make(map[string]struct{}, len(fields)+2)
	for _, field := range fields {
		seen[strings.ToUpper(strings.TrimSpace(field))] = struct{}{}
	}
	for _, field := range []string{"FACCTYEAR", "FACCTPERIOD"} {
		if _, exists := seen[field]; !exists {
			fields = append(fields, field)
			seen[field] = struct{}{}
		}
	}
	return fields
}

func buildWindowColumnMapping(fieldKeys []string, explicit map[string]string, existing map[string]string) ([]string, map[string]string) {
	fieldMap := make(map[string]string)
	cols := make([]string, 0, len(fieldKeys))
	for _, field := range fieldKeys {
		if column, ok := explicit[field]; ok {
			if actual, exists := existing[strings.ToUpper(column)]; exists {
				fieldMap[field] = actual
				cols = append(cols, actual)
				continue
			}
		}
		if actual, ok := existing[strings.ToUpper(field)]; ok {
			fieldMap[field] = actual
			cols = append(cols, actual)
			continue
		}
		if dot := strings.Index(field, "."); dot > 0 {
			if actual, ok := existing[strings.ToUpper(field[:dot])]; ok {
				fieldMap[field] = actual
				cols = append(cols, actual)
			}
		}
	}
	return cols, fieldMap
}

func appendWindowDefaultColumns(cols []string, defaults map[string]interface{}, existing map[string]string) []string {
	seen := make(map[string]struct{}, len(cols))
	for _, col := range cols {
		seen[strings.ToUpper(col)] = struct{}{}
	}
	for defaultColumn := range defaults {
		actual, ok := existing[strings.ToUpper(defaultColumn)]
		if !ok {
			continue
		}
		key := strings.ToUpper(actual)
		if _, exists := seen[key]; !exists {
			cols = append(cols, actual)
			seen[key] = struct{}{}
		}
	}
	return cols
}

func applyWindowDefaults(rows []map[string]interface{}, defaults map[string]interface{}, existing map[string]string, fieldMap map[string]string) []map[string]interface{} {
	if len(defaults) == 0 || len(rows) == 0 {
		return rows
	}
	result := make([]map[string]interface{}, len(rows))
	for i, row := range rows {
		copyRow := make(map[string]interface{}, len(row)+len(defaults))
		for key, value := range row {
			copyRow[key] = value
		}
		for defaultColumn, value := range defaults {
			actual, ok := existing[strings.ToUpper(defaultColumn)]
			if !ok {
				continue
			}
			missing := !hasWindowSourceValue(copyRow, actual, fieldMap)
			if missing {
				if text, ok := value.(string); ok && strings.TrimSpace(text) == "" {
					copyRow[actual] = configuredDefaultValue{Value: value}
				} else {
					copyRow[actual] = value
				}
			}
		}
		result[i] = copyRow
	}
	return result
}

func hasWindowSourceValue(row map[string]interface{}, targetColumn string, fieldMap map[string]string) bool {
	for key, value := range row {
		matchesTarget := strings.EqualFold(key, targetColumn)
		if !matchesTarget {
			for source, mappedTarget := range fieldMap {
				if strings.EqualFold(mappedTarget, targetColumn) && strings.EqualFold(source, key) {
					matchesTarget = true
					break
				}
			}
		}
		if !matchesTarget || value == nil {
			continue
		}
		if text, ok := value.(string); ok && strings.TrimSpace(text) == "" {
			continue
		}
		return true
	}
	return false
}

type configuredDefaultValue struct {
	Value interface{}
}

// WindowManifest 表示验收窗口的 JSON 规格文件。
type WindowManifest struct {
	ManifestKind    string               `json:"manifest_kind"`
	ContractHash    string               `json:"contract_hash"`
	MigrationTables []string             `json:"migration_tables"`
	Windows         []WindowSpec         `json:"windows"`
	TableMappings   []WindowTableMapping `json:"table_mappings"`
}

type CutoverManifest struct {
	ManifestKind    string               `json:"manifest_kind"`
	ContractHash    string               `json:"contract_hash"`
	ConfigSHA256    string               `json:"config_sha256"`
	GitCommit       string               `json:"git_commit"`
	GitDirty        bool                 `json:"git_dirty"`
	MigrationTables []string             `json:"migration_tables"`
	TableMappings   []WindowTableMapping `json:"table_mappings"`
}

// WindowTableMapping is the immutable per-form input recorded by preflight.
type WindowTableMapping struct {
	Form            string                 `json:"form"`
	Table           string                 `json:"table"`
	TargetTable     string                 `json:"target_table"`
	PrimaryKey      []string               `json:"primary_key"`
	StorageKey      []string               `json:"storage_key"`
	CursorKey       []string               `json:"cursor_key,omitempty"`
	ModifyTimeField string                 `json:"modify_time_field,omitempty"`
	FilterString    string                 `json:"filter_string"`
	Mode            string                 `json:"mode"`
	Filters         map[string]string      `json:"filters"`
	DefaultValues   map[string]interface{} `json:"default_values"`
}

// WindowSpec 描述单个窗口的表单列表和时间范围。
type WindowSpec struct {
	ID       int      `json:"id"`
	Start    string   `json:"start"` // RFC3339 时间
	End      string   `json:"end"`   // RFC3339 时间
	FormName []string `json:"form_names"`
}

// WindowMappings returns only preflight-approved window forms and their
// frozen filters for one window ID.
func (m *WindowManifest) WindowMappings(windowID int) ([]WindowTableMapping, error) {
	if _, err := m.FindWindow(windowID); err != nil {
		return nil, err
	}
	key := fmt.Sprintf("%d", windowID)
	migrationTables := make(map[string]struct{}, len(m.MigrationTables))
	for _, table := range m.MigrationTables {
		migrationTables[table] = struct{}{}
	}
	mappings := make([]WindowTableMapping, 0, len(m.TableMappings))
	for _, mapping := range m.TableMappings {
		if mapping.Mode != "window_supported" {
			continue
		}
		if mapping.Form == "" || mapping.Table == "" || mapping.TargetTable == "" || mapping.Filters[key] == "" {
			return nil, fmt.Errorf("manifest mapping for %s lacks frozen filter for window %d", mapping.Form, windowID)
		}
		expectedTarget := mapping.Table
		if _, migrated := migrationTables[mapping.Table]; migrated {
			if len(m.ContractHash) < 8 {
				return nil, fmt.Errorf("manifest contract hash is invalid")
			}
			expectedTarget = mapping.Table + "__next_" + m.ContractHash[:8]
		}
		if mapping.TargetTable != expectedTarget {
			return nil, fmt.Errorf("manifest target table for %s is %q, want %q", mapping.Table, mapping.TargetTable, expectedTarget)
		}
		mappings = append(mappings, mapping)
	}
	return mappings, nil
}

// LoadWindowManifest 从 JSON 文件加载窗口清单。
func LoadWindowManifest(path string) (*WindowManifest, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read manifest %s: %w", path, err)
	}
	var manifest WindowManifest
	if err := json.Unmarshal(data, &manifest); err != nil {
		return nil, fmt.Errorf("parse manifest %s: %w", path, err)
	}
	return &manifest, nil
}

func LoadCutoverManifest(path string) (*CutoverManifest, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read cutover manifest %s: %w", path, err)
	}
	var manifest CutoverManifest
	if err := json.Unmarshal(data, &manifest); err != nil {
		return nil, fmt.Errorf("parse cutover manifest %s: %w", path, err)
	}
	if manifest.ManifestKind != "cutover" || len(manifest.ContractHash) != 64 {
		return nil, fmt.Errorf("invalid cutover manifest kind or contract hash")
	}
	migration := make(map[string]struct{}, len(manifest.MigrationTables))
	for _, table := range manifest.MigrationTables {
		migration[table] = struct{}{}
	}
	for _, mapping := range manifest.TableMappings {
		expected := mapping.Table
		if _, ok := migration[mapping.Table]; ok {
			expected = mapping.Table + "__next_" + manifest.ContractHash[:8]
		}
		if mapping.Form == "" || mapping.Table == "" || mapping.TargetTable != expected || len(mapping.PrimaryKey) == 0 || len(mapping.StorageKey) == 0 {
			return nil, fmt.Errorf("invalid cutover mapping for %s", mapping.Table)
		}
		if mapping.Mode == "full" && len(mapping.CursorKey) == 0 {
			return nil, fmt.Errorf("cutover mapping for %s lacks cursor_key", mapping.Table)
		}
		if mapping.Mode == "full" && mapping.ModifyTimeField == "" {
			return nil, fmt.Errorf("cutover mapping for %s lacks modify_time_field", mapping.Table)
		}
		if mapping.Mode == "snapshot_full" && len(mapping.CursorKey) != 0 {
			return nil, fmt.Errorf("snapshot mapping for %s must not define cursor_key", mapping.Table)
		}
		if mapping.Mode == "snapshot_full" && mapping.ModifyTimeField != "" {
			return nil, fmt.Errorf("snapshot mapping for %s must not define modify_time_field", mapping.Table)
		}
	}
	return &manifest, nil
}

// FindWindow 按 ID 查找窗口规格。
func (m *WindowManifest) FindWindow(id int) (*WindowSpec, error) {
	for i := range m.Windows {
		if m.Windows[i].ID == id {
			return &m.Windows[i], nil
		}
	}
	return nil, fmt.Errorf("window %d not found", id)
}

// ToWindow 将 WindowSpec 解析为 Window 结构。
func (s *WindowSpec) ToWindow() (Window, error) {
	start, err := parseWindowTime(s.Start)
	if err != nil {
		return Window{}, fmt.Errorf("parse start time %q: %w", s.Start, err)
	}
	end, err := parseWindowTime(s.End)
	if err != nil {
		return Window{}, fmt.Errorf("parse end time %q: %w", s.End, err)
	}
	return Window{Start: start, End: end}, nil
}

func parseWindowTime(value string) (time.Time, error) {
	if parsed, err := time.Parse(time.RFC3339, value); err == nil {
		return parsed, nil
	}
	location, err := time.LoadLocation("Asia/Shanghai")
	if err != nil {
		return time.Time{}, err
	}
	return time.ParseInLocation("2006-01-02T15:04:05", value, location)
}
