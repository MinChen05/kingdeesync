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
	"reflect"
	"sync"
	"testing"
	"time"

	"github.com/kingdee-sync/go/internal/config"
	"github.com/kingdee-sync/go/internal/gormdb"
	"github.com/kingdee-sync/go/internal/kind"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

func setupRecoveryTest(t *testing.T) {
	t.Helper()
	oldDB := gormdb.DB
	db, err := gorm.Open(sqlite.Open(fmt.Sprintf("file:recovery-test-%d?mode=memory&cache=shared", time.Now().UnixNano())), &gorm.Config{})
	if err != nil {
		t.Fatalf("open test sqlite: %v", err)
	}
	gormdb.DB = db
	if err := gormdb.AutoMigrate(); err != nil {
		t.Fatalf("migrate test sqlite: %v", err)
	}
	t.Cleanup(func() {
		gormdb.DB = oldDB
		if sqlDB, err := db.DB(); err == nil {
			_ = sqlDB.Close()
		}
	})
}

func newRecoveryTestEngine(writer RowWriter) *SyncEngine {
	return &SyncEngine{
		writer: writer,
		formQuery: func(string) (config.FormQuery, bool) {
			return config.FormQuery{FormID: "TEST_FORM", FieldKeys: "FID"}, true
		},
	}
}

func createAbnormalRun(t *testing.T, runID string) *gormdb.SyncRun {
	t.Helper()
	run, err := gormdb.CreateSyncRun(runID, "test", "full")
	if err != nil {
		t.Fatal(err)
	}
	if err := gormdb.MarkSyncRunAbnormalExit(runID, "test abnormal exit"); err != nil {
		t.Fatal(err)
	}
	run, err = gormdb.GetSyncRun(runID)
	if err != nil {
		t.Fatal(err)
	}
	return run
}

func TestStartupRecoveryMarksRunningAndStoppingAbnormal(t *testing.T) {
	setupRecoveryTest(t)
	old := time.Now().Add(-10 * time.Minute)
	for _, status := range []string{"running", "stopping"} {
		runID := "stale-" + status
		if _, err := gormdb.CreateSyncRun(runID, "test", "full"); err != nil {
			t.Fatal(err)
		}
		if err := gormdb.DB.Model(&gormdb.SyncRun{}).Where("run_id = ?", runID).Updates(map[string]interface{}{
			"status":         status,
			"last_heartbeat": old,
			"error_message":  "",
			"end_time":       nil,
		}).Error; err != nil {
			t.Fatal(err)
		}
	}
	count, err := gormdb.RecoverAbnormalRuns(5 * time.Minute)
	if err != nil {
		t.Fatal(err)
	}
	if count != 2 {
		t.Fatalf("recovered count = %d, want 2", count)
	}
	for _, runID := range []string{"stale-running", "stale-stopping"} {
		run, err := gormdb.GetSyncRun(runID)
		if err != nil {
			t.Fatal(err)
		}
		if run.Status != string(StatusFailedAbnormalExit) {
			t.Fatalf("run %s status = %q", runID, run.Status)
		}
	}
}

