package syncengine

import (
	"bytes"
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	urlpkg "net/url"
	"os"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/jmoiron/sqlx"
	"github.com/kingdee-sync/go/internal/config"
)

// DorisWriter writes data to Doris using Stream Load (HTTP PUT).
// Doris 3.0 UNIQUE KEY tables use merge-on-write, so Stream Load
// with the right label provides idempotent upsert semantics.
// （原因：Doris 不支持 SQL Server 的 MERGE/staging，Stream Load 是官方推荐的高性能写入方式）
type DorisWriter struct {
	httpClient *http.Client
}

// NewDorisWriter creates a DorisWriter configured from the current app config.
func NewDorisWriter() *DorisWriter {
	cfg := config.Get()
	if cfg == nil {
		log.Println("[DORIS-WRITER] Warning: config not loaded, using defaults")
	}

	// TLS: default to verifying certificates. Only skip verification when
	// DORIS_SKIP_TLS_VERIFY=1 is explicitly set (e.g., internal test envs).
	skipTLS := false
	if cfg != nil {
		if env := os.Getenv("DORIS_SKIP_TLS_VERIFY"); strings.ToLower(env) == "1" || strings.ToLower(env) == "true" {
			skipTLS = true
		}
	}

	tlsConfig := &tls.Config{
		MinVersion:         tls.VersionTLS12,
		InsecureSkipVerify: skipTLS, //nolint:gosec // explicitly gated by env var
	}
	if skipTLS {
		log.Println("[DORIS-WRITER] Warning: TLS verification disabled by DORIS_SKIP_TLS_VERIFY")
	}

	return &DorisWriter{
		httpClient: &http.Client{
			Timeout:   5 * time.Minute,
			Transport: &http.Transport{TLSClientConfig: tlsConfig, MaxIdleConns: 10},
		},
	}
}

// dorisTarget returns the Doris HTTP endpoint and credentials.
// Doris Stream Load uses HTTP API on port 8030 (FE HTTP port),
// while MySQL protocol uses port 9030. We derive the HTTP port from the config.
// （原因：Stream Load 是 HTTP API，端口与 MySQL 协议端口不同）
func (w *DorisWriter) dorisTarget() (host string, user string, password string, err error) {
	cfg := config.Get()
	if cfg == nil {
		return "", "", "", fmt.Errorf("config not loaded")
	}
	dbCfg := cfg.GetEffectiveDatabase()
	if dbCfg.Type != "mysql" {
		return "", "", "", fmt.Errorf("DorisWriter requires database type=mysql, got %s", dbCfg.Type)
	}
	// Return host without port; callers add the port they need:
	// - Stream Load uses HTTP port 8030
	// - MySQL protocol (DeleteOrphaned) uses port 9030
	return dbCfg.Host, dbCfg.User, dbCfg.Password, nil
}

