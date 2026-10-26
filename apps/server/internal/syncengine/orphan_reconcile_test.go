package syncengine

import "testing"

func TestCanonicalSourceKeysIsDeterministicAndCountsDuplicates(t *testing.T) {
	first, firstHash, duplicates, err := canonicalSourceKeys([]map[string]interface{}{
		{"FID": 2, "FENTRYID": 1},
		{"FID": 1, "FENTRYID": 3},
		{"fid": 2, "fentryid": 1},
	}, []string{"FID", "FENTRYID"})
	if err != nil {
		t.Fatal(err)
	}
	_, secondHash, _, err := canonicalSourceKeys([]map[string]interface{}{
		{"FID": 1, "FENTRYID": 3},
		{"FID": 2, "FENTRYID": 1},
	}, []string{"FID", "FENTRYID"})
	if err != nil {
		t.Fatal(err)
	}
	if len(first) != 2 || duplicates != 1 || firstHash != secondHash {
		t.Fatalf("canonical keys len=%d duplicates=%d hashes=%s/%s", len(first), duplicates, firstHash, secondHash)
	}
}

func TestRenderKeyLiteralAvoidsScientificNotation(t *testing.T) {
	tests := []struct {
		name  string
		value interface{}
		want  string
	}{
		{"seven digit entry id", float64(9181671), "9181671"},
		{"six digit entry id", float64(915043), "915043"},
		{"nine digit id", float64(123456789), "123456789"},
		{"fractional", float64(1.5), "1.5"},
		{"int64", int64(9181671), "9181671"},
		{"string", "00123", "N'00123'"},
		{"string with quote", "O'Brien", "N'O''Brien'"},
		{"bool", true, "1"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := renderKeyLiteral(tt.value); got != tt.want {
				t.Fatalf("renderKeyLiteral(%v) = %q, want %q", tt.value, got, tt.want)
			}
		})
	}
}

func TestCanonicalSourceKeysRejectsMissingPhysicalKey(t *testing.T) {
	if _, _, _, err := canonicalSourceKeys([]map[string]interface{}{{"FID": 1}}, []string{"FID", "FDATE"}); err == nil {
		t.Fatal("expected missing partition key error")
	}
}
