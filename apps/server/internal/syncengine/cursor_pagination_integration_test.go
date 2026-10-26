package syncengine

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"testing"

	"github.com/kingdee-sync/go/internal/config"
	"github.com/kingdee-sync/go/internal/gormdb"
)

// runIsolatedKingdeeTest re-executes the test binary so the process-wide
// Kingdee client singleton is initialized from the fake server config.
func runIsolatedKingdeeTest(t *testing.T, envKey string) bool {
	t.Helper()
	if os.Getenv(envKey) != "" {
		return true
	}
	cmd := exec.Command(os.Args[0], "-test.run", "^"+t.Name()+"$")
	cmd.Env = append(os.Environ(), envKey+"=1")
	if output, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("isolated test failed: %v\n%s", err, output)
	}
	return false
}

type fakeCursorServer struct {
	mu       sync.Mutex
	requests int
	filters  []string
	pages    [][]map[string]interface{}
}

func (s *fakeCursorServer) handler(t *testing.T) http.HandlerFunc {
	t.Helper()
	return func(w http.ResponseWriter, r *http.Request) {
		defer r.Body.Close()
		switch r.URL.Path {
		case "/login":
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"LoginResultType":1,"SessionId":"local-session"}`))
		case "/query":
			var payload struct {
				Data struct {
					FilterString string `json:"FilterString"`
					Limit        int    `json:"Limit"`
				} `json:"data"`
			}
			if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
				http.Error(w, err.Error(), http.StatusBadRequest)
				return
			}
			s.mu.Lock()
			s.requests++
			index := s.requests - 1
			s.filters = append(s.filters, payload.Data.FilterString)
			s.mu.Unlock()
			if index >= len(s.pages) {
				http.Error(w, fmt.Sprintf("unexpected page request %d", s.requests), http.StatusBadRequest)
				return
			}
			w.Header().Set("Content-Type", "application/json")
			_ = json.NewEncoder(w).Encode(map[string]interface{}{
				"Result": map[string]interface{}{"Rows": s.pages[index]},
			})
		default:
			http.NotFound(w, r)
		}
	}
}

func setupCursorPaginationTest(t *testing.T, server *httptest.Server) {
	t.Helper()
	setupRecoveryTest(t)
	configPath := filepath.Join(t.TempDir(), "config.ini")
	content := fmt.Sprintf("[KINGDEE]\nlogin_url = %s/login\nquery_url = %s/query\npage_size = 2\nmax_pages = 10\nrate_limit_qps = 1000\n", server.URL, server.URL)
	if err := os.WriteFile(configPath, []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := config.Load(configPath); err != nil {
		t.Fatalf("load local Kingdee test config: %v", err)
	}
}

func runCursorFormSync(t *testing.T, runID, formName, tableName string, writes *[]int, logs *[]string) *FormStat {
	t.Helper()
	if _, err := gormdb.CreateSyncRun(runID, "test", "full"); err != nil {
		t.Fatal(err)
	}
	engine := &SyncEngine{}
	if err := engine.PrepareRun(runID, false); err != nil {
		t.Fatal(err)
	}
	engine.SetLogCallback(func(_, _, level, message string) {
		*logs = append(*logs, level+" "+message)
	}, runID)
	engine.writeRowsFunc = func(_ context.Context, _ string, rows []map[string]interface{}, _ []string, _ map[string]string) (UpsertResult, error) {
		*writes = append(*writes, len(rows))
		return UpsertResult{Inserted: len(rows), Total: len(rows)}, nil
	}
	stat := &FormStat{FormName: formName, TableName: tableName}
	engine.syncCursorForm(context.Background(), context.Background(), runID, formName, tableName,
		config.FormQuery{FormID: "PRD_PPBOM"}, []string{"FID", "FEntity_FENTRYID"},
		"FPrdOrgId = 171190", "full", false, stat)
	return stat
}

func TestCursorPaginationSkipsTerminalEmptyTailPage(t *testing.T) {
	if !runIsolatedKingdeeTest(t, "SYNCENGINE_CURSOR_TAIL_TEST") {
		return
	}
	pages := [][]map[string]interface{}{
		{{"FID": float64(1), "FEntity_FENTRYID": float64(11)}, {"FID": float64(2), "FEntity_FENTRYID": float64(22)}},
		{{"FID": float64(3), "FEntity_FENTRYID": float64(33)}, {"FID": float64(4), "FEntity_FENTRYID": float64(44)}},
		{{"FID": float64(5), "FEntity_FENTRYID": nil}},
	}
	fake := &fakeCursorServer{pages: pages}
	server := httptest.NewServer(fake.handler(t))
	defer server.Close()
	setupCursorPaginationTest(t, server)

	var writes []int
	var logs []string
	stat := runCursorFormSync(t, "cursor-tail", "生产用料清单明细表", "prd_ppbomentry", &writes, &logs)

	if stat.Status != StatusSuccess || stat.ErrorCount != 0 {
		t.Fatalf("status=%q errors=%d message=%q, want success", stat.Status, stat.ErrorCount, stat.Error)
	}
	if stat.FetchedCount != 4 || stat.InsertedCount != 4 {
		t.Fatalf("fetched=%d inserted=%d, want both 4", stat.FetchedCount, stat.InsertedCount)
	}
	if fake.requests != 3 {
		t.Fatalf("query requests=%d, want 3 (no repeated final page)", fake.requests)
	}
	if len(fake.filters) != 3 || !strings.Contains(fake.filters[1], "FID > 2") || !strings.Contains(fake.filters[2], "FID > 4") {
		t.Fatalf("cursor filters did not advance: %#v", fake.filters)
	}
	if len(writes) != 2 || writes[0] != 2 || writes[1] != 2 {
		t.Fatalf("write batches=%v, want [2 2] (invalid tail row skipped)", writes)
	}
	warned := false
	for _, entry := range logs {
		if strings.HasPrefix(entry, "WARN ") && strings.Contains(entry, "缺少游标键") {
			warned = true
		}
	}
	if !warned {
		t.Fatalf("expected a WARN about empty cursor keys, got %#v", logs)
	}
	if cp, err := gormdb.GetCheckpoint("生产用料清单明细表"); err != nil || cp != nil {
		t.Fatalf("checkpoint after success = %#v (err=%v), want cleared", cp, err)
	}
}

func TestCursorPaginationFailsOnFullEmptyPage(t *testing.T) {
	if !runIsolatedKingdeeTest(t, "SYNCENGINE_CURSOR_FULL_EMPTY_TEST") {
		return
	}
	pages := [][]map[string]interface{}{
		{{"FID": float64(1), "FEntity_FENTRYID": float64(11)}, {"FID": float64(2), "FEntity_FENTRYID": float64(22)}},
		{{"FID": nil, "FEntity_FENTRYID": nil}, {"FID": nil, "FEntity_FENTRYID": nil}},
	}
	fake := &fakeCursorServer{pages: pages}
	server := httptest.NewServer(fake.handler(t))
	defer server.Close()
	setupCursorPaginationTest(t, server)

	var writes []int
	var logs []string
	stat := runCursorFormSync(t, "cursor-full-empty", "生产用料清单明细表", "prd_ppbomentry", &writes, &logs)

	if stat.Status != StatusFailed || stat.ErrorCount != 1 {
		t.Fatalf("status=%q errors=%d, want failed with one error", stat.Status, stat.ErrorCount)
	}
	if !strings.Contains(stat.Error, "cursor page 2") || !strings.Contains(stat.Error, "no valid cursor keys") {
		t.Fatalf("error=%q, want cursor page 2 hard failure", stat.Error)
	}
	if fake.requests != 2 {
		t.Fatalf("query requests=%d, want 2 (no extra request after hard failure)", fake.requests)
	}
	if len(writes) != 1 || writes[0] != 2 {
		t.Fatalf("write batches=%v, want [2] before the failing page", writes)
	}
}