// Upsert uses Doris Stream Load to upsert rows into the target table.
//
// Write strategy:
//   - Format: JSON Lines (one JSON object per line)
//   - JSON keys are uppercased to match Doris column names.
//   - _sync_time is injected by the writer as current local time.
//   - Label is unique per call; on retry the same label is NOT reused
//     (Doris guarantees idempotency per label, but we rely on UNIQUE KEY
//     merge semantics instead).
func (w *DorisWriter) Upsert(ctx context.Context, tableName string, rows []map[string]interface{},
	cols []string, pkCols []string, fieldMap map[string]string) (int, error) {

	if len(rows) == 0 {
		return 0, nil
	}
	if ctx == nil {
		ctx = context.Background()
	}

	host, user, password := w.getEffectiveTarget()
	if host == "" {
		return 0, fmt.Errorf("Doris target not configured")
	}

	// Use https:// when DORIS_USE_HTTPS=1; default to http:// for compatibility.
	scheme := "http"
	if env := os.Getenv("DORIS_USE_HTTPS"); strings.ToLower(env) == "1" || strings.ToLower(env) == "true" {
		scheme = "https"
	}
	// Stream Load uses HTTP port 8030
	url := fmt.Sprintf("%s://%s:8030/api/kingdee_sync/%s/_stream_load", scheme, host, tableName)

	// Batch rows to avoid exceeding Doris streaming_load_json_max_mb.
	// （原因：大批量数据如 65 万行会生成超过 100MB 的 JSON body，需分批写入）
	const batchSize = 80000
	totalWritten := 0

	for start := 0; start < len(rows); start += batchSize {
		end := start + batchSize
		if end > len(rows) {
			end = len(rows)
		}
		batch := rows[start:end]

		payload, err := w.buildJSONPayload(tableName, batch, cols, fieldMap)
		if err != nil {
			return totalWritten, fmt.Errorf("build JSON payload for %s batch [%d:%d]: %w", tableName, start, end, err)
		}

		log.Printf("[DORIS-STREAM] %s: batch %d/%d, sending %d rows (%d bytes)",
			tableName, (start/batchSize)+1, (len(rows)+batchSize-1)/batchSize, len(batch), len(payload))

		label := "kingdee_sync_" + tableName + "_" + uuid.New().String()

		// Retry up to 3 times with exponential backoff.
		var lastErr error
		for attempt := 0; attempt < 3; attempt++ {
			if attempt > 0 {
				backoff := time.Duration(1<<uint(attempt-1)) * time.Second
				log.Printf("[DORIS-STREAM] Retry %d/%d for %s batch %d after %v: %v",
					attempt+1, 3, tableName, start/batchSize, backoff, lastErr)
				timer := time.NewTimer(backoff)
				select {
				case <-timer.C:
				case <-ctx.Done():
					if !timer.Stop() {
						select {
						case <-timer.C:
						default:
						}
					}
					return totalWritten, ctx.Err()
				}
			}

			written, err := w.doStreamLoad(ctx, url, user, password, label, tableName, payload)
			if err == nil {
				totalWritten += written
				log.Printf("[SYNC-PROGRESS] %s: 写入进度 %d/%d 条 (%.1f%%)",
					tableName, totalWritten, len(rows), float64(totalWritten)*100/float64(len(rows)))
				break
			}
			lastErr = err
			label = "kingdee_sync_" + tableName + "_" + uuid.New().String()
		}

		if lastErr != nil {
			return totalWritten, fmt.Errorf("Stream Load failed for %s batch [%d:%d] after 3 attempts: %w",
				tableName, start, end, lastErr)
		}
	}

	return totalWritten, nil
}

// DeleteOrphaned deletes rows from Doris that are not present in the provided Kingdee data.
//
// Implementation uses Doris 3.0 MOE DELETE with a batched IN clause.
// For composite PKs, uses (pk1, pk2) IN ((v1,v2), ...) syntax.
// Falls back to logging if the table has no PK configured.
func (w *DorisWriter) DeleteOrphaned(ctx context.Context, tableName string, rows []map[string]interface{},
	pkCols []string) (int, error) {

	if len(rows) == 0 || len(pkCols) == 0 {
		return 0, nil
	}

	// Collect distinct PK tuples present in Kingdee source data.
	pkSet := make(map[string][]interface{})
	for _, row := range rows {
		vals := make([]interface{}, len(pkCols))
		keyParts := make([]string, len(pkCols))
		for i, col := range pkCols {
			colUpper := strings.ToUpper(col)
			v := row[col]
			if v == nil {
				v = row[colUpper]
			}
			vals[i] = v
			keyParts[i] = fmt.Sprintf("%v", v)
		}
		key := strings.Join(keyParts, "|")
		pkSet[key] = vals
	}

	if len(pkSet) == 0 {
		return 0, nil
	}

	// Use SQL DELETE with complete NOT IN clause.
	// Do NOT fall back to Stream Load: the 2-way delete approach requires
	// a temporary snapshot table to identify orphans; naively marking source
	// PKs for deletion would remove valid rows instead.
	deleted, err := w.deleteOrphanedBySQL(ctx, tableName, pkCols, pkSet)
	if err != nil {
		return 0, fmt.Errorf("DeleteOrphaned for %s: %w", tableName, err)
	}

	log.Printf("[DORIS-DELETE] Deleted %d orphaned rows from %s (source has %d distinct PKs)", deleted, tableName, len(pkSet))
	return deleted, nil
}

