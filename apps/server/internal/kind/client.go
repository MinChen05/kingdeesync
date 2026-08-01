package kind

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/http/cookiejar"
	"strings"
	"sync"
	"time"

	"github.com/kingdee-sync/go/internal/circuit"
	"github.com/kingdee-sync/go/internal/config"
	"github.com/kingdee-sync/go/internal/ratelimit"
	"github.com/kingdee-sync/go/internal/retry"
)

type KingdeeClient struct {
	httpClient *http.Client
	mu         sync.Mutex
	loginGate  chan struct{}
	sessionID  string
	loggedIn   bool
	// Session keepalive
	keepAliveTicker *time.Ticker
	keepAliveDone   chan struct{}
}

type LoginData struct {
	AcctID   string `json:"acctID"`
	Username string `json:"username"`
	Password string `json:"password"`
	Lcid     string `json:"lcid"`
}

type LoginResult struct {
	LoginResultType int                    `json:"LoginResultType"`
	SessionId       string                 `json:"SessionId"`
	Context         map[string]interface{} `json:"Context"`
}

type QueryParams struct {
	FormID      string
	FieldKeys   string
	Filter      string
	StartRow    int
	Limit       int
	OrderField  string
	OrderRule   string
	OrderString string
	// Used for mapping array responses to objects
	FieldKeyList []string
	// SinglePage returns at most one configured page. Cutover uses this to
	// stream very large full snapshots without retaining all business rows.
	SinglePage bool
	// Optional callback for progress reporting during pagination.
	ProgressCallback func(fetchedSoFar int, currentPage int)
}

// AccountBalanceParams holds parameters for querying the GL_RPT_AccountBalance report.
// Mirrors the Python-side Model configuration in form-queries.json.
type AccountBalanceParams struct {
	AcctBookID    string // e.g., "002"
	Currency      string // "1" = local currency
	StartYear     int
	StartPeriod   int
	EndYear       int
	EndPeriod     int
	BalanceLevel  int // 4 = detail level
	ShowDetail    bool
	ShowForbidden bool
	ShowZero      bool
	// OnMonthFetched is called after each month is fetched (optional).
	// Args: year, period, rowsInMonth, totalRowsSoFar.
	// （原因：让调用方能向用户展示按月同步进度，避免长时间无日志输出）
	OnMonthFetched func(year, period, rowsInMonth, totalRows int)
}

type QueryResult struct {
	Rows       []map[string]interface{}
	TotalCount int
	Error      string
}

func NewKingdeeClient() *KingdeeClient {
	cfg := config.Get()
	if cfg == nil {
		log.Println("[KIND] Warning: config not loaded, using defaults")
	}

	// 初始化全局限流器（基于配置的 rate_limit_qps）
	qps := 10.0 // 默认值
	if cfg != nil && cfg.Kingdee.RateLimitQPS > 0 {
		qps = cfg.Kingdee.RateLimitQPS
	}
	ratelimit.InitGlobalLimiter(qps)

	// 初始化全局熔断器
	circuit.InitGlobalBreaker(circuit.DefaultConfig())

	jar, _ := cookiejar.New(nil)
	return &KingdeeClient{
		httpClient: &http.Client{
			Timeout: 120 * time.Second,
			Transport: &http.Transport{
				TLSHandshakeTimeout: 10 * time.Second,
			},
			Jar: jar,
		},
		loginGate: make(chan struct{}, 1),
	}
}

func (c *KingdeeClient) Login() error {
	return c.LoginContext(context.Background())
}

