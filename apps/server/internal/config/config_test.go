package config

import (
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

func TestFormQueryGetFilter(t *testing.T) {
	tests := []struct {
		name  string
		value interface{}
		want  string
	}{
		{name: "string", value: "FSTATUS = 'A'", want: "FSTATUS = 'A'"},
		{name: "array is handled separately", value: []interface{}{"A", "B"}, want: ""},
		{name: "unsupported value", value: 123, want: ""},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			query := FormQuery{FilterString: tt.value}
			if got := query.GetFilter(); got != tt.want {
				t.Fatalf("GetFilter() = %q, want %q", got, tt.want)
			}
		})
	}
}

func TestFormToTableName(t *testing.T) {
	tests := map[string]string{
		"物料":           "bd_material",
		"销售订单":         "saleorder",
		"物料清单子项":       "eng_bomchild",
		"Unknown Form": "unknownform",
	}

	for form, want := range tests {
		if got := FormToTableName(form); got != want {
			t.Errorf("FormToTableName(%q) = %q, want %q", form, got, want)
		}
	}
}

func TestGetConfiguredFormNamesReturnsSortedSnapshot(t *testing.T) {
	mu.Lock()
	previous := instance
	instance = &Config{FormQueries: map[string]FormQuery{"物料": {}, "客户资料": {}}}
	mu.Unlock()
	t.Cleanup(func() {
		mu.Lock()
		instance = previous
		mu.Unlock()
	})

	got := GetConfiguredFormNames()
	want := []string{"客户资料", "物料"}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("configured form names = %#v, want %#v", got, want)
	}
	got[0] = "changed"
	if next := GetConfiguredFormNames(); !reflect.DeepEqual(next, want) {
		t.Fatalf("configured form names leaked mutable state: %#v", next)
	}
}

func TestFormQueryCandidatesPreferConfiguredDirectory(t *testing.T) {
	root := t.TempDir()
	configured := filepath.Join(root, "configured")
	if err := os.MkdirAll(configured, 0o755); err != nil {
		t.Fatal(err)
	}
	t.Setenv("SYNC_CONFIG_DIR", configured)

	got := formQueryCandidates(filepath.Join(root, "config.local.ini"))
	want := filepath.Join(configured, "form-queries.json")
	if len(got) == 0 || got[0] != want {
		t.Fatalf("candidates = %#v, want first %q", got, want)
	}
}

func TestGetEffectiveDatabaseMergesCompatibleSection(t *testing.T) {
	cfg := &Config{
		Database: DatabaseConfig{Type: "mysql"},
		MySQL: DatabaseConfig{
			Host:     "doris.test",
			Port:     9030,
			User:     "reader",
			Password: "redacted",
			DBName:   "sync_db",
		},
	}

	got := cfg.GetEffectiveDatabase()
	if got.Type != "mysql" || got.Host != "doris.test" || got.Port != 9030 || got.User != "reader" || got.Password != "redacted" || got.DBName != "sync_db" {
		t.Fatalf("GetEffectiveDatabase() = %+v, want values merged from MYSQL", got)
	}
}