// deleteOrphanedBySQL uses Doris DELETE statement with a single NOT IN clause.
//
// IMPORTANT: NOT IN must include ALL source PKs in one statement. Splitting
// into batches would delete rows that exist in later batches (false positives).
// If the total IN-list exceeds a safe size, we refuse to delete entirely.
func (w *DorisWriter) deleteOrphanedBySQL(ctx context.Context, tableName string, pkCols []string, pkSet map[string][]interface{}) (int, error) {
	host, user, password, err := w.dorisTarget()
	if err != nil {
		return 0, err
	}

	tuples := make([][]interface{}, 0, len(pkSet))
	for _, vals := range pkSet {
		tuples = append(tuples, vals)
	}

	// Safety limit: refuse if PK count is too large.
	// （原因：防止 SQL 过长导致 Doris 解析失败，2000 对即时库存/物料清单等大数据量表不够）
	const maxTuples = 500000
	if len(tuples) > maxTuples {
		return 0, fmt.Errorf("PK count %d exceeds safe limit %d; orphan deletion refused", len(tuples), maxTuples)
	}

	// Build NOT IN list using a NULL-byte separator to avoid
	// composite PK collision: ("A|B","C") vs ("A","B|C") would collide
	// with "|" but never with "\x00" since SQL strings can't contain NUL.
	// （原因：Doris MySQL 协议不支持 prepare statement，必须使用非参数化 SQL）
	inValues := make([]string, 0, len(tuples))
	for _, vals := range tuples {
		var parts []string
		for _, v := range vals {
			switch val := v.(type) {
			case string:
				parts = append(parts, fmt.Sprintf("'%s'", val))
			default:
				parts = append(parts, fmt.Sprintf("%v", val))
			}
		}
		inValues = append(inValues, fmt.Sprintf("'%s'", strings.Join(parts, "\x00")))
	}

	colExprs := make([]string, len(pkCols))
	for i, c := range pkCols {
		colExprs[i] = "IFNULL(CAST(`" + c + "` AS CHAR), '')"
	}
	pkConcat := strings.Join(colExprs, ", ")

	deleteSQL := fmt.Sprintf("DELETE FROM `%s` WHERE CONCAT_WS(CHAR(0), %s) NOT IN (%s)",
		tableName, pkConcat, strings.Join(inValues, ", "))

	// Execute via MySQL protocol on Doris (port 9030, not 8030).
	mysqlURL := fmt.Sprintf("%s:%s@tcp(%s:9030)/kingdee_sync", user, password, host)
	db, sqlErr := sqlx.ConnectContext(ctx, "mysql", mysqlURL)
	if sqlErr != nil {
		return 0, fmt.Errorf("connect to Doris MySQL protocol: %w", sqlErr)
	}
	defer db.Close()

	result, sqlErr := db.ExecContext(ctx, deleteSQL)
	if sqlErr != nil {
		return 0, fmt.Errorf("execute DELETE for %s: %w", tableName, sqlErr)
	}
	n, _ := result.RowsAffected()
	return int(n), nil
}

func (w *DorisWriter) Close() error {
	// Nothing to close; httpClient is reused.
	return nil
}

