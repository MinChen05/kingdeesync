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

func TestCanonicalSourceKeysRejectsMissingPhysicalKey(t *testing.T) {
	if _, _, _, err := canonicalSourceKeys([]map[string]interface{}{{"FID": 1}}, []string{"FID", "FDATE"}); err == nil {
		t.Fatal("expected missing partition key error")
	}
}