func TestPrepareRecoveryCreatesChildOnlyForValidCheckpoint(t *testing.T) {
	setupRecoveryTest(t)
	parent := createAbnormalRun(t, "abnormal-parent")
	if err := gormdb.SaveCheckpointForRun("生产订单主表", parent.RunID, 120, ""); err != nil {
		t.Fatal(err)
	}
	engine := &SyncEngine{}
	plan, err := engine.PrepareRecovery(parent.RunID, false)
	if err != nil {
		t.Fatal(err)
	}
	if plan.RunID == "" || len(plan.Forms) != 1 || plan.Forms[0] != "生产订单主表" {
		t.Fatalf("recovery plan = %#v", plan)
	}
	child, err := gormdb.GetSyncRun(plan.RunID)
	if err != nil {
		t.Fatal(err)
	}
	if child.ParentRunID != parent.RunID || child.Status != string(StatusRunning) {
		t.Fatalf("child = %#v", child)
	}
	oldParent, err := gormdb.GetSyncRun(parent.RunID)
	if err != nil {
		t.Fatal(err)
	}
	if oldParent.Status != string(StatusFailedAbnormalExit) {
		t.Fatalf("parent was changed to %q", oldParent.Status)
	}

	invalidParent := createAbnormalRun(t, "invalid-parent")
	if err := gormdb.SaveCheckpointForRun("生产订单主表", invalidParent.RunID, 0, ""); err != nil {
		t.Fatal(err)
	}
	invalidPlan, err := (&SyncEngine{}).PrepareRecovery(invalidParent.RunID, false)
	if err != nil {
		t.Fatal(err)
	}
	if invalidPlan.RunID != "" || len(invalidPlan.Notices) != 1 {
		t.Fatalf("invalid recovery plan = %#v", invalidPlan)
	}
	notices, err := gormdb.ListRecoveryNotices(invalidParent.RunID)
	if err != nil {
		t.Fatal(err)
	}
	if len(notices) != 1 || notices[0].Level != "warning" || notices[0].FormName != "生产订单主表" || notices[0].Message == "" {
		t.Fatalf("persisted invalid checkpoint notices = %#v", notices)
	}

	noCheckpoint := createAbnormalRun(t, "no-checkpoint-parent")
	noCheckpointPlan, err := (&SyncEngine{}).PrepareRecovery(noCheckpoint.RunID, false)
	if err != nil {
		t.Fatal(err)
	}
	if noCheckpointPlan.RunID != "" || len(noCheckpointPlan.Notices) != 1 {
		t.Fatalf("no checkpoint plan = %#v", noCheckpointPlan)
	}
	notices, err = gormdb.ListRecoveryNotices(noCheckpoint.RunID)
	if err != nil {
		t.Fatal(err)
	}
	if len(notices) != 1 || notices[0].Level != "warning" {
		t.Fatalf("persisted no-checkpoint notices = %#v", notices)
	}
}

type recoveryTestWriter struct {
	mu          sync.Mutex
	deleteCalls int
}

func (w *recoveryTestWriter) Upsert(context.Context, string, []map[string]interface{}, []string, []string, map[string]string) (int, error) {
	return 0, nil
}
func (w *recoveryTestWriter) DeleteOrphaned(context.Context, string, []map[string]interface{}, []string) (int, error) {
	w.mu.Lock()
	w.deleteCalls++
	w.mu.Unlock()
	return 1, nil
}
func (w *recoveryTestWriter) Close() error { return nil }

func TestRecoveryUsesCheckpointPositionClearsAfterWriteAndSkipsOrphanDelete(t *testing.T) {
	setupRecoveryTest(t)
	parent := createAbnormalRun(t, "replay-parent")
	if err := gormdb.SaveCheckpointForRun("生产订单主表", parent.RunID, 120, ""); err != nil {
		t.Fatal(err)
	}
	writer := &recoveryTestWriter{}
	engine := newRecoveryTestEngine(writer)
	var gotStart int
	engine.fetchRows = func(ctx context.Context, formName string, start int) (*kind.QueryResult, error) {
		if formName != "生产订单主表" {
			t.Fatalf("fetched unexpected form %q", formName)
		}
		gotStart = start
		return &kind.QueryResult{Rows: []map[string]interface{}{{"FID": "1"}}}, nil
	}
	engine.writeRowsFunc = func(context.Context, string, []map[string]interface{}, []string, map[string]string) (int, error) {
		return 1, nil
	}
	plan, err := engine.PrepareRecovery(parent.RunID, false)
	if err != nil {
		t.Fatal(err)
	}
	result, err := engine.SyncDataWithRunID(context.Background(), plan.RunID, plan.Forms, "full", false)
	if err != nil {
		t.Fatal(err)
	}
	if result.Status != StatusSuccess || gotStart != 120 {
		t.Fatalf("result=%#v start=%d", result, gotStart)
	}
	child, err := gormdb.GetSyncRun(plan.RunID)
	if err != nil {
		t.Fatal(err)
	}
	if child.Status != string(StatusSuccess) || child.ParentRunID != parent.RunID {
		t.Fatalf("successful child = %#v", child)
	}
	parentAfter, err := gormdb.GetSyncRun(parent.RunID)
	if err != nil {
		t.Fatal(err)
	}
	if parentAfter.Status != string(StatusFailedAbnormalExit) {
		t.Fatalf("successful recovery changed parent to %q", parentAfter.Status)
	}
	cp, err := gormdb.GetCheckpoint("生产订单主表")
	if err != nil {
		t.Fatal(err)
	}
	if cp != nil {
		t.Fatalf("successful recovery kept checkpoint: %#v", cp)
	}
	writer.mu.Lock()
	deleteCalls := writer.deleteCalls
	writer.mu.Unlock()
	if deleteCalls != 0 {
		t.Fatalf("recovery called orphan deletion %d times", deleteCalls)
	}
}

