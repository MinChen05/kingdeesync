package config

import (
	"os"
	"path/filepath"
	"reflect"
	"testing"
	"time"

	"github.com/stretchr/testify/require"
	"gopkg.in/ini.v1"
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

func TestGetSyncRunTimeoutByType(t *testing.T) {
	old := instance
	t.Cleanup(func() { instance = old })

	instance = &Config{}
	instance.Sync.FullRunTimeoutMinutes = 240
	instance.Sync.IncrementalRunTimeoutMinutes = 30

	if got := GetSyncRunTimeout("full"); got != 240*time.Minute {
		t.Fatalf("full 超时应为 240 分钟，实际 %v", got)
	}
	if got := GetSyncRunTimeout("incremental"); got != 30*time.Minute {
		t.Fatalf("incremental 超时应为 30 分钟，实际 %v", got)
	}
	// 未知类型按增量口径兜底
	if got := GetSyncRunTimeout("whatever"); got != 30*time.Minute {
		t.Fatalf("未知类型应回退增量口径，实际 %v", got)
	}

	// 配置未加载时返回 0，由调用方兜底
	instance = nil
	if got := GetSyncRunTimeout("full"); got != 0 {
		t.Fatalf("配置未加载应返回 0，实际 %v", got)
	}
}

func TestDBProbeConfigDefaults(t *testing.T) {
	old := instance
	t.Cleanup(func() { instance = old })

	// 未加载配置：探活默认开启、默认 5 分钟
	instance = nil
	if !IsDBProbeEnabled() {
		t.Fatal("配置未加载时探活应默认开启")
	}
	if got := GetDBProbeInterval(); got != 5*time.Minute {
		t.Fatalf("配置未加载时探活间隔应默认 5 分钟，实际 %v", got)
	}

	// 已加载但字段缺省（Load 默认值填充前的裸结构）同样兜底
	instance = &Config{}
	if !IsDBProbeEnabled() {
		t.Fatal("字段缺省时探活应默认开启")
	}

	// 显式关闭
	disabled := false
	instance = &Config{}
	instance.Sync.DBProbeEnabled = &disabled
	if IsDBProbeEnabled() {
		t.Fatal("显式 false 时探活应关闭")
	}
	instance.Sync.DBProbeIntervalSecs = 60
	if got := GetDBProbeInterval(); got != time.Minute {
		t.Fatalf("探活间隔应为 60 秒，实际 %v", got)
	}
}

// TestFinalizeConfigAppliesFullPostProcessing 验证热重载与冷启动共用后处理链：
// 仅经 ini.Load→MapTo→finalizeConfig（不经过 Load）也必须得到默认值、
// 密码解密、INCREMENTAL_FIELDS 与 form-queries 加载。
// （原因：此前 Reload/watchConfig 各自实现不完整链路，热重载一次就静默坏掉）
func TestFinalizeConfigAppliesFullPostProcessing(t *testing.T) {
	t.Setenv("SYNC_ENCRYPTION_KEY", "finalize-config-test-key")
	encPw := EncryptPassword("my-secret")

	dir := t.TempDir()
	iniPath := filepath.Join(dir, "config.local.ini")
	content := "[KINGDEE]\nusername = u1\npassword = " + encPw + "\n[SQLSERVER]\nhost = h1\npassword = p#ss\n[INCREMENTAL_FIELDS]\nBD_MATERIAL = FModifyDate\n"
	require.NoError(t, os.WriteFile(iniPath, []byte(content), 0o600))

	f, err := ini.Load(iniPath)
	require.NoError(t, err)
	cfg := &Config{}
	require.NoError(t, f.MapTo(cfg))

	finalizeConfig(f, iniPath, cfg)

	// 默认值必须被补齐（此前 Reload 路径全部丢失）
	if cfg.Kingdee.Lcid != "2052" || cfg.Kingdee.PageSize != 9000 || cfg.Kingdee.MaxPages != 100000 {
		t.Fatalf("金蝶默认值未补齐: lcid=%q pageSize=%d maxPages=%d", cfg.Kingdee.Lcid, cfg.Kingdee.PageSize, cfg.Kingdee.MaxPages)
	}
	if cfg.Sync.SyncInterval != 120 || cfg.Sync.SyncType != "incremental" || cfg.Sync.TableConcurrency != 8 {
		t.Fatalf("同步默认值未补齐: %+v", cfg.Sync)
	}
	if cfg.Database.Type != "mysql" || cfg.Server.Host != "0.0.0.0" || cfg.Server.Port != 8000 {
		t.Fatalf("数据库/服务器默认值未补齐: dbType=%q host=%q port=%d", cfg.Database.Type, cfg.Server.Host, cfg.Server.Port)
	}
	if cfg.Sync.DBProbeEnabled == nil || !*cfg.Sync.DBProbeEnabled || cfg.Sync.DBProbeIntervalSecs != 300 {
		t.Fatal("探活默认值未补齐")
	}

	// ENC: 密文必须被解密回明文（此前 Reload 路径也有该步骤，但整条链路缺默认值；
	// 这里锁定完整链路缺一不可）
	if cfg.Kingdee.Password != "my-secret" {
		t.Fatalf("ENC 密码应被解密为 my-secret，实际 %q", cfg.Kingdee.Password)
	}

	// 含 # 的密码必须经 fixPasswordsFromFile 修复（ini 库会截断为注释）
	if cfg.SQLServer.Password != "p#ss" {
		t.Fatalf("含 # 的密码应被修复为 p#ss，实际 %q", cfg.SQLServer.Password)
	}

	// INCREMENTAL_FIELDS 必须按小写键加载
	if got := cfg.IncrementalFields["bd_material"]; got != "FModifyDate" {
		t.Fatalf("INCREMENTAL_FIELDS 未加载: %v", cfg.IncrementalFields)
	}
}

// TestValidateSQLIdentifier 覆盖标识符校验边界：
// 合法标识符、数字开头、中文、空白、SQL 注入片段、空串。
// （原因：该函数是所有表名/列名拼接的安全闸门）
func TestValidateSQLIdentifier(t *testing.T) {
	valid := []string{"bd_material", "T1", "_priv", "ArReceivable"}
	invalid := []string{"", "1abc", "表名", "a b", "a;b--", "a' OR '1'='1", "tbl; DROP TABLE x", "a-b", "a.b"}
	for _, name := range valid {
		if err := ValidateSQLIdentifier(name); err != nil {
			t.Fatalf("ValidateSQLIdentifier(%q) 应为合法: %v", name, err)
		}
	}
	for _, name := range invalid {
		if err := ValidateSQLIdentifier(name); err == nil {
			t.Fatalf("ValidateSQLIdentifier(%q) 应被拒绝", name)
		}
	}
	// FormToTableName 兜底会把中文表单名透传为表名，必须被闸门拦住
	if err := ValidateSQLIdentifier(FormToTableName("任意;注入")); err == nil {
		t.Fatal("中文/含注入字符的兜底表名必须被拒绝")
	}
}