// buildJSONPayload converts rows to a JSON array format for Doris Stream Load.
// Doris 3.0 MOE requires JSON array with strip_outer_array=true for multi-row loads.
// （原因：Doris 3.0 Stream Load 对 JSON Lines 支持不佳，JSON array + strip_outer_array 更可靠）
func (w *DorisWriter) buildJSONPayload(tableName string, rows []map[string]interface{}, cols []string, rowMap map[string]string) ([]byte, error) {
	// Build reverse map: DB column name -> Kingdee field name(s) to try.
	colToKingdee := make(map[string][]string)
	for kingdeeField, dbCol := range rowMap {
		colToKingdee[strings.ToUpper(dbCol)] = append(colToKingdee[strings.ToUpper(dbCol)], kingdeeField)
	}

	now := time.Now().In(time.Local).Format("2006-01-02 15:04:05")
	objs := make([]map[string]interface{}, 0, len(rows))

	for _, row := range rows {
		obj := make(map[string]interface{})

		for _, col := range cols {
			colUpper := strings.ToUpper(col)

			// Try to find the value using Kingdee field names first.
			v := w.lookupValue(row, col, colToKingdee[colUpper])
			if defaultValue, ok := v.(configuredDefaultValue); ok {
				v = defaultValue.Value
			} else {
				v = normalizeValue(v)
			}
			v = truncateDateTimeFraction(v)
			if shouldTruncateDateOnly(tableName, col) {
				v = truncateDateOnly(v)
			}

			// Use actual DB column name (from existingCols) as JSON key, not uppercase.
			// （原因：Doris 列名是区分大小写的，如 FDescription、F_ora_Text_9sb，不能全转大写）
			obj[col] = v
		}

		// Inject SYNC_TIME to match Doris DDL column name.
		obj["SYNC_TIME"] = now
		objs = append(objs, obj)
	}

	return json.Marshal(objs)
}

func shouldTruncateDateOnly(tableName, columnName string) bool {
	return strings.EqualFold(tableName, "customer") && strings.EqualFold(columnName, "FCREATEDATE")
}

// truncateDateTimeFraction keeps Go Stream Load compatible with the legacy
// Python SQL Server writer, which stores Kingdee datetimes at whole-second
// precision. Doris rounds fractional seconds when coercing JSON strings.
// If the value cannot be parsed as a valid datetime, returns nil so Doris
// treats it as NULL instead of rejecting the entire row.
// （原因：金蝶 API 可能返回 "0000-00-00 00:00:00" 或空字符串，直接传给 Doris 会导致 DATA_QUALITY_ERROR）
func truncateDateTimeFraction(value interface{}) interface{} {
	text, ok := value.(string)
	if !ok || len(text) < len("2006-01-02 15:04:05") {
		return value
	}
	if len(text) > 10 && text[10] == 'T' {
		text = text[:10] + " " + text[11:]
	}
	secondPrecision := text[:len("2006-01-02 15:04:05")]
	if _, err := time.Parse("2006-01-02 15:04:05", secondPrecision); err != nil {
		return nil // invalid datetime → NULL, prevents Doris DATA_QUALITY_ERROR
	}
	return secondPrecision
}

func truncateDateOnly(value interface{}) interface{} {
	text, ok := value.(string)
	if !ok || len(text) < len("2006-01-02") {
		return value
	}
	if _, err := time.Parse("2006-01-02", text[:len("2006-01-02")]); err != nil {
		return value
	}
	return text[:len("2006-01-02")] + " 00:00:00"
}

// lookupValue finds a value in a Kingdee row by trying various key names.
func (w *DorisWriter) lookupValue(row map[string]interface{}, col string, kingdeeFields []string) interface{} {
	// First try the DB column name directly (for fields without mapping).
	if v, ok := row[col]; ok && v != nil {
		return v
	}
	// Try uppercase DB column name.
	if v, ok := row[strings.ToUpper(col)]; ok && v != nil {
		return v
	}
	// Try Kingdee field names from the map.
	for _, kf := range kingdeeFields {
		if v, ok := row[kf]; ok && v != nil {
			return v
		}
	}
	// Kingdee may vary field-name casing between forms and response paths.
	// Match only after exact lookups so explicitly mapped keys retain priority.
	candidates := append([]string{col}, kingdeeFields...)
	for _, candidate := range candidates {
		for key, value := range row {
			if value != nil && strings.EqualFold(key, candidate) {
				return value
			}
		}
	}
	return nil
}

