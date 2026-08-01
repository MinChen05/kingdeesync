package syncengine

import "fmt"

type OrphanDeleteDecision string

const (
	OrphanDeleteBlocked          OrphanDeleteDecision = "blocked"
	OrphanDeleteAutoApproved     OrphanDeleteDecision = "auto_approved"
	OrphanDeleteApprovalRequired OrphanDeleteDecision = "approval_required"
)

type OrphanSafetyInput struct {
	SourceCount         int64
	PreviousSourceCount int64
	TargetCount         int64
	OrphanCount         int64
	DuplicateKeys       int64
	PartialWrite        bool
	FilteredRows        int64
}

type OrphanSafetyResult struct {
	Decision OrphanDeleteDecision
	Reason   string
}

func EvaluateOrphanDelete(input OrphanSafetyInput) OrphanSafetyResult {
	if input.SourceCount <= 0 {
		return OrphanSafetyResult{Decision: OrphanDeleteBlocked, Reason: "source snapshot is empty"}
	}
	if input.DuplicateKeys > 0 {
		return OrphanSafetyResult{Decision: OrphanDeleteBlocked, Reason: "source snapshot contains duplicate business keys"}
	}
	if input.PartialWrite {
		return OrphanSafetyResult{Decision: OrphanDeleteBlocked, Reason: "snapshot write is partial"}
	}
	if input.FilteredRows > 0 {
		return OrphanSafetyResult{Decision: OrphanDeleteBlocked, Reason: "stream load filtered rows"}
	}
	if input.OrphanCount < 0 || input.TargetCount < 0 || input.OrphanCount > input.TargetCount {
		return OrphanSafetyResult{Decision: OrphanDeleteBlocked, Reason: "invalid orphan or target count"}
	}
	if input.PreviousSourceCount > 0 && input.SourceCount*100 < input.PreviousSourceCount*90 {
		return OrphanSafetyResult{Decision: OrphanDeleteBlocked, Reason: "source count declined by more than 10 percent"}
	}
	if input.OrphanCount == 0 {
		return OrphanSafetyResult{Decision: OrphanDeleteAutoApproved, Reason: "no orphan rows"}
	}
	if input.TargetCount > 0 && input.OrphanCount <= 1000 && input.OrphanCount*100 <= input.TargetCount {
		return OrphanSafetyResult{Decision: OrphanDeleteAutoApproved, Reason: "orphan count is within automatic threshold"}
	}
	return OrphanSafetyResult{
		Decision: OrphanDeleteApprovalRequired,
		Reason:   fmt.Sprintf("orphan count %d exceeds automatic threshold", input.OrphanCount),
	}
}
