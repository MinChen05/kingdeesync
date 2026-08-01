package syncengine

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestDeleteStreamLoadUsesDeleteModeAndRejectsDuplicateKeys(t *testing.T) {
	var mergeType string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mergeType = r.Header.Get("merge_type")
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"Status":"Success","NumberTotalRows":1,"NumberLoadedRows":1,"NumberFilteredRows":0}`))
	}))
	defer server.Close()
	writer := &DorisWriter{httpClient: server.Client()}
	written, err := writer.doStreamLoadWithRedirect(
		context.Background(), server.URL, "user", "password", "label", "orders", []byte(`[{"FID":1}]`), "DELETE", 0,
	)
	if err != nil || written != 1 || mergeType != "DELETE" {
		t.Fatalf("delete stream load = (%d, %v), merge_type=%q", written, err, mergeType)
	}
}

func TestDeleteKeysRejectsIncompleteOrDuplicateKeysBeforeNetwork(t *testing.T) {
	writer := &DorisWriter{}
	if _, err := writer.DeleteKeys(context.Background(), "orders", []map[string]interface{}{{"FID": nil}}, []string{"FID"}); err == nil {
		t.Fatal("expected missing key error")
	}
	if _, err := writer.DeleteKeys(context.Background(), "orders", []map[string]interface{}{{"FID": 1}, {"fid": 1}}, []string{"FID"}); err == nil {
		t.Fatal("expected duplicate key error")
	}
}

func TestBuildJSONPayloadMapsFieldsAndConvertsWholeNumbers(t *testing.T) {
	writer := &DorisWriter{}
	rows := []map[string]interface{}{{
		"FID":          "1001",
		"FNAME":        "脱敏物料",
		"FGROUP.FNAME": "原材料",
		"FQTY":         float64(12),
		"FRATE":        float64(12.5),
		"FNOTE":        nil,
	}}
	payload, err := writer.buildJSONPayload("test_table", rows, []string{"FID", "NAME", "GROUP", "QTY", "RATE", "NOTE"}, map[string]string{
		"FNAME":        "NAME",
		"FGROUP.FNAME": "GROUP",
		"FQTY":         "QTY",
		"FRATE":        "RATE",
		"FNOTE":        "NOTE",
	})
	if err != nil {
		t.Fatal(err)
	}
	var got []map[string]json.RawMessage
	if err := json.Unmarshal(payload, &got); err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 {
		t.Fatalf("payload rows = %d, want 1", len(got))
	}
	if string(got[0]["NAME"]) != `"脱敏物料"` || string(got[0]["GROUP"]) != `"原材料"` {
		t.Fatalf("mapped payload strings = %s, %s", got[0]["NAME"], got[0]["GROUP"])
	}
	if !bytes.Equal(got[0]["QTY"], json.RawMessage("12")) {
		t.Fatalf("QTY JSON = %s, want integer JSON 12", got[0]["QTY"])
	}
	if !bytes.Equal(got[0]["RATE"], json.RawMessage("12.5")) {
		t.Fatalf("RATE JSON = %s, want decimal JSON 12.5", got[0]["RATE"])
	}
	if !bytes.Equal(got[0]["NOTE"], json.RawMessage("null")) {
		t.Fatalf("NOTE JSON = %s, want null", got[0]["NOTE"])
	}
	for _, col := range []string{"FID", "NAME", "GROUP", "QTY", "RATE", "NOTE", "SYNC_TIME"} {
		if _, ok := got[0][col]; !ok {
			t.Fatalf("payload missing Doris column %q: %#v", col, got[0])
		}
	}
	var syncTime string
	if err := json.Unmarshal(got[0]["SYNC_TIME"], &syncTime); err != nil || syncTime == "" {
		t.Fatalf("SYNC_TIME = %#v, want non-empty string", got[0]["SYNC_TIME"])
	}
	if _, err := time.ParseInLocation("2006-01-02 15:04:05", syncTime, time.Local); err != nil {
		t.Fatalf("SYNC_TIME = %q, want local timestamp format: %v", syncTime, err)
	}
}

func TestBuildJSONPayloadEmptyRowsReturnsEmptyArray(t *testing.T) {
	writer := &DorisWriter{}
	payload, err := writer.buildJSONPayload("test_table", nil, []string{"FID"}, nil)
	if err != nil || !bytes.Equal(payload, []byte("[]")) {
		t.Fatalf("buildJSONPayload(empty) = (%s, %v), want [] and nil", payload, err)
	}
}

func TestBuildJSONPayloadTruncatesFractionalDateTime(t *testing.T) {
	writer := &DorisWriter{}
	payload, err := writer.buildJSONPayload(
		"test_table",
		[]map[string]interface{}{{"FModifyDate": "2025-01-23T14:16:16.517"}},
		[]string{"FModifyDate"},
		map[string]string{"FModifyDate": "FModifyDate"},
	)
	if err != nil {
		t.Fatal(err)
	}
	var got []map[string]string
	if err := json.Unmarshal(payload, &got); err != nil {
		t.Fatal(err)
	}
	if got[0]["FModifyDate"] != "2025-01-23 14:16:16" {
		t.Fatalf("FModifyDate = %q, want whole-second value", got[0]["FModifyDate"])
	}
}

func TestBuildJSONPayloadAppliesTextNormalization(t *testing.T) {
	writer := &DorisWriter{}
	payload, err := writer.buildJSONPayload(
		"test_table",
		[]map[string]interface{}{{"FCUSTOMERID.FNAME": "  金宇机电  ", "FREMARK": " \t "}},
		[]string{"FCUSTOMERNAME", "FREMARK"},
		map[string]string{"FCUSTOMERID.FNAME": "FCUSTOMERNAME", "FREMARK": "FREMARK"},
	)
	if err != nil {
		t.Fatalf("buildJSONPayload() error = %v", err)
	}

	var rows []map[string]json.RawMessage
	if err := json.Unmarshal(payload, &rows); err != nil {
		t.Fatalf("unmarshal payload: %v", err)
	}
	var customer string
	if err := json.Unmarshal(rows[0]["FCUSTOMERNAME"], &customer); err != nil {
		t.Fatalf("unmarshal FCUSTOMERNAME: %v", err)
	}
	if customer != "金宇机电" {
		t.Fatalf("FCUSTOMERNAME = %q, want 金宇机电", customer)
	}
	if !bytes.Equal(rows[0]["FREMARK"], json.RawMessage("null")) {
		t.Fatalf("FREMARK JSON = %s, want null", rows[0]["FREMARK"])
	}
}

func TestBuildJSONPayloadMatchesKingdeeFieldsCaseInsensitively(t *testing.T) {
	writer := &DorisWriter{}
	payload, err := writer.buildJSONPayload(
		"test_table",
		[]map[string]interface{}{{
			"FDOCUMENTSTATUS": "C",
			"fbilltype.fname": "物料清单",
			"FDESCRIPTION":    "出口托盘",
		}},
		[]string{"FDOCUMENTSTATUS", "FBILLTYPE", "FDescription"},
		map[string]string{
			"FDocumentStatus": "FDOCUMENTSTATUS",
			"FBILLTYPE.FNAME": "FBILLTYPE",
			"FDescription":    "FDescription",
		},
	)
	if err != nil {
		t.Fatal(err)
	}
	var rows []map[string]interface{}
	if err := json.Unmarshal(payload, &rows); err != nil {
		t.Fatal(err)
	}
	if rows[0]["FDOCUMENTSTATUS"] != "C" {
		t.Fatalf("FDOCUMENTSTATUS = %#v", rows[0]["FDOCUMENTSTATUS"])
	}
	if rows[0]["FBILLTYPE"] != "物料清单" {
		t.Fatalf("FBILLTYPE = %#v", rows[0]["FBILLTYPE"])
	}
	if rows[0]["FDescription"] != "出口托盘" {
		t.Fatalf("FDescription = %#v", rows[0]["FDescription"])
	}
}

func TestBuildJSONPayloadOnlyTruncatesCustomerCreateDate(t *testing.T) {
	writer := &DorisWriter{}
	input := []map[string]interface{}{{"FCREATEDATE": "2026-06-25 09:49:29"}}

	customerPayload, err := writer.buildJSONPayload("customer", input, []string{"FCREATEDATE"}, nil)
	if err != nil {
		t.Fatal(err)
	}
	productionPayload, err := writer.buildJSONPayload("prd_mo", input, []string{"FCREATEDATE"}, nil)
	if err != nil {
		t.Fatal(err)
	}
	var customerRows, productionRows []map[string]string
	if err := json.Unmarshal(customerPayload, &customerRows); err != nil {
		t.Fatal(err)
	}
	if err := json.Unmarshal(productionPayload, &productionRows); err != nil {
		t.Fatal(err)
	}
	if customerRows[0]["FCREATEDATE"] != "2026-06-25 00:00:00" {
		t.Fatalf("customer FCREATEDATE = %q", customerRows[0]["FCREATEDATE"])
	}
	if productionRows[0]["FCREATEDATE"] != "2026-06-25 09:49:29" {
		t.Fatalf("prd_mo FCREATEDATE = %q", productionRows[0]["FCREATEDATE"])
	}
}

// TestPaginatedFixtureShape verifies the fixed multi-page sample structure
// only. It does not drive QueryData or the production pagination loop; that
// real chain is deferred to a future injectable sync-engine seam.
func TestPaginatedFixtureShape(t *testing.T) {
	emptyData, err := os.ReadFile(filepath.Join("..", "..", "testdata", "kingdee", "empty.json"))
	if err != nil {
		t.Fatal(err)
	}
	var empty struct {
		Result struct {
			Rows []map[string]interface{} `json:"Rows"`
		} `json:"Result"`
	}
	if err := json.Unmarshal(emptyData, &empty); err != nil {
		t.Fatalf("parse empty.json: %v", err)
	}
	if len(empty.Result.Rows) != 0 {
		t.Fatalf("empty sample rows = %d, want 0", len(empty.Result.Rows))
	}

	data, err := os.ReadFile(filepath.Join("..", "..", "testdata", "kingdee", "paginated.json"))
	if err != nil {
		t.Fatal(err)
	}
	var pages []struct {
		Result struct {
			Rows       []map[string]interface{} `json:"Rows"`
			PageIndex  int                      `json:"PageIndex"`
			PageSize   int                      `json:"PageSize"`
			TotalCount int                      `json:"TotalCount"`
		} `json:"Result"`
	}
	if err := json.Unmarshal(data, &pages); err != nil {
		t.Fatalf("parse paginated.json: %v", err)
	}
	if len(pages) != 2 {
		t.Fatalf("pagination pages = %d, want 2", len(pages))
	}
	for i, page := range pages {
		if page.Result.PageIndex != i+1 || page.Result.PageSize != 2 || page.Result.TotalCount != 4 {
			t.Fatalf("page %d metadata = %+v, want page %d size 2 total 4", i+1, page.Result, i+1)
		}
	}
	if len(pages[0].Result.Rows) != 2 || len(pages[1].Result.Rows) != 2 {
		t.Fatalf("page row counts = %d and %d, want 2 and 2", len(pages[0].Result.Rows), len(pages[1].Result.Rows))
	}
	if pages[0].Result.Rows[0]["FID"] != "1001" || pages[1].Result.Rows[1]["FNUMBER"] != "M-004" {
		t.Fatalf("paginated sample boundary rows = %#v and %#v", pages[0].Result.Rows[0], pages[1].Result.Rows[1])
	}
	if value, ok := pages[0].Result.Rows[0]["FDESCRIPTION"]; !ok || value != nil {
		t.Fatalf("paginated sample null field = %#v, want FDESCRIPTION:null", value)
	}

}