func TestRecoveryFailureKeepsCheckpointForRetry(t *testing.T) {
	setupRecoveryTest(t)
	parent := createAbnormalRun(t, "failed-replay-parent")
	if err := gormdb.SaveCheckpointForRun("生产订单主表", parent.RunID, 9, ""); err != nil {
		t.Fatal(err)
	}
	engine := newRecoveryTestEngine(nil)
	engine.fetchRows = func(context.Context, string, int) (*kind.QueryResult, error) {
		return &kind.QueryResult{Rows: []map[string]interface{}{{"FID": "1"}}}, nil
	}
	engine.writeRowsFunc = func(context.Context, string, []map[string]interface{}, []string, map[string]string) (int, error) {
		return 0, fmt.Errorf("fake Doris write failed")
	}
	plan, err := engine.PrepareRecovery(parent.RunID, false)
	if err != nil {
		t.Fatal(err)
	}
	result, err := engine.SyncDataWithRunID(context.Background(), plan.RunID, plan.Forms, "full", false)
	if err != nil {
		t.Fatal(err)
	}
	if result.Status != StatusFailed {
		t.Fatalf("result status = %q, want failed", result.Status)
	}
	child, err := gormdb.GetSyncRun(plan.RunID)
	if err != nil {
		t.Fatal(err)
	}
	if child.Status != string(StatusFailed) || child.ParentRunID != parent.RunID {
		t.Fatalf("failed child = %#v", child)
	}
	parentAfter, err := gormdb.GetSyncRun(parent.RunID)
	if err != nil {
		t.Fatal(err)
	}
	if parentAfter.Status != string(StatusFailedAbnormalExit) {
		t.Fatalf("failed recovery changed parent to %q", parentAfter.Status)
	}
	cp, err := gormdb.GetCheckpoint("生产订单主表")
	if err != nil {
		t.Fatal(err)
	}
	if cp == nil || cp.LastPosition != 9 || cp.RunID != parent.RunID {
		t.Fatalf("failed recovery checkpoint = %#v", cp)
	}
}

func TestRecoveryIdentityFailureFailsFormAndSkipsOrphanDelete(t *testing.T) {
	setupRecoveryTest(t)
	parent := createAbnormalRun(t, "identity-parent")
	if err := gormdb.SaveCheckpointForRun("生产订单主表", parent.RunID, 10, ""); err != nil {
		t.Fatal(err)
	}
	writer := &recoveryTestWriter{}
	engine := newRecoveryTestEngine(writer)
	engine.fetchRows = func(context.Context, string, int) (*kind.QueryResult, error) {
		return &kind.QueryResult{Rows: []map[string]interface{}{{"FID": "1"}}}, nil
	}
	engine.writeRowsFunc = func(context.Context, string, []map[string]interface{}, []string, map[string]string) (int, error) {
		return 1, nil
	}
	plan, err := engine.PrepareRecovery(parent.RunID, false)
	if err != nil {
		t.Fatal(err)
	}
	if err := gormdb.DB.Where("run_id = ?", parent.RunID).Delete(&gormdb.SyncRun{}).Error; err != nil {
		t.Fatal(err)
	}
	result, err := engine.SyncDataWithRunID(context.Background(), plan.RunID, plan.Forms, "full", false)
	if err != nil {
		t.Fatal(err)
	}
	if result.Status != StatusFailed {
		t.Fatalf("identity failure result status = %q", result.Status)
	}
	writer.mu.Lock()
	deleteCalls := writer.deleteCalls
	writer.mu.Unlock()
	if deleteCalls != 0 {
		t.Fatalf("identity failure called orphan deletion %d times", deleteCalls)
	}
}