// doStreamLoad performs a single Stream Load request, handling Doris 307 redirects.
// Doris FE redirects Stream Load to BE via 307, and the BE requires Basic Auth.
// Go's default HTTP client does NOT follow 307, so we handle it manually.
// （原因：Doris 3.0 Stream Load 使用 307 重定向到 BE，需要手动处理并重新认证）
func (w *DorisWriter) doStreamLoad(ctx context.Context, url, user, password, label, tableName string, payload []byte) (int, error) {
	return w.doStreamLoadWithRedirect(ctx, url, user, password, label, tableName, payload, "", 0)
}

func (w *DorisWriter) doStreamLoadWithRedirect(ctx context.Context, url, user, password, label, tableName string, payload []byte, mergeType string, redirectCount int) (int, error) {
	if redirectCount > 3 {
		return 0, fmt.Errorf("too many redirects for Stream Load to %s", tableName)
	}

	req, err := http.NewRequestWithContext(ctx, "PUT", url, bytes.NewReader(payload))
	if err != nil {
		return 0, fmt.Errorf("create request: %w", err)
	}

	// Force Expect: 100-continue header.
	// Go's HTTP client only sends this for large bodies by default, but Doris requires it.
	// （原因：Doris Stream Load 强制要求 Expect: 100-continue，Go client 对小 body 不自动发送）
	req.Header.Set("Expect", "100-continue")

	// Only set Basic Auth if the URL doesn't already contain credentials.
	// Doris FE 307 redirect Location URLs may already embed user:password@host.
	// （原因：Doris 3.0 重定向 URL 已嵌入认证信息，重复设置 Basic Auth 导致 BE 拒绝）
	if u, err := urlpkg.Parse(url); err == nil && (u.User == nil || u.User.Username() == "") {
		req.SetBasicAuth(user, password)
	}
	req.Header.Set("label", label)
	req.Header.Set("format", "json")
	req.Header.Set("strip_outer_array", "true") // JSON array format requires this
	req.Header.Set("max_filter_ratio", "1")
	req.Header.Set("strict_mode", "false")
	if mergeType != "" {
		req.Header.Set("merge_type", mergeType)
	}

	resp, err := w.httpClient.Do(req)
	if err != nil {
		return 0, fmt.Errorf("HTTP request: %w", err)
	}
	defer resp.Body.Close()

	// Handle 307 Temporary Redirect from Doris FE to BE.
	if resp.StatusCode == 307 || resp.StatusCode == 302 {
		location := resp.Header.Get("Location")
		if location == "" {
			return 0, fmt.Errorf("redirect without Location header for %s", tableName)
		}
		log.Printf("[DORIS-STREAM] Following redirect for %s: %s -> %s", tableName, url, location)
		return w.doStreamLoadWithRedirect(ctx, location, user, password, label, tableName, payload, mergeType, redirectCount+1)
	}

	body, _ := io.ReadAll(resp.Body)

	// Doris Stream Load response JSON.
	// Doris 3.0 MOE may use either lowercase or PascalCase keys.
	var result struct {
		// Lowercase (Doris 3.0 MOE)
		Status               string `json:"status"`
		NumberOfTotalRows    int    `json:"number_total_rows"`
		NumberOfLoadedRows   int    `json:"number_loaded_rows"`
		NumberOfFilteredRows int    `json:"number_filtered_rows"`
		Message              string `json:"msg"`
		// PascalCase (older Doris)
		PStatus               string `json:"Status"`
		PNumberOfTotalRows    int    `json:"NumberTotalRows"`
		PNumberOfLoadedRows   int    `json:"NumberLoadedRows"`
		PNumberOfFilteredRows int    `json:"NumberFilteredRows"`
		PMessage              string `json:"Message"`
		ErrorURL              string `json:"error_url"`
		PErrorURL             string `json:"ErrorURL"`
	}

	if err := json.Unmarshal(body, &result); err != nil {
		log.Printf("[DORIS-STREAM] Failed to parse response for %s: %v (bytes=%d)", tableName, err, len(body))
		return 0, fmt.Errorf("parse Stream Load response: %w", err)
	}

	// Prefer lowercase fields, fallback to PascalCase.
	status := result.Status
	if status == "" {
		status = result.PStatus
	}
	totalRows := result.NumberOfTotalRows
	if totalRows == 0 && result.PNumberOfTotalRows > 0 {
		totalRows = result.PNumberOfTotalRows
	}
	loadedRows := result.NumberOfLoadedRows
	if loadedRows == 0 && result.PNumberOfLoadedRows > 0 {
		loadedRows = result.PNumberOfLoadedRows
	}
	filteredRows := result.NumberOfFilteredRows
	if filteredRows == 0 && result.PNumberOfFilteredRows > 0 {
		filteredRows = result.PNumberOfFilteredRows
	}
	msg := result.Message
	if msg == "" {
		msg = result.PMessage
	}
	errorURL := result.ErrorURL
	if errorURL == "" {
		errorURL = result.PErrorURL
	}

	log.Printf("[DORIS-STREAM] %s: Status=%s, Total=%d, Loaded=%d, Filtered=%d, Msg=%s",
		tableName, status, totalRows, loadedRows, filteredRows, msg)

	if status == "Success" {
		return loadedRows, nil
	}

	if filteredRows > 0 || loadedRows != totalRows {
		return 0, fmt.Errorf(
			"Stream Load incomplete: Status=%s Total=%d Loaded=%d Filtered=%d Message=%s ErrorURL=%s",
			status, totalRows, loadedRows, filteredRows, msg, errorURL,
		)
	}

	return 0, fmt.Errorf("Stream Load failed: Status=%s, Message=%s, ErrorURL=%s", status, msg, errorURL)
}

