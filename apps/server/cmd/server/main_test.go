package main

import (
	"path/filepath"
	"testing"
)

func TestDefaultConfigDirectory(t *testing.T) {
	got := defaultConfigDirectory(filepath.Join("/opt", "kingdee", "server"))
	want := filepath.Join("/opt", "kingdee", "packages", "sync-config")
	if got != want {
		t.Fatalf("config directory = %q, want %q", got, want)
	}
}

func TestFrontendDistCandidatesUseAppsWeb(t *testing.T) {
	got := frontendDistCandidates(filepath.Join("/opt", "kingdee", "server"))
	want := filepath.Join("/opt", "kingdee", "apps", "web", "dist")
	for _, candidate := range got {
		if candidate == want {
			return
		}
	}
	t.Fatalf("candidates = %#v, missing %q", got, want)
}