func TestGracefulStopWaitsForSubmittedWrite(t *testing.T) {
	setupRecoveryTest(t)
	parent := createAbnormalRun(t, "graceful-parent")
	if err := gormdb.SaveCheckpointForRun("生产订单主表", parent.RunID, 4, ""); err != nil {
		t.Fatal(err)
	}
	engine := newRecoveryTestEngine(nil)
	engine.fetchRows = func(context.Context, string, int) (*kind.QueryResult, error) {
		return &kind.QueryResult{Rows: []map[string]interface{}{{"FID": "1"}}}, nil
	}
	writeStarted := make(chan struct{})
	releaseWrite := make(chan struct{})
	writerCanceled := make(chan struct{})
	engine.writeRowsFunc = func(ctx context.Context, _ string, _ []map[string]interface{}, _ []string, _ map[string]string) (int, error) {
		close(writeStarted)
		select {
		case <-releaseWrite:
			return 1, nil
		case <-ctx.Done():
			close(writerCanceled)
			return 0, ctx.Err()
		}
	}
	plan, err := engine.PrepareRecovery(parent.RunID, false)
	if err != nil {
		t.Fatal(err)
	}
	resultDone := make(chan *SyncResult, 1)
	go func() {
		result, err := engine.SyncDataWithRunID(context.Background(), plan.RunID, plan.Forms, "full", false)
		if err != nil {
			t.Errorf("recovery sync failed: %v", err)
		}
		resultDone <- result
	}()
	<-writeStarted
	stopDone := make(chan error, 1)
	go func() { stopDone <- engine.GracefulStop(context.Background()) }()
	select {
	case err := <-stopDone:
		t.Fatalf("graceful stop returned before write completed: %v", err)
	case <-time.After(20 * time.Millisecond):
	}
	select {
	case <-writerCanceled:
		t.Fatal("graceful stop canceled an already submitted writer")
	default:
	}
	close(releaseWrite)
	if err := <-stopDone; err != nil {
		t.Fatal(err)
	}
	result := <-resultDone
	if result.Status != StatusStopped {
		t.Fatalf("graceful result status = %q, want stopped", result.Status)
	}
	cp, err := gormdb.GetCheckpoint("生产订单主表")
	if err != nil {
		t.Fatal(err)
	}
	if cp != nil {
		t.Fatalf("drained successful recovery kept checkpoint: %#v", cp)
	}
}

func TestFullRunGracefulStopSkipsOrphanDeleteAndFinishesStopped(t *testing.T) {
	setupRecoveryTest(t)
	if _, err := gormdb.CreateSyncRun("full-graceful-stop", "test", "full"); err != nil {
		t.Fatal(err)
	}
	writer := &recoveryTestWriter{}
	engine := newRecoveryTestEngine(writer)
	engine.formQuery = func(string) (config.FormQuery, bool) {
		return config.FormQuery{FormID: "TEST_FORM", FieldKeys: "FID,FENTRYID"}, true
	}
	engine.fetchRows = func(context.Context, string, int) (*kind.QueryResult, error) {
		return &kind.QueryResult{Rows: []map[string]interface{}{{"FID": "1", "FENTRYID": "1"}}}, nil
	}
	writeStarted := make(chan struct{})
	releaseWrite := make(chan struct{})
	engine.writeRowsFunc = func(context.Context, string, []map[string]interface{}, []string, map[string]string) (int, error) {
		close(writeStarted)
		<-releaseWrite
		return 1, nil
	}
	if err := engine.PrepareRun("full-graceful-stop", false); err != nil {
		t.Fatal(err)
	}
	resultDone := make(chan *SyncResult, 1)
	go func() {
		result, err := engine.SyncDataWithRunID(context.Background(), "full-graceful-stop", []string{"销售订单"}, "full", false)
		if err != nil {
			t.Errorf("full sync failed: %v", err)
			return
		}
		resultDone <- result
	}()
	<-writeStarted
	if !engine.RequestGracefulStop("full-graceful-stop") {
		t.Fatal("failed to request graceful stop")
	}
	close(releaseWrite)
	result := <-resultDone
	if result.Status != StatusStopped {
		t.Fatalf("result status = %q, want stopped", result.Status)
	}
	run, err := gormdb.GetSyncRun("full-graceful-stop")
	if err != nil {
		t.Fatal(err)
	}
	if run.Status != string(StatusStopped) {
		t.Fatalf("persisted status = %q, want stopped", run.Status)
	}
	writer.mu.Lock()
	deleteCalls := writer.deleteCalls
	writer.mu.Unlock()
	if deleteCalls != 0 {
		t.Fatalf("graceful full run called orphan deletion %d times", deleteCalls)
	}
}

