package config

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"

	"github.com/fsnotify/fsnotify"
	"github.com/kingdee-sync/go/internal/gormdb"
	"gopkg.in/ini.v1"
)

type KingdeeConfig struct {
	LoginURL          string  `ini:"login_url"`
	QueryURL          string  `ini:"query_url"`
	AcctID            string  `ini:"acct_id"`
	Username          string  `ini:"username"`
	Password          string  `ini:"password"`
	Lcid              string  `ini:"lcid"`
	PageSize          int     `ini:"page_size"`
	MaxPages          int     `ini:"max_pages"`
	RateLimitQPS      float64 `ini:"rate_limit_qps"`
	KeepSessionAlive  bool    `ini:"keep_session_alive"`
	KeepAliveInterval int     `ini:"keep_alive_interval_secs"`
}

type FormQuery struct {
	FormID       string      `json:"FormId"`
	FieldKeys    string      `json:"FieldKeys"`
	FilterString interface{} `json:"FilterString"`
	// FieldMap maps Kingdee API field names to database column names.
	// Example: {"FGROUP.FNAME": "FGROUP", "FSELLER.FNAME": "FSELLERNAME"}
	FieldMap map[string]string `json:"FieldMap,omitempty"`
	// DefaultValues contains acceptance-only target defaults used when the
	// legacy Python writer had no corresponding source field.
	DefaultValues map[string]interface{} `json:"DefaultValues,omitempty"`
}

func (q FormQuery) GetFilter() string {
	switch v := q.FilterString.(type) {
	case string:
		return v
	case []interface{}:
		// Join filter array
		parts := make([]string, 0, len(v))
		for _, item := range v {
			if s, ok := item.(string); ok {
				parts = append(parts, s)
			}
		}
		return "" // Return empty for now, filters handled separately
	default:
		return ""
	}
}

type DatabaseConfig struct {
	Type     string `ini:"type"`
	Host     string `ini:"host"`
	Port     int    `ini:"port"`
	User     string `ini:"user"`
	Password string `ini:"password"`
	DBName   string `ini:"database"`
}

type Config struct {
	Kingdee KingdeeConfig `ini:"KINGDEE"`
	Sync    struct {
		AutoSync         bool   `ini:"auto_sync"`
		SyncInterval     int    `ini:"sync_interval"`
		SyncType         string `ini:"sync_type"`
		TimeWindowDays   int    `ini:"time_window_days"`
		TableConcurrency int    `ini:"table_concurrency"`
	} `ini:"SYNC"`
	Database DatabaseConfig `ini:"DATABASE"`
	// Also read from [SQLSERVER] or [MYSQL] sections for compatibility with existing config.local.ini
	SQLServer DatabaseConfig `ini:"SQLSERVER"`
	MySQL     DatabaseConfig `ini:"MYSQL"`
	Server    struct {
		Host       string `ini:"host"`
		Port       int    `ini:"port"`
		CorsOrigin string `ini:"cors_origin"`
	} `ini:"SERVER"`
	FormQueries map[string]FormQuery `json:"-"`
	// IncrementalFields maps table/form name to its modify date field (e.g., "bd_material" -> "FMODIFYDATE")
	IncrementalFields map[string]string `ini:"-"`
}

