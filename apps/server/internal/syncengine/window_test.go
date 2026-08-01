package syncengine

import (
	"context"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/kingdee-sync/go/internal/config"
	"github.com/kingdee-sync/go/internal/kind"
	"github.com/stretchr/testify/require"
)

func TestBuildWindowFilterUsesHalfOpenRange(t *testing.T) {
	start := time.Date(2025, 3, 1, 0, 0, 0, 0, time.Local)
	end := time.Date(2025, 3, 4, 0, 0, 0, 0, time.Local)
	got, err := BuildWindowFilter("FUseOrgId = YOUR_ORG_ID", Window{Start: start, End: end})
	require.NoError(t, err)
	require.Equal(t, "(FUseOrgId = YOUR_ORG_ID) AND (FModifyDate >= '2025-03-01 00:00:00' AND FModifyDate < '2025-03-04 00:00:00')", got)
}

func TestBuildWindowFilterEmptyBase(t *testing.T) {
	start := time.Date(2025, 3, 1, 0, 0, 0, 0, time.Local)
	end := time.Date(2025, 3, 4, 0, 0, 0, 0, time.Local)
	got, err := BuildWindowFilter("", Window{Start: start, End: end})
	require.NoError(t, err)
	require.Equal(t, "(FModifyDate >= '2025-03-01 00:00:00' AND FModifyDate < '2025-03-04 00:00:00')", got)
}

func TestBuildWindowFilterRejectsInverted(t *testing.T) {
	start := time.Date(2025, 3, 4, 0, 0, 0, 0, time.Local)
	end := time.Date(2025, 3, 1, 0, 0, 0, 0, time.Local)
	_, err := BuildWindowFilter("", Window{Start: start, End: end})
	require.Error(t, err)
}

// fakeWriter 记录 Upsert 调用次数，不实际写入。
type fakeWriter struct {
	upsertCalls    int
	upsertReturned int
	upsertErr      error
	deleteCalls    int
	cols           []string
	rows           []map[string]interface{}
}

func (f *fakeWriter) Upsert(ctx context.Context, tableName string, rows []map[string]interface{}, cols []string, pkCols []string, fieldMap map[string]string) (int, error) {
	f.upsertCalls++
	f.cols = append([]string(nil), cols...)
	f.rows = rows
	return f.upsertReturned, f.upsertErr
}

func fakeColumns(string) (map[string]string, error) {
	return map[string]string{"FID": "FID", "FNAME": "FNAME"}, nil
}
func (f *fakeWriter) DeleteOrphaned(ctx context.Context, tableName string, rows []map[string]interface{}, pkCols []string) (int, error) {
	f.deleteCalls++
	return 0, nil
}
func (f *fakeWriter) Close() error { return nil }

func TestWindowRunnerWritesRowsWithoutCheckpointOrOrphanDelete(t *testing.T) {
	w := &fakeWriter{upsertReturned: 2}
	fetch := func(ctx context.Context, p kind.QueryParams) (*kind.QueryResult, error) {
		return &kind.QueryResult{Rows: []map[string]interface{}{{"FID": 1}, {"FID": 2}}}, nil
	}
	formQuery := func(name string) (config.FormQuery, bool) {
		return config.FormQuery{FormID: "SALEORDER", FieldKeys: "FID,FNAME", FilterString: "FUseOrgId = YOUR_ORG_ID"}, true
	}
	runner := NewWindowRunner(fetch, w, formQuery, fakeColumns)
	window := Window{
		Start: time.Date(2025, 3, 1, 0, 0, 0, 0, time.Local),
		End:   time.Date(2025, 3, 4, 0, 0, 0, 0, time.Local),
	}

	summary, err := runner.SyncForm(context.Background(), "销售订单", window)
	require.NoError(t, err)
	require.Equal(t, "销售订单", summary.FormName)
	require.Equal(t, 2, summary.Fetched)
	require.Equal(t, 2, summary.Inserted)
	require.Empty(t, summary.Error)
	require.Equal(t, 1, w.upsertCalls, "Upsert should be called exactly once")
	require.Equal(t, []string{"FID", "FNAME"}, w.cols)
	require.Equal(t, 0, w.deleteCalls, "DeleteOrphaned must never be called")
}