// LoginContext logs in while honoring cancellation during the HTTP request and retries.
func (c *KingdeeClient) LoginContext(ctx context.Context) error {
	if ctx == nil {
		ctx = context.Background()
	}
	if err := ctx.Err(); err != nil {
		return err
	}
	if err := c.acquireLogin(ctx); err != nil {
		return err
	}
	defer c.releaseLogin()

	c.mu.Lock()
	if c.loggedIn && c.sessionID != "" {
		c.mu.Unlock()
		return nil
	}
	c.mu.Unlock()

	cfg := config.Get()
	if cfg == nil {
		return fmt.Errorf("config not loaded")
	}

	loginData := LoginData{
		AcctID:   cfg.Kingdee.AcctID,
		Username: cfg.Kingdee.Username,
		Password: cfg.Kingdee.Password,
		Lcid:     cfg.Kingdee.Lcid,
	}

	resp, err := c.doPostWithRetryContext(ctx, cfg.Kingdee.LoginURL, loginData)
	if err != nil {
		return fmt.Errorf("login request failed: %w", err)
	}
	defer resp.Body.Close()

	var lr LoginResult
	if err := json.NewDecoder(resp.Body).Decode(&lr); err != nil {
		return fmt.Errorf("decode login response: %w", err)
	}

	if lr.LoginResultType != 1 {
		return fmt.Errorf("login failed, resultType=%d", lr.LoginResultType)
	}

	// SessionId may be in Context.SessionId (Kingdee cloud returns it nested)
	c.mu.Lock()
	c.sessionID = lr.SessionId
	if c.sessionID == "" {
		if ctx, ok := lr.Context["SessionId"]; ok {
			c.sessionID = fmt.Sprintf("%v", ctx)
		}
	}
	c.loggedIn = true
	c.mu.Unlock()
	log.Printf("Kingdee login success")
	return nil
}

func (c *KingdeeClient) ensureLoggedIn() error {
	return c.ensureLoggedInContext(context.Background())
}

func (c *KingdeeClient) ensureLoggedInContext(ctx context.Context) error {
	if ctx == nil {
		ctx = context.Background()
	}
	return c.LoginContext(ctx)
}

func (c *KingdeeClient) acquireLogin(ctx context.Context) error {
	c.mu.Lock()
	gate := c.loginGate
	if gate == nil {
		gate = make(chan struct{}, 1)
		c.loginGate = gate
	}
	c.mu.Unlock()
	select {
	case gate <- struct{}{}:
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}

func (c *KingdeeClient) releaseLogin() {
	c.mu.Lock()
	gate := c.loginGate
	c.mu.Unlock()
	if gate != nil {
		<-gate
	}
}

// doPostWithRetry 执行 HTTP POST，集成限流、熔断和重试。
func (c *KingdeeClient) doPostWithRetry(url string, payload interface{}) (*http.Response, error) {
	return c.doPostWithRetryContext(context.Background(), url, payload)
}

func (c *KingdeeClient) doPostWithRetryContext(ctx context.Context, url string, payload interface{}) (*http.Response, error) {
	if ctx == nil {
		ctx = context.Background()
	}
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	body, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("marshal payload: %w", err)
	}

	// 熔断 + 重试：每次实际 HTTP 尝试都重新经过限流器。
	var resp *http.Response
	err = circuit.GlobalExecute(func() error {
		// 重试配置
		retryCfg := retry.Config{
			MaxAttempts:     4,
			InitialInterval: 1 * time.Second,
			MaxInterval:     10 * time.Second,
			BackoffFactor:   2.0,
			Jitter:          true,
		}

		// 自定义可重试判断：HTTP 5xx/429 + 网络错误
		shouldRetry := func(err error) bool {
			// 先检查是否是 HTTP 可重试状态码
			if resp != nil {
				if retry.IsHTTPRetryableStatusCode(resp.StatusCode) {
					resp.Body.Close()
					resp = nil
					return true
				}
			}
			// 网络级错误交给默认判断
			return retry.DefaultShouldRetry(err)
		}

		return retry.RetryContext(ctx, func() error {
			if err := ratelimit.GlobalWaitContext(ctx); err != nil {
				return fmt.Errorf("rate limit wait failed: %w", err)
			}
			req, reqErr := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(body))
			if reqErr != nil {
				return reqErr
			}
			req.Header.Set("Content-Type", "application/json")
			req.Header.Set("Accept", "application/json")

			var doErr error
			resp, doErr = c.httpClient.Do(req)
			if doErr == nil && retry.IsHTTPRetryableStatusCode(resp.StatusCode) {
				statusCode := resp.StatusCode
				resp.Body.Close()
				resp = nil
				return fmt.Errorf("HTTP %d", statusCode)
			}
			return doErr
		}, retryCfg, shouldRetry)
	})

	if err != nil {
		return nil, err
	}

	// 检查 HTTP 状态码（非重试级错误）
	if resp.StatusCode != http.StatusOK {
		resp.Body.Close()
		return nil, fmt.Errorf("HTTP %d", resp.StatusCode)
	}

	return resp, nil
}

