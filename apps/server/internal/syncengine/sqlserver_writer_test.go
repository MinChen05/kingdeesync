package syncengine

import (
	"strings"
	"testing"
)

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
