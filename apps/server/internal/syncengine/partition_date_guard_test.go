package syncengine

import "testing"

func TestValidateSourceBusinessDatesRejectsCrossPartitionChange(t *testing.T) {
	err := validateSourceBusinessDates([]map[string]interface{}{
		{"FID": 1, "FDATE": "2025-03-31 00:00:00"},
		{"FID": 1, "FDATE": "2025-04-01 00:00:00"},
	}, []string{"FID"}, "FDATE")
	if err == nil {
		t.Fatal("expected cross-partition date change to be rejected")
	}
}

func TestValidateSourceBusinessDatesAcceptsRepeatedStableDate(t *testing.T) {
	err := validateSourceBusinessDates([]map[string]interface{}{
		{"FID": 1, "FENTRYID": 1, "FDATE": "2025-03-31 00:00:00"},
		{"FID": 1, "FENTRYID": 2, "FDATE": "2025-03-31 00:00:00"},
	}, []string{"FID", "FENTRYID"}, "FDATE")
	if err != nil {
		t.Fatal(err)
	}
}