// extractRows parses Kingdee response and returns rows
func extractRows(raw interface{}, fieldKeys []string) ([]map[string]interface{}, error) {
	// Handle empty array (no data returned)
	if arr, ok := raw.([]interface{}); ok && len(arr) == 0 {
		return []map[string]interface{}{}, nil
	}

	// Handle direct array-of-arrays response first (e.g., SUB_SUBREQORDER returns [[val1,val2,...],...])
	// before unwrapping single-element outer arrays.
	// （原因：某些表单如委外订单直接返回数组格式，需优先处理）
	if arr, ok := raw.([]interface{}); ok && len(arr) > 0 {
		if _, isArray := arr[0].([]interface{}); isArray {
			return mapRows(arr, fieldKeys), nil
		}
	}

	// Unwrap single-element outer array: [[...]] -> [...]
	if arr, ok := raw.([]interface{}); ok && len(arr) == 1 {
		raw = arr[0]
	}

	// Handle object response: {"Result": {"Rows": [...]}}
	if obj, ok := raw.(map[string]interface{}); ok {
		if resMap, ok := obj["Result"].(map[string]interface{}); ok {
			// Check for errors
			if rs, ok := resMap["ResponseStatus"].(map[string]interface{}); ok {
				if errors, ok := rs["Errors"].([]interface{}); ok && len(errors) > 0 {
					errMsgs := []string{}
					for _, e := range errors {
						if m, ok := e.(map[string]interface{}); ok {
							if msg, ok := m["Message"].(string); ok {
								errMsgs = append(errMsgs, msg)
							}
						}
					}
					if len(errMsgs) > 0 {
						joined := strings.Join(errMsgs, " ")
						if strings.Contains(joined, "会话") || strings.Contains(joined, "登录") {
							return nil, fmt.Errorf("SESSION_ERROR: %s", joined)
						}
						return nil, fmt.Errorf("API error: %s", joined)
					}
				}
			}
			if r, ok := resMap["Rows"].([]interface{}); ok {
				return mapRows(r, fieldKeys), nil
			}
			return []map[string]interface{}{}, nil
		}
	}

	// Handle array response: [{"Result": {"Rows": [...]}}]
	if arr, ok := raw.([]interface{}); ok && len(arr) > 0 {
		if obj, ok := arr[0].(map[string]interface{}); ok {
			if resMap, ok := obj["Result"].(map[string]interface{}); ok {
				if r, ok := resMap["Rows"].([]interface{}); ok {
					return mapRows(r, fieldKeys), nil
				}
				// Rows might be a single object if only 1 row
				if r, ok := resMap["Rows"].(map[string]interface{}); ok {
					return mapRows([]interface{}{r}, fieldKeys), nil
				}
			}
		}
	}

	// Handle direct array of rows: [[val1,val2,...],...] or [{key:value,...},...]
	if arr, ok := raw.([]interface{}); ok && len(arr) > 0 {
		// Check if first element is a map (already key-value) or array (needs fieldKeys mapping)
		if _, isMap := arr[0].(map[string]interface{}); isMap {
			return mapRows(arr, fieldKeys), nil
		}
		// Array of arrays - map using fieldKeys
		if _, isArray := arr[0].([]interface{}); isArray {
			return mapRows(arr, fieldKeys), nil
		}
	}

	return nil, fmt.Errorf("unrecognized response structure")
}

// mapRows converts Kingdee rows to map objects
// Rows can be: [{key:value,...},...] or [[val1,val2,...],...]
func mapRows(rows []interface{}, fieldKeys []string) []map[string]interface{} {
	if len(rows) == 0 {
		return []map[string]interface{}{}
	}

	result := make([]map[string]interface{}, 0, len(rows))
	// Check if first row is already a map
	if _, isMap := rows[0].(map[string]interface{}); isMap {
		for _, row := range rows {
			if m, ok := row.(map[string]interface{}); ok {
				result = append(result, m)
			}
		}

		return result
	}

	// Array format: map by position using fieldKeys
	if len(fieldKeys) == 0 {
		return result
	}

	for _, row := range rows {
		if arr, ok := row.([]interface{}); ok {
			m := make(map[string]interface{})
			for i, val := range arr {
				if i < len(fieldKeys) {
					m[fieldKeys[i]] = val
				}
			}
			result = append(result, m)
		}
	}
	return result
}

