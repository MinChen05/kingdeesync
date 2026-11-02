package syncengine

import (
	"context"
	"strings"
	"testing"
	"time"
)

func TestCleanupContextIgnoresParentCancellation(t *testing.T) {
	parent, cancel := context.WithCancel(context.Background())
	cancel()

	cleanupCtx, cancelCleanup := cleanupContext(parent)
	defer cancelCleanup()

	if cleanupCtx.Err() != nil {
		t.Fatalf("清理上下文不得继承父取消，否则 staging DROP 与 ROLLBACK 必然失败: %v", cleanupCtx.Err())
	}
	if _, ok := cleanupCtx.Deadline(); !ok {
		t.Fatal("清理上下文必须自带超时，避免无界挂起")
	}
}

func TestCleanupContextKeepsParentValues(t *testing.T) {
	type ctxKey struct{}
	base, cancel := context.WithCancel(context.Background())
	defer cancel()
	parent := context.WithValue(base, ctxKey{}, "run-1")
	cancel()

	cleanupCtx, cancelCleanup := cleanupContext(parent)
	defer cancelCleanup()

	if got, _ := cleanupCtx.Value(ctxKey{}).(string); got != "run-1" {
		t.Fatalf("清理上下文应保留父上下文取值（WithoutCancel 而非 Background），got=%q", got)
	}
}

func TestCleanupContextAcceptsNilParent(t *testing.T) {
	cleanupCtx, cancelCleanup := cleanupContext(nil)
	defer cancelCleanup()
	if cleanupCtx == nil || cleanupCtx.Err() != nil {
		t.Fatalf("nil 父上下文应回退到 Background，got=%v", cleanupCtx)
	}
	if dl, ok := cleanupCtx.Deadline(); !ok || time.Until(dl) > cleanupTimeout {
		t.Fatalf("清理超时未生效: %v", cleanupTimeout)
	}
}

func TestBuildDirectKeyCountQueryUsesFullCompositeKey(t *testing.T) {
	writer := &SQLServerWriter{}
	query, args := writer.buildDirectKeyCountQuery("stk_instock", []string{"FID", "FENTRYID"}, []map[string]interface{}{
		{"FID": float64(1), "FENTRYID": float64(11)},
		{"FID": float64(1), "FENTRYID": float64(12)},
	}, nil)

	if !strings.Contains(query, "VALUES (@p1,@p2),(@p3,@p4)") {
		t.Fatalf("query should stage every batch row, got: %s", query)
	}
	if !strings.Contains(query, "EXISTS") {
		t.Fatalf("query should count each source row at most once, got: %s", query)
	}
	for _, want := range []string{"t.[FID] = s.[FID]", "t.[FENTRYID] = s.[FENTRYID]"} {
		if !strings.Contains(query, want) {
			t.Fatalf("query missing composite key predicate %q: %s", want, query)
		}
	}
	if len(args) != 4 {
		t.Fatalf("args = %d, want 4", len(args))
	}
	wantArgs := []interface{}{float64(1), float64(11), float64(1), float64(12)}
	for i := range wantArgs {
		if args[i] != wantArgs[i] {
			t.Fatalf("args[%d] = %#v, want %#v", i, args[i], wantArgs[i])
		}
	}
}
