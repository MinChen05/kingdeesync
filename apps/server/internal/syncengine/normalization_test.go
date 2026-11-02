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
	err := ValidateSnapshotData(nil, []string{"FID"}, "test-form", nil)
	if err == nil {
		t.Fatal("expected error for empty rows")
	}
}

func TestValidateSnapshotDataRejectsMissingPK(t *testing.T) {
	rows := []map[string]interface{}{{"FID": "1"}}
	err := ValidateSnapshotData(rows, []string{}, "test-form", nil)
	if err == nil {
		t.Fatal("expected error for missing PK columns")
	}
}

func TestValidateSnapshotDataRejectsNilPK(t *testing.T) {
	rows := []map[string]interface{}{{"FID": nil}}
	err := ValidateSnapshotData(rows, []string{"FID"}, "test-form", nil)
	if err == nil {
		t.Fatal("expected error for nil PK values")
	}
}

func TestValidateSnapshotDataPasses(t *testing.T) {
	rows := []map[string]interface{}{
		{"FID": "1", "FENTRYID": "A"},
		{"FID": "2", "FENTRYID": "B"},
	}
	err := ValidateSnapshotData(rows, []string{"FID", "FENTRYID"}, "test-form", nil)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestValidateSnapshotDataWithFieldMap(t *testing.T) {
	// 金蝶返回的字段名是 "FEntity_FENTRYID"，但 Doris 列名是 "FENTRYID"
	rows := []map[string]interface{}{
		{"FID": "1", "FEntity_FENTRYID": "A"},
		{"FID": "2", "FEntity_FENTRYID": "B"},
	}
	fieldMap := map[string]string{"FEntity_FENTRYID": "FENTRYID"}
	err := ValidateSnapshotData(rows, []string{"FID", "FENTRYID"}, "test-form", fieldMap)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestFindDuplicateBusinessKeysDetectsCompositeDup(t *testing.T) {
	rows := []map[string]interface{}{
		{"FID": "1", "FENTRYID": "A"},
		{"FID": "1", "FENTRYID": "A"},
		{"FID": "2", "FENTRYID": "B"},
		{"FID": "3", "FENTRYID": "C"},
		{"FID": "3", "FENTRYID": "C"},
	}
	sample, dups := FindDuplicateBusinessKeys(rows, []string{"FID", "FENTRYID"}, nil, 3)
	if dups != 2 {
		t.Fatalf("重复组数 = %d, want 2", dups)
	}
	if len(sample) != 2 || sample[0] != "1|A×2" || sample[1] != "3|C×2" {
		t.Fatalf("样例 = %#v, want 排序后的 [1|A×2 3|C×2]", sample)
	}
}

func TestFindDuplicateBusinessKeysNoDup(t *testing.T) {
	rows := []map[string]interface{}{
		{"FID": "1", "FENTRYID": "A"},
		{"FID": "1", "FENTRYID": "B"},
	}
	if sample, dups := FindDuplicateBusinessKeys(rows, []string{"FID", "FENTRYID"}, nil, 3); dups != 0 || sample != nil {
		t.Fatalf("无重复时应返回 (nil, 0)，实得 %#v / %d", sample, dups)
	}
}

// 键取不到值时不得判为重复：无唯一索引的目标表历史上可能已在静默写入空键行，
// 那属于"键缺失"问题，不应被本校验突然变成写入失败（原因：避免引入新回归）。
func TestFindDuplicateBusinessKeysSkipsWhenKeyMissing(t *testing.T) {
	rows := []map[string]interface{}{
		{"FID": nil, "FENTRYID": "A"},
		{"FID": nil, "FENTRYID": "A"},
	}
	if sample, dups := FindDuplicateBusinessKeys(rows, []string{"FID", "FENTRYID"}, nil, 3); dups != 0 || sample != nil {
		t.Fatalf("键缺失应跳过重复判定，实得 %#v / %d", sample, dups)
	}
}

func TestFindDuplicateBusinessKeysUsesFieldMapReverse(t *testing.T) {
	// 源数据只有金蝶字段名，业务键是 DB 列名
	rows := []map[string]interface{}{
		{"FID": "1", "FEntity_FENTRYID": "A"},
		{"FID": "1", "FEntity_FENTRYID": "A"},
	}
	fieldMap := map[string]string{"FEntity_FENTRYID": "FENTRYID"}
	sample, dups := FindDuplicateBusinessKeys(rows, []string{"FID", "FENTRYID"}, fieldMap, 3)
	if dups != 1 {
		t.Fatalf("应通过 fieldMap 反查识别出重复，实得 dups=%d sample=%#v", dups, sample)
	}

	// 大小写回退：键列以小写声明，而金蝶行数据里是大写列名
	rows2 := []map[string]interface{}{{"fmaterialid": "9"}, {"FMATERIALID": "9"}}
	if _, dups2 := FindDuplicateBusinessKeys(rows2, []string{"fmaterialid"}, nil, 3); dups2 != 1 {
		t.Fatalf("大小写回退失效，dups=%d", dups2)
	}
}

func TestFindDuplicateBusinessKeysSampleLimit(t *testing.T) {
	rows := make([]map[string]interface{}, 0, 8)
	for i := 0; i < 4; i++ {
		k := string(rune('a' + i))
		rows = append(rows, map[string]interface{}{"FID": k}, map[string]interface{}{"FID": k})
	}
	sample, dups := FindDuplicateBusinessKeys(rows, []string{"FID"}, nil, 2)
	if dups != 4 {
		t.Fatalf("重复组数 = %d, want 4", dups)
	}
	if len(sample) != 2 {
		t.Fatalf("样例数 = %d, want 截断到 2：%#v", len(sample), sample)
	}
}

func TestFindDuplicateBusinessKeysGuardsBadInput(t *testing.T) {
	rows := []map[string]interface{}{{"FID": "1"}, {"FID": "1"}}
	if _, dups := FindDuplicateBusinessKeys(rows, nil, nil, 3); dups != 0 {
		t.Fatal("无键列定义时应跳过")
	}
	if _, dups := FindDuplicateBusinessKeys(rows, []string{"FID"}, nil, 0); dups != 0 {
		t.Fatal("limit<=0 时应跳过")
	}
	if _, dups := FindDuplicateBusinessKeys(nil, []string{"FID"}, nil, 3); dups != 0 {
		t.Fatal("空数据时应跳过")
	}
}