// TestConnection tests if the Kingdee API is reachable by attempting a login.
func (c *KingdeeClient) TestConnection() bool {
	start := time.Now()
	err := c.Login()
	log.Printf("[KIND] Connection test completed in %v: %v", time.Since(start), err)
	return err == nil
}

func (c *KingdeeClient) QueryData(queryParams QueryParams) (*QueryResult, error) {
	return c.QueryDataContext(context.Background(), queryParams)
}

// QueryDataContext queries paginated data while honoring cancellation.
func (c *KingdeeClient) QueryDataContext(ctx context.Context, queryParams QueryParams) (*QueryResult, error) {
	if ctx == nil {
		ctx = context.Background()
	}
	if err := c.ensureLoggedInContext(ctx); err != nil {
		return nil, err
	}

	cfg := config.Get()
	if cfg == nil {
		return nil, fmt.Errorf("config not loaded")
	}

	result := &QueryResult{Rows: []map[string]interface{}{}}
	pageSize := cfg.Kingdee.PageSize
	if queryParams.Limit > 0 {
		pageSize = queryParams.Limit
	}
	if pageSize <= 0 {
		pageSize = 9000
	}
	maxPages := cfg.Kingdee.MaxPages
	if maxPages <= 0 {
		maxPages = 100000
	}

	currentRow := queryParams.StartRow
	pageIndex := 0

	for {
		pageIndex++
		if pageIndex > maxPages {
			log.Printf("Page limit reached (%d) for form %s", maxPages, queryParams.FormID)
			break
		}

		requestData := map[string]interface{}{
			"FormId":   queryParams.FormID,
			"StartRow": currentRow,
			"Limit":    pageSize,
		}

		if queryParams.FieldKeys != "" {
			requestData["FieldKeys"] = queryParams.FieldKeys
		}
		if queryParams.Filter != "" {
			requestData["FilterString"] = queryParams.Filter
		}
		if queryParams.OrderString != "" {
			requestData["OrderString"] = queryParams.OrderString
		} else if queryParams.OrderField != "" {
			requestData["OrderField"] = queryParams.OrderField
			requestData["OrderRule"] = queryParams.OrderRule
		}

		payload := map[string]interface{}{"data": requestData}

		resp, err := c.doPostWithRetryContext(ctx, cfg.Kingdee.QueryURL, payload)
		if err != nil {
			return nil, fmt.Errorf("query request failed: %w", err)
		}

		var raw interface{}
		if err := json.NewDecoder(resp.Body).Decode(&raw); err != nil {
			resp.Body.Close()
			return nil, fmt.Errorf("decode query response: %w", err)
		}
		resp.Body.Close()

		pageRows, err := extractRows(raw, queryParams.FieldKeyList)
		if err != nil {
			if strings.Contains(err.Error(), "SESSION_ERROR") {
				log.Printf("Session error for %s, re-login and retry...", queryParams.FormID)
				c.mu.Lock()
				c.loggedIn = false
				c.mu.Unlock()
				if loginErr := c.LoginContext(ctx); loginErr != nil {
					return nil, fmt.Errorf("session error and re-login failed: %w", loginErr)
				}
				pageIndex--
				continue
			}
			return nil, err
		}

		if len(pageRows) == 0 {
			break
		}

		result.Rows = append(result.Rows, pageRows...)
		log.Printf("Fetched %d rows for %s (page %d, total %d)", len(pageRows), queryParams.FormID, pageIndex, len(result.Rows))
		if queryParams.ProgressCallback != nil {
			log.Printf("[PROGRESS-CALLBACK] %s: calling ProgressCallback(total=%d, page=%d)", queryParams.FormID, len(result.Rows), pageIndex)
			queryParams.ProgressCallback(len(result.Rows), pageIndex)
		} else {
			log.Printf("[PROGRESS-CALLBACK] %s: ProgressCallback is nil", queryParams.FormID)
		}

		currentRow += len(pageRows)
		if queryParams.SinglePage {
			break
		}

		// Stop only when we got fewer rows than requested.
		if len(pageRows) < pageSize {
			break
		}
	}

	result.TotalCount = len(result.Rows)
	return result, nil
}

