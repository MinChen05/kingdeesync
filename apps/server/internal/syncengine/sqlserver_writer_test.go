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

func TestValidateSnapshotScope(t *testing.T) {
	cols := []string{"FID", "FBALANCEID", "FACCTYEAR", "FACCTPERIOD"}
	scope := []string{"FACCTYEAR", "FACCTPERIOD"}

	t.Run("无作用域列时跳过校验", func(t *testing.T) {
		groups, err := validateSnapshotScope([]map[string]interface{}{{"FID": int64(1)}}, []string{"FID"}, nil, nil)
		if err != nil || groups != 0 {
			t.Fatalf("空作用域应直接放行, groups=%d err=%v", groups, err)
		}
	})

	t.Run("作用域列不在写列中时拒绝", func(t *testing.T) {
		rows := []map[string]interface{}{{"FID": int64(1), "FACCTYEAR": "2026", "FACCTPERIOD": "1"}}
		if _, err := validateSnapshotScope(rows, []string{"FID", "FACCTYEAR"}, scope, nil); err == nil {
			t.Fatal("缺少 FACCTPERIOD 写列时必须拒绝，否则会静默退化成整表删除")
		}
	})

	t.Run("作用域值为 NULL 或空串时拒绝", func(t *testing.T) {
		nulls := []map[string]interface{}{
			{"FACCTYEAR": "2026", "FACCTPERIOD": nil},
		}
		if _, err := validateSnapshotScope(nulls, cols, scope, nil); err == nil {
			t.Fatal("NULL 作用域值会让 DELETE…JOIN 删不到旧行，必须拒绝")
		}
		blanks := []map[string]interface{}{
			{"FACCTYEAR": "2026", "FACCTPERIOD": "   "},
		}
		if _, err := validateSnapshotScope(blanks, cols, scope, nil); err == nil {
			t.Fatal("空串作用域值同样必须拒绝")
		}
	})

	t.Run("按金蝶源字段名取值", func(t *testing.T) {
		rows := []map[string]interface{}{
			{"FYEAR": "2026", "FPERIOD": "1"},
			{"FYEAR": "2026", "FPERIOD": "2"},
			{"FYEAR": "2026", "FPERIOD": "1"},
		}
		fieldMap := map[string]string{"FYEAR": "FACCTYEAR", "FPERIOD": "FACCTPERIOD"}
		groups, err := validateSnapshotScope(rows, cols, scope, fieldMap)
		if err != nil {
			t.Fatalf("应能通过 fieldMap 反查取值: %v", err)
		}
		if groups != 2 {
			t.Fatalf("作用域组合数 = %d, want 2", groups)
		}
	})

	t.Run("非法标识符拒绝", func(t *testing.T) {
		rows := []map[string]interface{}{{"FACCTYEAR": "2026", "FACCTPERIOD": "1"}}
		if _, err := validateSnapshotScope(rows, cols, []string{"FACCTYEAR]; DROP TABLE x"}, nil); err == nil {
			t.Fatal("作用域列名必须过标识符校验（会被拼接进 DELETE…JOIN）")
		}
	})
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