func TestWindowRunnerEmptyResultSkipsWrite(t *testing.T) {
	w := &fakeWriter{}
	fetch := func(ctx context.Context, p kind.QueryParams) (*kind.QueryResult, error) {
		return &kind.QueryResult{Rows: []map[string]interface{}{}}, nil
	}
	formQuery := func(name string) (config.FormQuery, bool) {
		return config.FormQuery{FormID: "BD_MATERIAL", FieldKeys: "FID"}, true
	}
	runner := NewWindowRunner(fetch, w, formQuery, fakeColumns)
	window := Window{
		Start: time.Date(2025, 1, 1, 0, 0, 0, 0, time.Local),
		End:   time.Date(2025, 1, 2, 0, 0, 0, 0, time.Local),
	}

	summary, err := runner.SyncForm(context.Background(), "物料", window)
	require.NoError(t, err)
	require.Equal(t, 0, summary.Fetched)
	require.Equal(t, 0, summary.Inserted)
	require.Equal(t, 0, w.upsertCalls, "Upsert should not be called for empty result")
}

func TestWindowRunnerAppliesConfiguredDefaultValues(t *testing.T) {
	w := &fakeWriter{upsertReturned: 1}
	sourceRow := map[string]interface{}{"FID": 1}
	fetch := func(context.Context, kind.QueryParams) (*kind.QueryResult, error) {
		return &kind.QueryResult{Rows: []map[string]interface{}{sourceRow}}, nil
	}
	formQuery := func(string) (config.FormQuery, bool) {
		return config.FormQuery{
			FormID:        "AP_Payable",
			FieldKeys:     "FID",
			DefaultValues: map[string]interface{}{"FNOTAXAMOUNTFOR": 0},
		}, true
	}
	columns := func(string) (map[string]string, error) {
		return map[string]string{"FID": "FID", "FNOTAXAMOUNTFOR": "FNOTAXAMOUNTFOR"}, nil
	}
	runner := NewWindowRunner(fetch, w, formQuery, columns)

	_, err := runner.SyncFormWithFilter(context.Background(), "应付单", "ap_payable", "1=1")
	require.NoError(t, err)
	require.Contains(t, w.cols, "FNOTAXAMOUNTFOR")
	require.Equal(t, 0, w.rows[0]["FNOTAXAMOUNTFOR"])
	require.NotContains(t, sourceRow, "FNOTAXAMOUNTFOR")
}

func TestWindowRunnerIncludesDerivedAccountBalanceWriteFields(t *testing.T) {
	w := &fakeWriter{upsertReturned: 1}
	columns := func(string) (map[string]string, error) {
		return map[string]string{
			"FBALANCEID":  "FBALANCEID",
			"FACCTYEAR":   "FACCTYEAR",
			"FACCTPERIOD": "FACCTPERIOD",
		}, nil
	}
	runner := NewWindowRunner(nil, w, nil, columns)
	mapping := WindowTableMapping{Form: "科目余额表", Table: "gl_rpt_accountbalance", TargetTable: "gl_rpt_accountbalance"}
	fq := config.FormQuery{FieldKeys: "FBALANCEID"}
	result := &kind.QueryResult{Rows: []map[string]interface{}{{
		"FBALANCEID": "1001", "FACCTYEAR": 2025, "FACCTPERIOD": 1,
	}}}

	summary, err := runner.SyncManifestRows(context.Background(), mapping, fq, "", result)

	require.NoError(t, err)
	require.Empty(t, summary.Error)
	require.Equal(t, []string{"FBALANCEID", "FACCTYEAR", "FACCTPERIOD"}, w.cols)
}

func TestWindowRunnerAppliesManifestBlankDefaultWithoutNormalizingItToNull(t *testing.T) {
	w := &fakeWriter{upsertReturned: 1}
	fetch := func(context.Context, kind.QueryParams) (*kind.QueryResult, error) {
		return &kind.QueryResult{Rows: []map[string]interface{}{{"FNUMBER": "M-1", "F_ORA_TEXT_QTR": " "}}}, nil
	}
	formQuery := func(string) (config.FormQuery, bool) {
		return config.FormQuery{FormID: "BD_MATERIAL", FieldKeys: "FNUMBER,F_ORA_TEXT_QTR"}, true
	}
	columns := func(string) (map[string]string, error) {
		return map[string]string{"FNUMBER": "FNUMBER", "F_ORA_TEXT_QTR": "F_ORA_TEXT_QTR"}, nil
	}
	runner := NewWindowRunner(fetch, w, formQuery, columns)
	mapping := WindowTableMapping{
		Form: "物料", Table: "bd_material", TargetTable: "bd_material__next_abcdef01",
		DefaultValues: map[string]interface{}{"F_ORA_TEXT_QTR": ""},
	}

	_, err := runner.SyncManifestMapping(context.Background(), mapping, "1=1")
	require.NoError(t, err)
	defaultValue, ok := w.rows[0]["F_ORA_TEXT_QTR"].(configuredDefaultValue)
	require.True(t, ok)
	require.Equal(t, "", defaultValue.Value)
}