// DeleteKeys marks only the supplied, already-reconciled Unique Key rows as deleted.
func (w *DorisWriter) DeleteKeys(ctx context.Context, tableName string, rows []map[string]interface{}, keyCols []string) (int, error) {
	if len(rows) == 0 {
		return 0, nil
	}
	if len(keyCols) == 0 {
		return 0, fmt.Errorf("delete keys require at least one key column")
	}
	objects := make([]map[string]interface{}, 0, len(rows))
	seen := make(map[string]struct{}, len(rows))
	for index, row := range rows {
		object := make(map[string]interface{}, len(keyCols))
		parts := make([]string, len(keyCols))
		for i, column := range keyCols {
			value := lookupCaseInsensitive(row, column)
			if value == nil || strings.TrimSpace(fmt.Sprint(value)) == "" {
				return 0, fmt.Errorf("delete key row %d is missing %s", index, column)
			}
			object[column] = value
			parts[i] = fmt.Sprint(value)
		}
		identity := strings.Join(parts, "\x00")
		if _, exists := seen[identity]; exists {
			return 0, fmt.Errorf("duplicate delete key at row %d", index)
		}
		seen[identity] = struct{}{}
		objects = append(objects, object)
	}
	payload, err := json.Marshal(objects)
	if err != nil {
		return 0, fmt.Errorf("marshal delete keys: %w", err)
	}
	host, user, password := w.getEffectiveTarget()
	if host == "" {
		return 0, fmt.Errorf("Doris target not configured")
	}
	scheme := "http"
	if env := strings.ToLower(os.Getenv("DORIS_USE_HTTPS")); env == "1" || env == "true" {
		scheme = "https"
	}
	url := fmt.Sprintf("%s://%s:8030/api/kingdee_sync/%s/_stream_load", scheme, host, tableName)
	label := "kingdee_delete_" + tableName + "_" + uuid.New().String()
	return w.doStreamLoadWithRedirect(ctx, url, user, password, label, tableName, payload, "DELETE", 0)
}

func lookupCaseInsensitive(row map[string]interface{}, column string) interface{} {
	if value, ok := row[column]; ok {
		return value
	}
	for key, value := range row {
		if strings.EqualFold(key, column) {
			return value
		}
	}
	return nil
}

// getEffectiveTarget caches the target to avoid repeated config lookups.
func (w *DorisWriter) getEffectiveTarget() (host, user, password string) {
	h, u, p, err := w.dorisTarget()
	if err != nil {
		log.Printf("[DORIS-WRITER] Failed to get Doris target: %v", err)
		return "", "", ""
	}
	return h, u, p
}