func TestPreparedRunStoppedBeforeRunnerDoesNotExecuteAndFinishesStopped(t *testing.T) {
	setupRecoveryTest(t)
	if _, err := gormdb.CreateSyncRun("pending-stop", "test", "full"); err != nil {
		t.Fatal(err)
	}
	engine := newRecoveryTestEngine(nil)
	fetchCalled := make(chan struct{}, 1)
	engine.fetchRows = func(context.Context, string, int) (*kind.QueryResult, error) {
		fetchCalled <- struct{}{}
		return &kind.QueryResult{Rows: []map[string]interface{}{{"FID": "1"}}}, nil
	}
	if err := engine.PrepareRun("pending-stop", false); err != nil {
		t.Fatal(err)
	}
	if err := engine.GracefulStop(context.Background()); err != nil {
		t.Fatal(err)
	}
	result, err := engine.SyncDataWithRunID(context.Background(), "pending-stop", []string{"销售订单"}, "full", false)
	if err != nil {
		t.Fatal(err)
	}
	if result.Status != StatusStopped {
		t.Fatalf("pending runner result status = %q, want stopped", result.Status)
	}
	select {
	case <-fetchCalled:
		t.Fatal("pending runner executed fetch after shutdown")
	default:
	}
	run, err := gormdb.GetSyncRun("pending-stop")
	if err != nil {
		t.Fatal(err)
	}
	if run.Status != string(StatusStopped) {
		t.Fatalf("pending runner persisted status = %q, want stopped", run.Status)
	}
}

func TestGracefulStopTimeoutCancelsAndKeepsCheckpoint(t *testing.T) {
	setupRecoveryTest(t)
	parent := createAbnormalRun(t, "timeout-parent")
	if err := gormdb.SaveCheckpointForRun("生产订单主表", parent.RunID, 6, ""); err != nil {
		t.Fatal(err)
	}
	engine := newRecoveryTestEngine(nil)
	engine.fetchRows = func(context.Context, string, int) (*kind.QueryResult, error) {
		return &kind.QueryResult{Rows: []map[string]interface{}{{"FID": "1"}}}, nil
	}
	writeStarted := make(chan struct{})
	writeCanceled := make(chan struct{})
	engine.writeRowsFunc = func(ctx context.Context, _ string, _ []map[string]interface{}, _ []string, _ map[string]string) (int, error) {
		close(writeStarted)
		select {
		case <-ctx.Done():
			close(writeCanceled)
			return 0, ctx.Err()
		case <-time.After(time.Second):
			return 1, nil
		}
	}
	plan, err := engine.PrepareRecovery(parent.RunID, false)
	if err != nil {
		t.Fatal(err)
	}
	resultDone := make(chan *SyncResult, 1)
	go func() {
		result, err := engine.SyncDataWithRunID(context.Background(), plan.RunID, plan.Forms, "full", false)
		if err != nil {
			t.Errorf("recovery sync failed: %v", err)
		}
		resultDone <- result
	}()
	<-writeStarted
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
	defer cancel()
	if err := engine.GracefulStop(ctx); err != context.DeadlineExceeded {
		t.Fatalf("graceful timeout error = %v", err)
	}
	select {
	case <-writeCanceled:
	case <-time.After(time.Second):
		t.Fatal("writer did not observe shutdown cancellation")
	}
	run, err := gormdb.GetSyncRun(plan.RunID)
	if err != nil {
		t.Fatal(err)
	}
	if run.Status != string(StatusFailedAbnormalExit) {
		t.Fatalf("timed out recovery status = %q", run.Status)
	}
	cp, err := gormdb.GetCheckpoint("生产订单主表")
	if err != nil {
		t.Fatal(err)
	}
	if cp == nil || cp.LastPosition != 6 {
		t.Fatalf("timed out recovery checkpoint = %#v", cp)
	}
	<-resultDone
}