func TestWindowRunnerDoesNotOverrideMappedSourceWithContractDefault(t *testing.T) {
	w := &fakeWriter{upsertReturned: 1}
	fetch := func(context.Context, kind.QueryParams) (*kind.QueryResult, error) {
		return &kind.QueryResult{Rows: []map[string]interface{}{{
			"FDocumentStatus": "C",
			"FDescription":    "出口托盘",
		}}}, nil
	}
	formQuery := func(string) (config.FormQuery, bool) {
		return config.FormQuery{
			FormID:    "BD_MATERIAL",
			FieldKeys: "FDocumentStatus,FDescription",
			FieldMap: map[string]string{
				"FDocumentStatus": "FDOCUMENTSTATUS",
				"FDescription":    "FDESCRIPTION",
			},
		}, true
	}
	columns := func(string) (map[string]string, error) {
		return map[string]string{
			"FDOCUMENTSTATUS": "FDOCUMENTSTATUS",
			"FDESCRIPTION":    "FDESCRIPTION",
		}, nil
	}
	runner := NewWindowRunner(fetch, w, formQuery, columns)
	mapping := WindowTableMapping{
		Form: "物料", Table: "bd_material", TargetTable: "bd_material__next_abcdef01",
		DefaultValues: map[string]interface{}{"FDOCUMENTSTATUS": "", "FDESCRIPTION": ""},
	}

	_, err := runner.SyncManifestMapping(context.Background(), mapping, "1=1")
	require.NoError(t, err)
	require.NotContains(t, w.rows[0], "FDOCUMENTSTATUS")
	require.NotContains(t, w.rows[0], "FDESCRIPTION")
	require.Equal(t, "C", w.rows[0]["FDocumentStatus"])
	require.Equal(t, "出口托盘", w.rows[0]["FDescription"])
}

func TestWindowRunnerFormNotFound(t *testing.T) {
	w := &fakeWriter{}
	fetch := func(ctx context.Context, p kind.QueryParams) (*kind.QueryResult, error) {
		t.Fatal("fetch should not be called")
		return nil, nil
	}
	formQuery := func(name string) (config.FormQuery, bool) {
		return config.FormQuery{}, false
	}
	runner := NewWindowRunner(fetch, w, formQuery, fakeColumns)
	window := Window{
		Start: time.Date(2025, 1, 1, 0, 0, 0, 0, time.Local),
		End:   time.Date(2025, 1, 2, 0, 0, 0, 0, time.Local),
	}

	summary, err := runner.SyncForm(context.Background(), "未知表单", window)
	require.NoError(t, err)
	require.Contains(t, summary.Error, "form not found")
	require.Equal(t, 0, w.upsertCalls)
}

func TestWindowRunnerFetchError(t *testing.T) {
	w := &fakeWriter{}
	fetch := func(ctx context.Context, p kind.QueryParams) (*kind.QueryResult, error) {
		return nil, fmtErr("network timeout")
	}
	formQuery := func(name string) (config.FormQuery, bool) {
		return config.FormQuery{FormID: "BD_MATERIAL", FieldKeys: "FID"}, true
	}
	runner := NewWindowRunner(fetch, w, formQuery, fakeColumns)
	window := Window{
		Start: time.Date(2025, 1, 1, 0, 0, 0, 0, time.Local),
		End:   time.Date(2025, 1, 2, 0, 0, 0, 0, time.Local),
	}

	summary, err := runner.SyncForm(context.Background(), "物料", window)
	require.NoError(t, err)
	require.Contains(t, summary.Error, "network timeout")
	require.Equal(t, 0, w.upsertCalls)
}

func TestWindowRunnerWriterError(t *testing.T) {
	w := &fakeWriter{upsertErr: fmtErr("write failed")}
	fetch := func(ctx context.Context, p kind.QueryParams) (*kind.QueryResult, error) {
		return &kind.QueryResult{Rows: []map[string]interface{}{{"FID": 1}}}, nil
	}
	formQuery := func(name string) (config.FormQuery, bool) {
		return config.FormQuery{FormID: "BD_MATERIAL", FieldKeys: "FID"}, true
	}
	runner := NewWindowRunner(fetch, w, formQuery, fakeColumns)
	window := Window{
		Start: time.Date(2025, 1, 1, 0, 0, 0, 0, time.Local),
		End:   time.Date(2025, 1, 2, 0, 0, 0, 0, time.Local),
	}

	summary, err := runner.SyncForm(context.Background(), "物料", window)
	require.NoError(t, err)
	require.Contains(t, summary.Error, "write failed")
	require.Equal(t, 1, summary.Fetched)
}