// GetEffectiveDatabase returns the effective database config by merging DATABASE with SQLSERVER/MYSQL sections.
func (c *Config) GetEffectiveDatabase() DatabaseConfig {
	db := c.Database
	// Debug logging
	fmt.Printf("[CONFIG] Database section: type=%s, host=%s, user=%s, password_len=%d\n",
		c.Database.Type, c.Database.Host, c.Database.User, len(c.Database.Password))
	fmt.Printf("[CONFIG] SQLServer section: host=%s, user=%s, password_len=%d, db=%s\n",
		c.SQLServer.Host, c.SQLServer.User, len(c.SQLServer.Password), c.SQLServer.DBName)
	// If DATABASE.type is set but host is empty, try to merge from SQLSERVER/MYSQL
	if db.Type != "" && db.Host == "" {
		switch db.Type {
		case "sqlserver":
			if c.SQLServer.Host != "" {
				db.Host = c.SQLServer.Host
			}
			if c.SQLServer.Port != 0 {
				db.Port = c.SQLServer.Port
			}
			if c.SQLServer.User != "" {
				db.User = c.SQLServer.User
			}
			if c.SQLServer.Password != "" {
				db.Password = c.SQLServer.Password
			}
			if c.SQLServer.DBName != "" {
				db.DBName = c.SQLServer.DBName
			}
		case "mysql":
			if c.MySQL.Host != "" {
				db.Host = c.MySQL.Host
			}
			if c.MySQL.Port != 0 {
				db.Port = c.MySQL.Port
			}
			if c.MySQL.User != "" {
				db.User = c.MySQL.User
			}
			if c.MySQL.Password != "" {
				db.Password = c.MySQL.Password
			}
			if c.MySQL.DBName != "" {
				db.DBName = c.MySQL.DBName
			}
		}
	}
	// If DATABASE is empty, prefer the Doris/MySQL section. Go production writes
	// only through the MySQL protocol; SQL Server remains a read-only baseline.
	if db.Type == "" && c.MySQL.Host != "" {
		db = c.MySQL
		db.Type = "mysql"
	}
	return db
}

var (
	instance *Config
	mu       sync.RWMutex
)

// fixPasswordsFromFile manually parses the INI file to fix passwords that contain
// # or ; characters, which the ini library incorrectly treats as comment markers.
func fixPasswordsFromFile(path string, cfg *Config) error {
	f, err := os.Open(path)
	if err != nil {
		return err
	}
	defer f.Close()

	passwords := make(map[string]string) // section -> password
	currentSection := ""

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") || strings.HasPrefix(line, ";") {
			continue
		}
		if strings.HasPrefix(line, "[") && strings.HasSuffix(line, "]") {
			currentSection = strings.TrimSpace(line[1 : len(line)-1])
			continue
		}
		if currentSection == "SQLSERVER" || currentSection == "MYSQL" {
			if strings.HasPrefix(line, "password") {
				parts := strings.SplitN(line, "=", 2)
				if len(parts) == 2 {
					val := strings.TrimSpace(parts[1])
					// Remove surrounding quotes if present
					if len(val) >= 2 && val[0] == '"' && val[len(val)-1] == '"' {
						val = val[1 : len(val)-1]
					}
					passwords[currentSection] = val
				}
			}
		}
	}
	if err := scanner.Err(); err != nil {
		return err
	}

	// Apply fixed passwords
	if pw, ok := passwords["SQLSERVER"]; ok {
		cfg.SQLServer.Password = pw
	}
	if pw, ok := passwords["MYSQL"]; ok {
		cfg.MySQL.Password = pw
	}
	return nil
}

func Load(path string) (*Config, error) {
	mu.Lock()
	defer mu.Unlock()

	if instance != nil {
		return instance, nil
	}

	if path == "" {
		candidates := []string{
			"config.local.ini",
			"config.ini",
			filepath.Join("..", "config.local.ini"),
			filepath.Join("..", "config.ini"),
		}
		for _, p := range candidates {
			if _, err := os.Stat(p); err == nil {
				path = p
				break
			}
		}
		if path == "" {
			return nil, fmt.Errorf("config file not found")
		}
	}

	// Resolve to absolute path
	path, _ = filepath.Abs(path)

	// Config dir is project root (config.local.ini is at project root)
	configDir := filepath.Dir(path)

	f, err := ini.Load(path)
	if err != nil {
		return nil, fmt.Errorf("load config: %w", err)
	}

	cfg := &Config{}
	if err := f.MapTo(cfg); err != nil {
		return nil, fmt.Errorf("parse config: %w", err)
	}

	// Fix passwords that contain # or ; (ini library treats them as comments)
	// Manually parse the raw file to get correct password values.
	if err := fixPasswordsFromFile(path, cfg); err != nil {
		fmt.Printf("Warning: failed to fix passwords from config file: %v\n", err)
	}

	// Defaults
	if cfg.Kingdee.Lcid == "" {
		cfg.Kingdee.Lcid = "2052"
	}
	if cfg.Kingdee.PageSize == 0 {
		cfg.Kingdee.PageSize = 9000
	}
	if cfg.Kingdee.MaxPages == 0 {
		cfg.Kingdee.MaxPages = 100000
	}
	if cfg.Kingdee.RateLimitQPS == 0 {
		cfg.Kingdee.RateLimitQPS = 10
	}
	if cfg.Kingdee.KeepAliveInterval == 0 {
		cfg.Kingdee.KeepAliveInterval = 600
	}
	if cfg.Sync.SyncInterval == 0 {
		cfg.Sync.SyncInterval = 120
	}
	if cfg.Sync.SyncType == "" {
		cfg.Sync.SyncType = "incremental"
	}
	if cfg.Sync.TimeWindowDays == 0 {
		cfg.Sync.TimeWindowDays = 30
	}
	if cfg.Sync.TableConcurrency == 0 {
		cfg.Sync.TableConcurrency = 8
	}
	if cfg.Database.Type == "" {
		cfg.Database.Type = "mysql"
	}
	if cfg.Server.Host == "" {
		cfg.Server.Host = "0.0.0.0"
	}
	if cfg.Server.Port == 0 {
		cfg.Server.Port = 8000
	}

	// Load INCREMENTAL_FIELDS section
	cfg.IncrementalFields = make(map[string]string)
	if section, err := f.GetSection("INCREMENTAL_FIELDS"); err == nil {
		for _, key := range section.Keys() {
			cfg.IncrementalFields[strings.ToLower(key.Name())] = key.String()
		}
	}

	// Load form-queries.json relative to config dir
	if err := loadFormQueries(cfg, configDir); err != nil {
		fmt.Printf("Warning: failed to load form-queries.json: %v\n", err)
	}

	instance = cfg

	// Watch for changes
	go watchConfig(path)

	return cfg, nil
}