// parseAmount removes thousands separators and converts to float64.
// Mirrors Python _parse_amount() behavior.
func parseAmount(value interface{}) float64 {
	if value == nil {
		return 0
	}
	switch v := value.(type) {
	case float64:
		return v
	case string:
		v = strings.ReplaceAll(v, ",", "")
		v = strings.TrimSpace(v)
		if v == "" {
			return 0
		}
		var f float64
		_, err := fmt.Sscanf(v, "%f", &f)
		if err != nil {
			return 0
		}
		return f
	default:
		return 0
	}
}

func fillAccountBalanceLocalAmounts(row map[string]interface{}) {
	for local, base := range map[string]string{
		"FBEGINDEBITLOCAL":  "FBEGINDEBIT",
		"FBEGINCREDITLOCAL": "FBEGINCREDIT",
		"FDEBITLOCAL":       "FDEBIT",
		"FCREDITLOCAL":      "FCREDIT",
		"FYTDDEBITLOCAL":    "FYTDDEBIT",
		"FYTDCREDITLOCAL":   "FYTDCREDIT",
		"FENDDEBITLOCAL":    "FENDDEBIT",
		"FENDCREDITLOCAL":   "FENDCREDIT",
	} {
		if value, exists := row[local]; !exists || value == nil || strings.TrimSpace(fmt.Sprint(value)) == "" {
			row[local] = row[base]
		}
	}
}

// QueryAccountBalance calls the GetSysReportData API for a specific year/month,
// then returns rows with FACCTYEAR and FACCTPERIOD injected.
// This follows the account-balance monthly synchronization contract.
// （原因：科目余额表走 GetSysReportData 而非 ExecuteBillQuery，需按月逐月拉取）
func (c *KingdeeClient) QueryAccountBalance(params AccountBalanceParams) (*QueryResult, error) {
	return c.QueryAccountBalanceContext(context.Background(), params)
}