func TestLoadWindowManifest(t *testing.T) {
	dir := t.TempDir()
	data := `{
		"windows": [{
			"id": 1,
			"start": "2025-03-01T00:00:00Z",
			"end": "2025-03-04T00:00:00Z",
			"form_names": ["物料", "仓库"]
		}]
	}`
	path := filepath.Join(dir, "manifest.json")
	require.NoError(t, os.WriteFile(path, []byte(data), 0644))

	m, err := LoadWindowManifest(path)
	require.NoError(t, err)
	require.Len(t, m.Windows, 1)

	spec, err := m.FindWindow(1)
	require.NoError(t, err)
	require.Equal(t, []string{"物料", "仓库"}, spec.FormName)

	w, err := spec.ToWindow()
	require.NoError(t, err)
	require.Equal(t, time.Date(2025, 3, 1, 0, 0, 0, 0, time.UTC), w.Start)
	require.Equal(t, time.Date(2025, 3, 4, 0, 0, 0, 0, time.UTC), w.End)
}

func TestLoadCutoverManifestRejectsWindowAndTamperedTargets(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "cutover.json")
	data := `{
		"manifest_kind":"cutover",
		"contract_hash":"abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
		"migration_tables":["bd_material"],
		"table_mappings":[{
			"form":"物料","table":"bd_material","target_table":"bd_material",
			"primary_key":["FNUMBER"],"storage_key":["FNUMBER"]
		}]
	}`
	require.NoError(t, os.WriteFile(path, []byte(data), 0644))
	_, err := LoadCutoverManifest(path)
	require.ErrorContains(t, err, "invalid cutover mapping")
}

func TestLoadCutoverManifestRequiresCursorKeyForFullForms(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "cutover.json")
	data := `{
		"manifest_kind":"cutover",
		"contract_hash":"abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
		"table_mappings":[{
			"form":"物料","table":"bd_material","target_table":"bd_material",
			"primary_key":["FNUMBER"],"storage_key":["FNUMBER"],"mode":"full"
		}]
	}`
	require.NoError(t, os.WriteFile(path, []byte(data), 0644))
	_, err := LoadCutoverManifest(path)
	require.ErrorContains(t, err, "cursor_key")
}

func TestWindowMappingsUseFrozenFilters(t *testing.T) {
	m := &WindowManifest{
		ContractHash:    "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
		MigrationTables: []string{"bd_material"},
		Windows:         []WindowSpec{{ID: 1}},
		TableMappings: []WindowTableMapping{
			{Form: "物料", Table: "bd_material", TargetTable: "bd_material__next_abcdef01", Mode: "window_supported", Filters: map[string]string{"1": "FModifyDate >= '2025-01-01 00:00:00'"}},
			{Form: "即时库存", Table: "stk_inventory", TargetTable: "stk_inventory", Mode: "snapshot_only"},
		},
	}
	mappings, err := m.WindowMappings(1)
	require.NoError(t, err)
	require.Len(t, mappings, 1)
	require.Equal(t, "bd_material__next_abcdef01", mappings[0].TargetTable)
	require.Contains(t, mappings[0].Filters["1"], "FModifyDate >=")
}

func TestWindowMappingsRejectTamperedTargetTable(t *testing.T) {
	m := &WindowManifest{
		ContractHash:    "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
		MigrationTables: []string{"bd_material"},
		Windows:         []WindowSpec{{ID: 1}},
		TableMappings: []WindowTableMapping{
			{Form: "物料", Table: "bd_material", TargetTable: "bd_material", Mode: "window_supported", Filters: map[string]string{"1": "1=1"}},
		},
	}

	_, err := m.WindowMappings(1)
	require.ErrorContains(t, err, "target table")
}

func TestFindWindowNotFound(t *testing.T) {
	m := &WindowManifest{Windows: []WindowSpec{{ID: 1}}}
	_, err := m.FindWindow(99)
	require.Error(t, err)
}

func TestWindowSpecParsesManifestLocalTime(t *testing.T) {
	spec := WindowSpec{ID: 1, Start: "2025-01-23T00:00:00", End: "2025-01-26T00:00:00"}
	window, err := spec.ToWindow()
	require.NoError(t, err)
	require.Equal(t, "Asia/Shanghai", window.Start.Location().String())
	require.Equal(t, 23, window.Start.Day())
}

// fmtErr is a helper to create errors in test files without importing fmt in every place.
func fmtErr(s string) error {
	return &literalError{s}
}

type literalError struct{ s string }

func (e *literalError) Error() string { return e.s }