func loadFormQueries(cfg *Config, configDir string) error {
	for _, p := range formQueryCandidates(filepath.Join(configDir, "config.local.ini")) {
		data, err := os.ReadFile(p)
		if err != nil {
			continue
		}
		var queries map[string]FormQuery
		if err := json.Unmarshal(data, &queries); err != nil {
			continue
		}
		cfg.FormQueries = queries
		return nil
	}
	return fmt.Errorf("form-queries.json not found")
}

func formQueryCandidates(configPath string) []string {
	configDir := filepath.Dir(configPath)
	candidates := make([]string, 0, 3)
	if configuredDir := strings.TrimSpace(os.Getenv("SYNC_CONFIG_DIR")); configuredDir != "" {
		candidates = append(candidates, filepath.Join(configuredDir, "form-queries.json"))
	}
	return append(candidates,
		filepath.Join(configDir, "packages", "sync-config", "form-queries.json"),
		filepath.Join(configDir, "form-queries.json"),
	)
}

func GetFormQuery(formName string) (FormQuery, bool) {
	// Try database first
	if gormdb.DB != nil {
		var cfg gormdb.FormQueryConfig
		if err := gormdb.DB.Where("form_name = ?", formName).First(&cfg).Error; err == nil {
			return dbFormQueryToConfig(&cfg), true
		}
	}
	// Fallback to JSON config
	mu.RLock()
	defer mu.RUnlock()
	if instance == nil || instance.FormQueries == nil {
		return FormQuery{}, false
	}
	q, ok := instance.FormQueries[formName]
	return q, ok
}

// GetConfiguredFormNames returns a stable snapshot of every configured form
// that is not explicitly disabled via FormSetting.
func GetConfiguredFormNames() []string {
	// Try database first
	if gormdb.DB != nil {
		var configs []gormdb.FormQueryConfig
		if err := gormdb.DB.Find(&configs).Error; err == nil && len(configs) > 0 {
			disabled := gormdb.GetDisabledFormNames()
			forms := make([]string, 0, len(configs))
			for _, c := range configs {
				if !disabled[c.FormName] {
					forms = append(forms, c.FormName)
				}
			}
			sort.Strings(forms)
			return forms
		}
	}
	// Fallback to JSON config
	mu.RLock()
	defer mu.RUnlock()
	if instance == nil || len(instance.FormQueries) == 0 {
		return nil
	}
	disabled := gormdb.GetDisabledFormNames()
	forms := make([]string, 0, len(instance.FormQueries))
	for form := range instance.FormQueries {
		if !disabled[form] {
			forms = append(forms, form)
		}
	}
	sort.Strings(forms)
	return forms
}

