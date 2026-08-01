package syncengine

import (
	"reflect"
	"testing"
	"time"
)

func TestNormalizeValueFloatToInt(t *testing.T) {
	tests := []struct {
		input    interface{}
		expected interface{}
	}{
		{float64(12), int64(12)},
		{float64(0), int64(0)},
		{float64(12.5), float64(12.5)},
		{nil, nil},
		{"hello", "hello"},
		{int64(5), int64(5)},
	}
	for _, tt := range tests {
		got := normalizeValue(tt.input)
		if !reflect.DeepEqual(got, tt.expected) {
			t.Errorf("normalizeValue(%v) = %v (%T), want %v (%T)", tt.input, got, got, tt.expected, tt.expected)
		}
	}
}

func TestNormalizeRowInjectsSyncTime(t *testing.T) {
	rows := []map[string]interface{}{{"FID": "1", "FNAME": "Test"}}
	cols := []string{"FID", "FNAME"}
	result := NormalizeRows(rows, cols, nil, nil)
	if len(result) != 1 {
		t.Fatalf("result rows = %d, want 1", len(result))
	}
	if _, ok := result[0]["SYNC_TIME"]; !ok {
		t.Fatal("SYNC_TIME not injected")
	}
	if result[0]["FID"] != "1" {
		t.Fatalf("FID = %v, want 1", result[0]["FID"])
	}
}

func TestNormalizeRowsEmpty(t *testing.T) {
	result := NormalizeRows(nil, []string{"FID"}, nil, nil)
	if result != nil {
		t.Fatalf("NormalizeRows(nil) = %v, want nil", result)
	}
}

func TestNormalizeRowTrimsTextAndConvertsBlankToNil(t *testing.T) {
	result := NormalizeRow(map[string]interface{}{
		"FCUSTOMERNAME": "  金宇机电  ",
		"FREMARK":       " \t ",
	}, []string{"FCUSTOMERNAME", "FREMARK"}, nil, time.UTC)

	if got := result["FCUSTOMERNAME"]; got != "金宇机电" {
		t.Fatalf("trimmed text = %#v, want 金宇机电", got)
	}
	if got := result["FREMARK"]; got != nil {
		t.Fatalf("blank text = %#v, want nil", got)
	}
}

func TestBuildReverseFieldMap(t *testing.T) {
	fieldMap := map[string]string{
		"FNAME": "NAME",
		"FID":   "ID",
	}
	reverse := buildReverseFieldMap(fieldMap)
	if len(reverse) != 2 {
		t.Fatalf("reverse map size = %d, want 2", len(reverse))
	}
	if !reflect.DeepEqual(reverse["NAME"], []string{"FNAME"}) {
		t.Fatalf("reverse[NAME] = %v, want [FNAME]", reverse["NAME"])
	}
}

func TestLookupNormalizedValueDirectMatch(t *testing.T) {
	row := map[string]interface{}{"FID": "100", "FNAME": "A"}
	val := lookupNormalizedValue(row, "FID", nil)
	if val != "100" {
		t.Fatalf("direct match = %v, want 100", val)
	}
}

func TestLookupNormalizedValueUppercaseFallback(t *testing.T) {
	row := map[string]interface{}{"FID": "100"}
	val := lookupNormalizedValue(row, "fid", nil)
	if val != "100" {
		t.Fatalf("uppercase fallback = %v, want 100", val)
	}
}

func TestLookupNormalizedValueFieldMap(t *testing.T) {
	row := map[string]interface{}{"FNAME": "Product-A"}
	reverse := map[string][]string{"NAME": {"FNAME"}}
	val := lookupNormalizedValue(row, "NAME", reverse)
	if val != "Product-A" {
		t.Fatalf("field map lookup = %v, want Product-A", val)
	}
}

func TestLookupNormalizedValueNilReturnsNil(t *testing.T) {
	row := map[string]interface{}{"FID": "1"}
	val := lookupNormalizedValue(row, "MISSING", nil)
	if val != nil {
		t.Fatalf("missing column = %v, want nil", val)
	}
}

func TestComputePkCount(t *testing.T) {
	rows := []map[string]interface{}{
		{"FID": "1", "FENTRYID": "A"},
		{"FID": "1", "FENTRYID": "B"},
		{"FID": "2", "FENTRYID": "A"},
	}
	count := ComputePkCount(rows, []string{"FID", "FENTRYID"})
	if count != 3 {
		t.Fatalf("PkCount = %d, want 3", count)
	}
}

func TestValidateSnapshotDataRejectsEmpty(t *testing.T) {
	err := ValidateSnapshotData(nil, []string{"FID"}, "test-form")
	if err == nil {
		t.Fatal("expected error for empty rows")
	}
}

func TestValidateSnapshotDataRejectsMissingPK(t *testing.T) {
	rows := []map[string]interface{}{{"FID": "1"}}
	err := ValidateSnapshotData(rows, []string{}, "test-form")
	if err == nil {
		t.Fatal("expected error for missing PK columns")
	}
}

func TestValidateSnapshotDataRejectsNilPK(t *testing.T) {
	rows := []map[string]interface{}{{"FID": nil}}
	err := ValidateSnapshotData(rows, []string{"FID"}, "test-form")
	if err == nil {
		t.Fatal("expected error for nil PK values")
	}
}

func TestValidateSnapshotDataPasses(t *testing.T) {
	rows := []map[string]interface{}{
		{"FID": "1", "FENTRYID": "A"},
		{"FID": "2", "FENTRYID": "B"},
	}
	err := ValidateSnapshotData(rows, []string{"FID", "FENTRYID"}, "test-form")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}
