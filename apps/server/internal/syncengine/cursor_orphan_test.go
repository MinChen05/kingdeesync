package syncengine

import (
	"testing"
)

func TestLookupSourceKeyValueDirectAndCaseInsensitive(t *testing.T) {
	row := map[string]interface{}{
		"FID":         float64(10),
		"FENTRYID":    "20",
		"FSaleOrgId":  100,
		"FGROUP.FNAME": "测试组",
	}
	// direct key match
	if v := lookupSourceKeyValue(row, "FID", nil); v != float64(10) {
		t.Fatalf("direct lookup FID = %v", v)
	}
	// case-insensitive match (row key differs only in case)
	if v := lookupSourceKeyValue(row, "fentryid", nil); v != "20" {
		t.Fatalf("case-insensitive lookup = %v", v)
	}
	// missing key
	if v := lookupSourceKeyValue(row, "FNUMBER", nil); v != nil {
		t.Fatalf("missing key lookup = %v, want nil", v)
	}
}

func TestLookupSourceKeyValueViaFieldMapReverse(t *testing.T) {
	// fieldMap: kingdee field -> db column; lookup goes db column -> kingdee field
	fieldMap := map[string]string{
		"FTreeEntity_FENTRYID": "FENTRYID",
		"FID":                  "FID",
	}
	colToKingdee := make(map[string][]string)
	for kField, dbCol := range fieldMap {
		colToKingdee[dbCol] = append(colToKingdee[dbCol], kField)
	}
	row := map[string]interface{}{
		"FID":                  float64(7),
		"FTreeEntity_FENTRYID": "99",
	}
	if v := lookupSourceKeyValue(row, "FENTRYID", colToKingdee); v != "99" {
		t.Fatalf("reverse fieldMap lookup FENTRYID = %v, want 99", v)
	}
	if v := lookupSourceKeyValue(row, "FID", colToKingdee); v != float64(7) {
		t.Fatalf("reverse fieldMap lookup FID = %v, want 7", v)
	}
}

func TestSourceKeyCollectorCompletenessGateBlocksPartialWrite(t *testing.T) {
	// ReconcileAndDelete must refuse to delete when written != fetched,
	// without touching the database (nil collector db would panic otherwise).
	c := &sourceKeyCollector{db: nil, stagingTable: "srckeys_test"}
	if _, err := c.ReconcileAndDelete(t.Context(), "saleorder", 100, 99); err == nil {
		t.Fatal("expected partial-write block error")
	}
	if _, err := c.ReconcileAndDelete(t.Context(), "saleorder", 0, 0); err == nil {
		t.Fatal("expected empty-source block error")
	}
}
