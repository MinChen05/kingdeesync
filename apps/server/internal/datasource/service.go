package datasource

import (
	"fmt"
	"log"
	"net/url"
	"sync"
	"time"

	"github.com/kingdee-sync/go/internal/config"
	"github.com/kingdee-sync/go/internal/db"
	"github.com/kingdee-sync/go/internal/kind"
)

// DataSource represents a configured data source.
type DataSource struct {
	ID           string                 `json:"id"`
	Name         string                 `json:"name"`
	Type         string                 `json:"type"`   // "api" or "database"
	Status       string                 `json:"status"` // "ok", "error", "unknown"
	Latency      string                 `json:"latency"`
	LastTestTime string                 `json:"last_test_time"`
	AccountInfo  string                 `json:"account_info"`
	Config       map[string]interface{} `json:"config"`
}

// TestResult represents a connection test result.
type TestResult struct {
	DataSource string  `json:"data_source"`
	CheckItem  string  `json:"check_item"`
	Status     string  `json:"status"`
	DurationMs float64 `json:"duration_ms"`
	Message    string  `json:"message"`
	TestTime   string  `json:"test_time"`
}

// Service manages data source operations.
type Service struct {
	mu           sync.RWMutex
	lastTestTime time.Time
	lastResults  []TestResult
}

var instance *Service

func NewService() *Service {
	if instance != nil {
		return instance
	}
	instance = &Service{}
	return instance
}

func GetService() *Service {
	return instance
}

// GetDataSources returns all configured data sources with their status.
func (s *Service) GetDataSources() []DataSource {
	cfg := config.Get()
	if cfg == nil {
		return []DataSource{}
	}

	var sources []DataSource

	// Kingdee API data source
	apiStatus := "unknown"
	apiLatency := "--"
	apiAccount := cfg.Kingdee.AcctID
	if apiAccount == "" {
		apiAccount = "--"
	}

	// Check recent test results
	s.mu.RLock()
	for _, r := range s.lastResults {
		if r.DataSource == "kingdee" && r.Status == "ok" {
			apiStatus = "ok"
			apiLatency = fmt.Sprintf("%.0fms", r.DurationMs)
		}
	}
	s.mu.RUnlock()

	if apiStatus == "unknown" && cfg.Kingdee.LoginURL != "" {
		apiStatus = "configured"
	}

	apiURL := cfg.Kingdee.QueryURL
	if apiURL == "" {
		apiURL = cfg.Kingdee.LoginURL
	}

	sources = append(sources, DataSource{
		ID:           "kingdee",
		Name:         "金蝶云星空 API",
		Type:         "api",
		Status:       apiStatus,
		Latency:      apiLatency,
		LastTestTime: formatLastTest(s.lastTestTime),
		AccountInfo:  apiAccount,
		Config: map[string]interface{}{
			"api_url":     extractOrigin(apiURL),
			"acct_id":     cfg.Kingdee.AcctID,
			"username":    cfg.Kingdee.Username,
			"auth_status": "认证有效 (Token 自动刷新)",
		},
	})

	// Database data source
	dbStatus := "unknown"
	dbLatency := "--"
	dbAccount := cfg.Database.User
	if dbAccount == "" {
		dbAccount = "--"
	}

	s.mu.RLock()
	for _, r := range s.lastResults {
		if r.DataSource == "database" && r.Status == "ok" {
			dbStatus = "ok"
			dbLatency = fmt.Sprintf("%.0fms", r.DurationMs)
		}
	}
	s.mu.RUnlock()

	if dbStatus == "unknown" && db.DB != nil {
		dbStatus = "connected"
	}

	effectiveDB := cfg.GetEffectiveDatabase()
	poolStats := "未连接"
	if db.DB != nil {
		stats := db.DB.Stats()
		poolStats = fmt.Sprintf("正常 (活动连接: %d/%d)", stats.InUse, stats.MaxOpenConnections)
	}

	sources = append(sources, DataSource{
		ID:           "database",
		Name:         fmt.Sprintf("%s 数据库", effectiveDB.Type),
		Type:         "database",
		Status:       dbStatus,
		Latency:      dbLatency,
		LastTestTime: formatLastTest(s.lastTestTime),
		AccountInfo:  dbAccount,
		Config: map[string]interface{}{
			"server":      fmt.Sprintf("%s:%d", effectiveDB.Host, effectiveDB.Port),
			"database":    effectiveDB.DBName,
			"write_perm":  "可写入",
			"pool_status": poolStats,
		},
	})

	return sources
}