func TestGracefulStopCancelsBlockingKingdeePaginationRequest(t *testing.T) {
	if os.Getenv("SYNCENGINE_BLOCKING_PAGINATION_TEST") == "" {
		cmd := exec.Command(os.Args[0], "-test.run", "^"+t.Name()+"$")
		cmd.Env = append(os.Environ(), "SYNCENGINE_BLOCKING_PAGINATION_TEST=1")
		if output, err := cmd.CombinedOutput(); err != nil {
			t.Fatalf("isolated blocking pagination test failed: %v\n%s", err, output)
		}
		return
	}

	setupRecoveryTest(t)
	secondPageStarted := make(chan struct{})
	secondPageCanceled := make(chan struct{})
	var requestMu sync.Mutex
	var startRows []int
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer r.Body.Close()
		if r.URL.Path == "/login" {
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"LoginResultType":1,"SessionId":"local-session"}`))
			return
		}
		if r.URL.Path != "/query" {
			http.NotFound(w, r)
			return
		}

		var payload struct {
			Data struct {
				StartRow int `json:"StartRow"`
				Limit    int `json:"Limit"`
			} `json:"data"`
		}
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		if payload.Data.Limit != 2 {
			http.Error(w, fmt.Sprintf("unexpected page size %d", payload.Data.Limit), http.StatusBadRequest)
			return
		}
		requestMu.Lock()
		startRows = append(startRows, payload.Data.StartRow)
		requestMu.Unlock()

		switch payload.Data.StartRow {
		case 0:
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"Result":{"Rows":[{"FID":"1"},{"FID":"2"}]}}`))
		case 2:
			close(secondPageStarted)
			<-r.Context().Done()
			close(secondPageCanceled)
		case 4:
			http.Error(w, "third page must not be requested", http.StatusInternalServerError)
		default:
			http.Error(w, fmt.Sprintf("unexpected StartRow %d", payload.Data.StartRow), http.StatusBadRequest)
		}
	}))
	defer server.Close()

	configPath := filepath.Join(t.TempDir(), "config.ini")
	content := fmt.Sprintf("[KINGDEE]\nlogin_url = %s/login\nquery_url = %s/query\npage_size = 2\nmax_pages = 10\nrate_limit_qps = 1000\n", server.URL, server.URL)
	if err := os.WriteFile(configPath, []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := config.Load(configPath); err != nil {
		t.Fatalf("load local Kingdee test config: %v", err)
	}

	const runID = "blocking-pagination-stop"
	if _, err := gormdb.CreateSyncRun(runID, "test", "full"); err != nil {
		t.Fatal(err)
	}
	engine := newRecoveryTestEngine(&recoveryTestWriter{})
	if err := engine.PrepareRun(runID, false); err != nil {
		t.Fatal(err)
	}
	resultDone := make(chan *SyncResult, 1)
	go func() {
		// 使用非游标表单名：销售订单已加入游标分页列表，游标路径不走 StartRow
		// 分页且要求完整游标字段，与本测试的 httptest server（StartRow 0→2→4）不兼容
		result, err := engine.SyncDataWithRunID(context.Background(), runID, []string{"测试表单"}, "full", false)
		if err != nil {
			t.Errorf("sync failed: %v", err)
			return
		}
		resultDone <- result
	}()

	select {
	case <-secondPageStarted:
	case <-time.After(time.Second):
		t.Fatal("second Kingdee page request did not reach the test server")
	}
	if err := engine.GracefulStop(context.Background()); err != nil {
		t.Fatalf("GracefulStop() error = %v", err)
	}
	select {
	case <-secondPageCanceled:
	case <-time.After(time.Second):
		t.Fatal("blocking second Kingdee page did not observe request context cancellation")
	}
	result := <-resultDone
	if result.Status != StatusStopped {
		t.Fatalf("sync result status = %q, want stopped", result.Status)
	}
	requestMu.Lock()
	gotStartRows := append([]int(nil), startRows...)
	requestMu.Unlock()
	if !reflect.DeepEqual(gotStartRows, []int{0, 2}) {
		t.Fatalf("Kingdee query StartRow sequence = %#v, want [0 2] with no third page", gotStartRows)
	}
}