// QueryAccountBalanceContext queries the monthly report while honoring cancellation.
func (c *KingdeeClient) QueryAccountBalanceContext(ctx context.Context, params AccountBalanceParams) (*QueryResult, error) {
	if ctx == nil {
		ctx = context.Background()
	}
	if err := c.ensureLoggedInContext(ctx); err != nil {
		return nil, err
	}

	cfg := config.Get()
	if cfg == nil {
		return nil, fmt.Errorf("config not loaded")
	}

	result := &QueryResult{Rows: []map[string]interface{}{}}

	// Iterate through each month from start to end
	for year := params.StartYear; year <= params.EndYear; year++ {
		startMonth := 1
		endMonth := 12
		if year == params.StartYear {
			startMonth = params.StartPeriod
		}
		if year == params.EndYear {
			endMonth = params.EndPeriod
		}

		for period := startMonth; period <= endMonth; period++ {
			if err := ctx.Err(); err != nil {
				return result, err
			}
			// Build the Model payload for GetSysReportData
			model := map[string]interface{}{
				"FACCTBOOKID":      map[string]interface{}{"FNumber": params.AcctBookID},
				"FCURRENCY":        params.Currency,
				"FSTARTYEAR":       year,
				"FSTARTPERIOD":     period,
				"FENDYEAR":         year,
				"FENDPERIOD":       period,
				"FBALANCELEVEL":    params.BalanceLevel,
				"FSHOWDETAIL":      params.ShowDetail,
				"FFORBIDBALANCE":   params.ShowForbidden,
				"FNOTPOSTVOUCHER":  true,
				"FBALANCEZERO":     params.ShowZero,
				"FPERIODNOBALANCE": true,
				"FYEARNOBALANCE":   true,
				"FSHOWFULLNAME":    false,
				"FDETAILSHOWACCT":  true,
				"FSHOWDETAILONLY":  false,
			}

			// FieldKeys required by GetSysReportData API
			balanceFieldKeys := strings.Join([]string{
				"FBALANCEID", "FBALANCENAME", "FDETAILNUMBER", "FDETAILNAME",
				"FBEGINYEARDEBITLOCAL", "FBEGINYEARCREDITLOCAL",
				"FBEGINDEBIT", "FBEGINDEBITLOCAL", "FBEGINCREDIT", "FBEGINCREDITLOCAL",
				"FDEBIT", "FDEBITLOCAL", "FCREDIT", "FCREDITLOCAL",
				"FYTDDEBIT", "FYTDDEBITLOCAL", "FYTDCREDIT", "FYTDCREDITLOCAL",
				"FENDDEBIT", "FENDDEBITLOCAL", "FENDCREDIT", "FENDCREDITLOCAL",
				"FPROFITLOCAL", "FYTDPROFITLOCAL",
			}, ",")

			requestData := map[string]interface{}{
				"FormId":    "GL_RPT_AccountBalance",
				"FieldKeys": balanceFieldKeys,
				"Model":     model,
			}
			// GetSysReportData requires "data" to be a JSON string, not an object.
			// Also pass formId at the top level.
			// （原因：与 Python _build_report_payload 对齐，data 必须是 JSON 字符串，且需携带 FieldKeys）
			dataJSON, err := json.Marshal(requestData)
			if err != nil {
				log.Printf("[GL] Failed to marshal request for %d-%02d: %v", year, period, err)
				return result, fmt.Errorf("marshal account balance request for %d-%02d: %w", year, period, err)
			}
			payload := map[string]interface{}{
				"formId": "GL_RPT_AccountBalance",
				"data":   string(dataJSON),
			}

			// Use the report URL (typically same as QueryURL but different endpoint)
			reportURL := cfg.Kingdee.QueryURL
			// Replace ExecuteBillQuery with GetSysReportData if needed
			if strings.Contains(reportURL, "ExecuteBillQuery") {
				reportURL = strings.Replace(reportURL, "ExecuteBillQuery", "GetSysReportData", 1)
			}

			resp, err := c.doPostWithRetryContext(ctx, reportURL, payload)
			if err != nil {
				if ctx.Err() != nil {
					return result, ctx.Err()
				}
				// SESSION_ERROR in HTTP response body
				if strings.Contains(err.Error(), "SESSION_ERROR") {
					log.Printf("[GL] Session error for %d-%02d, re-login and retry...", year, period)
					c.mu.Lock()
					c.loggedIn = false
					c.mu.Unlock()
					if loginErr := c.LoginContext(ctx); loginErr != nil {
						return result, fmt.Errorf("session error and re-login failed: %w", loginErr)
					}
					period--
					continue
				}
				log.Printf("[GL] Failed to query %d-%02d: %v", year, period, err)
				return result, fmt.Errorf("query account balance for %d-%02d: %w", year, period, err)
			}

			// Read and buffer response body so we can log it for debugging
			respBytes, readErr := io.ReadAll(resp.Body)
			resp.Body.Close()
			if readErr != nil {
				log.Printf("[GL] Failed to read response for %d-%02d: %v", year, period, readErr)
				return result, fmt.Errorf("read account balance response for %d-%02d: %w", year, period, readErr)
			}

			var raw interface{}
			if err := json.Unmarshal(respBytes, &raw); err != nil {
				log.Printf("[GL] Failed to decode response for %d-%02d: %v", year, period, err)
				return result, fmt.Errorf("decode account balance response for %d-%02d: %w", year, period, err)
			}

			// Parse response - report data usually comes as array of arrays
			fieldKeys := []string{
				"FBALANCEID", "FBALANCENAME", "FDETAILNUMBER", "FDETAILNAME",
				"FBEGINYEARDEBITLOCAL", "FBEGINYEARCREDITLOCAL",
				"FBEGINDEBIT", "FBEGINDEBITLOCAL", "FBEGINCREDIT", "FBEGINCREDITLOCAL",
				"FDEBIT", "FDEBITLOCAL", "FCREDIT", "FCREDITLOCAL",
				"FYTDDEBIT", "FYTDDEBITLOCAL", "FYTDCREDIT", "FYTDCREDITLOCAL",
				"FENDDEBIT", "FENDDEBITLOCAL", "FENDCREDIT", "FENDCREDITLOCAL",
				"FPROFITLOCAL", "FYTDPROFITLOCAL",
			}

			pageRows, err := extractRows(raw, fieldKeys)
			if err != nil {
				// SESSION_ERROR recovery: re-login and retry this month
				if strings.Contains(err.Error(), "SESSION_ERROR") {
					log.Printf("[GL] Session error for %d-%02d, re-login and retry...", year, period)
					c.mu.Lock()
					c.loggedIn = false
					c.mu.Unlock()
					if loginErr := c.LoginContext(ctx); loginErr != nil {
						return result, fmt.Errorf("session error and re-login failed: %w", loginErr)
					}
					// Remove the period increment so the for-loop retries this month
					period--
					continue
				}
				log.Printf("[GL] Failed to extract rows for %d-%02d: %v", year, period, err)
				return result, fmt.Errorf("parse account balance response for %d-%02d: %w", year, period, err)
			}

			// Inject FACCTYEAR and FACCTPERIOD, clean amount fields
			for _, row := range pageRows {
				row["FACCTYEAR"] = year
				row["FACCTPERIOD"] = period
				fillAccountBalanceLocalAmounts(row)
				// Clean amount fields that might have commas
				for _, key := range []string{
					"FBEGINYEARDEBITLOCAL", "FBEGINYEARCREDITLOCAL",
					"FBEGINDEBIT", "FBEGINDEBITLOCAL", "FBEGINCREDIT", "FBEGINCREDITLOCAL",
					"FDEBIT", "FDEBITLOCAL", "FCREDIT", "FCREDITLOCAL",
					"FYTDDEBIT", "FYTDDEBITLOCAL", "FYTDCREDIT", "FYTDCREDITLOCAL",
					"FENDDEBIT", "FENDDEBITLOCAL", "FENDCREDIT", "FENDCREDITLOCAL",
					"FPROFITLOCAL", "FYTDPROFITLOCAL",
				} {
					if val, ok := row[key]; ok {
						row[key] = parseAmount(val)
					}
				}
			}

			result.Rows = append(result.Rows, pageRows...)
			log.Printf("[GL] Fetched %d rows for %d-%02d (total: %d)", len(pageRows), year, period, len(result.Rows))
			if params.OnMonthFetched != nil {
				params.OnMonthFetched(year, period, len(pageRows), len(result.Rows))
			}
		}
	}

	result.TotalCount = len(result.Rows)
	log.Printf("[GL] Account balance sync complete: %d total rows", len(result.Rows))
	return result, nil
}