// GetDataSourceByID returns a single data source by ID.
func (s *Service) GetDataSourceByID(id string) (*DataSource, error) {
	sources := s.GetDataSources()
	for _, src := range sources {
		if src.ID == id {
			return &src, nil
		}
	}
	return nil, fmt.Errorf("data source not found: %s", id)
}

// TestAllConnections tests all data source connections.
func (s *Service) TestAllConnections() []TestResult {
	s.mu.Lock()
	defer s.mu.Unlock()

	var results []TestResult
	var wg sync.WaitGroup
	var mu sync.Mutex

	// Test Kingdee API
	wg.Add(1)
	go func() {
		defer wg.Done()
		start := time.Now()
		client := kind.NewKingdeeClient()
		ok := client.TestConnection()
		duration := time.Since(start).Milliseconds()

		status := "ok"
		msg := "连接正常"
		if !ok {
			status = "error"
			msg = "连接失败"
		}

		r := TestResult{
			DataSource: "kingdee",
			CheckItem:  "API 连接测试",
			Status:     status,
			DurationMs: float64(duration),
			Message:    msg,
			TestTime:   time.Now().Format("2006-01-02 15:04:05"),
		}
		mu.Lock()
		results = append(results, r)
		mu.Unlock()
	}()

	// Test Database
	wg.Add(1)
	go func() {
		defer wg.Done()
		start := time.Now()

		var status string
		var msg string
		if db.DB == nil {
			status = "error"
			msg = "数据库未初始化"
		} else {
			err := db.DB.Ping()
			if err != nil {
				status = "error"
				msg = fmt.Sprintf("连接失败: %v", err)
			} else {
				status = "ok"
				msg = "连接正常"
			}
		}

		duration := time.Since(start).Milliseconds()

		r := TestResult{
			DataSource: "database",
			CheckItem:  "数据库连接测试",
			Status:     status,
			DurationMs: float64(duration),
			Message:    msg,
			TestTime:   time.Now().Format("2006-01-02 15:04:05"),
		}
		mu.Lock()
		results = append(results, r)
		mu.Unlock()
	}()

	wg.Wait()

	s.lastTestTime = time.Now()
	s.lastResults = results

	log.Printf("[DATASOURCE] Connection test completed: %v", results)
	return results
}

// TestConnection tests a single data source connection.
func (s *Service) TestConnection(id string) TestResult {
	s.mu.Lock()
	defer s.mu.Unlock()

	start := time.Now()
	var result TestResult

	switch id {
	case "kingdee":
		client := kind.NewKingdeeClient()
		ok := client.TestConnection()
		duration := time.Since(start).Milliseconds()

		result = TestResult{
			DataSource: "kingdee",
			CheckItem:  "API 连接测试",
			Status:     map[bool]string{true: "ok", false: "error"}[ok],
			DurationMs: float64(duration),
			Message:    map[bool]string{true: "连接正常", false: "连接失败"}[ok],
			TestTime:   time.Now().Format("2006-01-02 15:04:05"),
		}

	case "database":
		var status string
		var msg string
		if db.DB == nil {
			status = "error"
			msg = "数据库未初始化"
		} else {
			err := db.DB.Ping()
			if err != nil {
				status = "error"
				msg = fmt.Sprintf("连接失败: %v", err)
			} else {
				status = "ok"
				msg = "连接正常"
			}
		}
		duration := time.Since(start).Milliseconds()

		result = TestResult{
			DataSource: "database",
			CheckItem:  "数据库连接测试",
			Status:     status,
			DurationMs: float64(duration),
			Message:    msg,
			TestTime:   time.Now().Format("2006-01-02 15:04:05"),
		}

	default:
		result = TestResult{
			DataSource: id,
			CheckItem:  "连接测试",
			Status:     "error",
			DurationMs: 0,
			Message:    fmt.Sprintf("未知数据源: %s", id),
			TestTime:   time.Now().Format("2006-01-02 15:04:05"),
		}
	}

	s.lastTestTime = time.Now()
	s.lastResults = []TestResult{result}

	return result
}

// GetLastTestResults returns the last test results.
func (s *Service) GetLastTestResults() []TestResult {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.lastResults
}

// extractOrigin extracts the origin (scheme://host) from a URL.
func extractOrigin(rawURL string) string {
	if rawURL == "" {
		return "--"
	}
	u, err := url.Parse(rawURL)
	if err != nil {
		return rawURL
	}
	return u.Scheme + "://" + u.Host
}

// formatLastTest formats the last test time for display.
func formatLastTest(t time.Time) string {
	if t.IsZero() {
		return "--"
	}
	return t.Format("2006-01-02 15:04:05")
}