// dbFormQueryToConfig converts a FormQueryConfig DB record to a FormQuery config struct.
func dbFormQueryToConfig(cfg *gormdb.FormQueryConfig) FormQuery {
	q := FormQuery{
		FormID:       cfg.FormID,
		FieldKeys:    cfg.FieldKeys,
		FilterString: cfg.FilterString,
	}
	if cfg.FieldMap != "" {
		json.Unmarshal([]byte(cfg.FieldMap), &q.FieldMap)
	}
	if cfg.DefaultValues != "" {
		json.Unmarshal([]byte(cfg.DefaultValues), &q.DefaultValues)
	}
	return q
}

func Get() *Config {
	mu.RLock()
	defer mu.RUnlock()
	return instance
}

// Reload reloads the config from file. Called when config is updated via API.
func Reload(path string) {
	mu.Lock()
	defer mu.Unlock()

	if path == "" {
		return
	}

	f, err := ini.Load(path)
	if err != nil {
		return
	}

	cfg := &Config{}
	if err := f.MapTo(cfg); err != nil {
		return
	}

	// Fix passwords
	fixPasswordsFromFile(path, cfg)

	// Reload incremental fields
	cfg.IncrementalFields = make(map[string]string)
	if section, err := f.GetSection("INCREMENTAL_FIELDS"); err == nil {
		for _, key := range section.Keys() {
			cfg.IncrementalFields[strings.ToLower(key.Name())] = key.String()
		}
	}

	// Reload form queries
	configDir := filepath.Dir(path)
	loadFormQueries(cfg, configDir)

	instance = cfg
}

// GetIncrementField returns the modify date field for a table/form.
// Checks by table name first, then form name, then falls back to "FModifyDate".
func GetIncrementField(tableName string, formName string) string {
	mu.RLock()
	defer mu.RUnlock()
	if instance == nil || instance.IncrementalFields == nil {
		return "FModifyDate"
	}
	// Try table name (lowercase)
	if field, ok := instance.IncrementalFields[strings.ToLower(tableName)]; ok {
		return field
	}
	// Try form name (lowercase)
	if field, ok := instance.IncrementalFields[strings.ToLower(formName)]; ok {
		return field
	}
	return "FModifyDate"
}

// FormToTableName maps Kingdee form names to DB table names.
// Mirrors the Python-side naming convention.
var formToTableName = map[string]string{
	"物料":        "bd_material",
	"仓库":        "bd_stock",
	"客户资料":      "customer",
	"销售订单":      "saleorder",
	"销售出库单":     "sal_outstock",
	"销售退货单":     "sal_returnstock",
	"发货通知单":     "sal_deliverynotice",
	"预测订单":      "pln_forecast",
	"生产订单主表":    "prd_mo",
	"生产订单明细":    "prd_moentry",
	"生产入库单":     "prd_instock",
	"生产用料清单主表":  "prd_ppbom",
	"生产用料清单明细表": "prd_ppbomentry",
	"物料清单":      "eng_bom",
	"物料清单子项":    "eng_bomchild",
	"采购订单":      "pur_purchaseorder",
	"采购入库单":     "stk_instock",
	"委外订单":      "sub_subreqorder",
	"应付单":       "ap_payable",
	"应收单":       "ar_receivable",
	"即时库存":      "stk_inventory",
	"科目余额表":     "gl_rpt_accountbalance",
}

func FormToTableName(formName string) string {
	if t, ok := formToTableName[formName]; ok {
		return t
	}
	// Fallback: use formName as-is (lowercase, spaces removed)
	s := strings.ToLower(formName)
	s = strings.ReplaceAll(s, " ", "")
	return s
}

func watchConfig(path string) {
	watcher, err := fsnotify.NewWatcher()
	if err != nil {
		return
	}
	defer watcher.Close()

	if err := watcher.Add(path); err != nil {
		return
	}

	for {
		select {
		case _, ok := <-watcher.Events:
			if !ok {
				return
			}
			mu.Lock()
			if f, err := ini.Load(path); err == nil {
				cfg := &Config{}
				if err := f.MapTo(cfg); err == nil {
					instance = cfg
				}
			}
			mu.Unlock()
		case _, ok := <-watcher.Errors:
			if !ok {
				return
			}
		}
	}
}