// StartSessionKeepAlive starts a background goroutine that periodically re-logs
// in to keep the Kingdee session alive. The interval is read from config
// (KeepSessionAlive / KeepAliveInterval).
//
// Call StopSessionKeepAlive when the client is no longer needed.
func (c *KingdeeClient) StartSessionKeepAlive() {
	cfg := config.Get()
	if cfg == nil || !cfg.Kingdee.KeepSessionAlive {
		return
	}
	interval := time.Duration(cfg.Kingdee.KeepAliveInterval) * time.Second
	if interval < 30*time.Second {
		interval = 5 * time.Minute // sensible default
	}

	c.keepAliveDone = make(chan struct{})
	c.keepAliveTicker = time.NewTicker(interval)
	log.Printf("[KIND] Session keepalive started (interval=%v)", interval)

	go func() {
		for {
			select {
			case <-c.keepAliveDone:
				c.keepAliveTicker.Stop()
				log.Printf("[KIND] Session keepalive stopped")
				return
			case <-c.keepAliveTicker.C:
				c.mu.Lock()
				if c.loggedIn && c.sessionID != "" {
					c.loggedIn = false // force re-login
				}
				c.mu.Unlock()
				ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
				if err := c.LoginContext(ctx); err != nil {
					log.Printf("[KIND] Keepalive re-login failed: %v", err)
				} else {
					log.Printf("[KIND] Keepalive re-login success")
				}
				cancel()
			}
		}
	}()
}

// StopSessionKeepAlive stops the session keepalive goroutine.
func (c *KingdeeClient) StopSessionKeepAlive() {
	if c.keepAliveDone != nil {
		close(c.keepAliveDone)
	}
}
