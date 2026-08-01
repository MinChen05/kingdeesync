package syncengine

import "testing"

func TestEvaluateOrphanDeleteBlocksInvalidSnapshots(t *testing.T) {
	tests := []OrphanSafetyInput{
		{SourceCount: 0},
		{SourceCount: 100, DuplicateKeys: 1},
		{SourceCount: 100, PartialWrite: true},
		{SourceCount: 100, FilteredRows: 1},
		{SourceCount: 89, PreviousSourceCount: 100},
	}
	for _, input := range tests {
		if got := EvaluateOrphanDelete(input); got.Decision != OrphanDeleteBlocked {
			t.Fatalf("EvaluateOrphanDelete(%+v) = %+v", input, got)
		}
	}
}

func TestEvaluateOrphanDeleteThresholds(t *testing.T) {
	auto := EvaluateOrphanDelete(OrphanSafetyInput{SourceCount: 9900, TargetCount: 10000, OrphanCount: 100})
	if auto.Decision != OrphanDeleteAutoApproved {
		t.Fatalf("automatic decision = %+v", auto)
	}
	ratio := EvaluateOrphanDelete(OrphanSafetyInput{SourceCount: 9899, TargetCount: 10000, OrphanCount: 101})
	if ratio.Decision != OrphanDeleteApprovalRequired {
		t.Fatalf("ratio decision = %+v", ratio)
	}
	absolute := EvaluateOrphanDelete(OrphanSafetyInput{SourceCount: 200000, TargetCount: 201001, OrphanCount: 1001})
	if absolute.Decision != OrphanDeleteApprovalRequired {
		t.Fatalf("absolute decision = %+v", absolute)
	}
}
