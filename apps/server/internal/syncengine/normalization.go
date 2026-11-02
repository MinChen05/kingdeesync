package syncengine

import (
	"fmt"
	"math"
	"regexp"
	"sort"
	"strings"
	"time"
)

// controlCharRe matches ASCII control characters (except normal whitespace).
var controlCharRe = regexp.MustCompile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

// normalizeValue converts float64 whole numbers to int64 and applies the
// project's text convention: leading/trailing whitespace is removed and an
// empty result is stored as NULL.
// （原因：金蝶可能返回超长字符串，需截断到 SQL Server varchar(500) 限制以内）
func normalizeValue(v interface{}) interface{} {
	if v == nil {
		return nil
	}
	if f, ok := v.(float64); ok {
		if f == math.Trunc(f) {
			return int64(f)
		}
	}
	if s, ok := v.(string); ok {
		s = strings.TrimSpace(s)
		// Strip control characters that cause SQL Server JSON parse errors.
		s = controlCharRe.ReplaceAllString(s, "")
		// Truncate to 500 bytes to match SQL Server varchar(500) limit.
		// （原因：金蝶可能返回超过 500 字节的字符串，不截断会导致整个 Stream Load 失败）
		if len(s) > 500 {
			s = truncateUTF8(s, 500)
		}
		if s == "" {
			return nil
		}
		return s
	}
	return v
}

// truncateUTF8 truncates a string to at most maxBytes without breaking UTF-8 characters.
func truncateUTF8(s string, maxBytes int) string {
	if len(s) <= maxBytes {
		return s
	}
	for len(s) > maxBytes {
		s = s[:len(s)-1]
	}
	return s
}

// NormalizeRow applies consistent normalization to a Kingdee row before
// SQL Server: uppercase column names, null/blank string handling,
// float-to-int for whole numbers, and local time for SYNC_TIME.
func NormalizeRow(row map[string]interface{}, cols []string, fieldMap map[string]string, loc *time.Location) map[string]interface{} {
	if loc == nil {
		loc = time.Local
	}

	obj := make(map[string]interface{}, len(cols)+1)

	colToKingdee := buildReverseFieldMap(fieldMap)

	for _, col := range cols {
		v := lookupNormalizedValue(row, col, colToKingdee)
		v = normalizeValue(v)
		obj[col] = v
	}

	// Inject SYNC_TIME as Go-local time.
	obj["SYNC_TIME"] = time.Now().In(loc).Format("2006-01-02 15:04:05")

	return obj
}

// NormalizeRows normalizes a batch of rows and returns a new slice.
func NormalizeRows(rows []map[string]interface{}, cols []string, fieldMap map[string]string, loc *time.Location) []map[string]interface{} {
	if len(rows) == 0 {
		return rows
	}
	result := make([]map[string]interface{}, 0, len(rows))
	for _, row := range rows {
		result = append(result, NormalizeRow(row, cols, fieldMap, loc))
	}
	return result
}

// buildReverseFieldMap creates a map from DB column name (uppercased) to
// Kingdee field names that should be tried for that column.
func buildReverseFieldMap(fieldMap map[string]string) map[string][]string {
	colToKingdee := make(map[string][]string)
	for kingdeeField, dbCol := range fieldMap {
		colToKingdee[strings.ToUpper(dbCol)] = append(colToKingdee[strings.ToUpper(dbCol)], kingdeeField)
	}
	return colToKingdee
}

// lookupNormalizedValue tries the DB column directly, uppercase, then Kingdee
// field names from the reverse map.
func lookupNormalizedValue(row map[string]interface{}, col string, colToKingdee map[string][]string) interface{} {
	if v, ok := row[col]; ok && v != nil {
		return v
	}
	colUpper := strings.ToUpper(col)
	if v, ok := row[colUpper]; ok && v != nil {
		return v
	}
	for _, kf := range colToKingdee[colUpper] {
		if v, ok := row[kf]; ok && v != nil {
			return v
		}
	}
	return nil
}

// ComputePkCount returns the number of distinct primary key tuples in the rows.
func ComputePkCount(rows []map[string]interface{}, pkCols []string) int {
	pkSet := make(map[string]struct{})
	for _, row := range rows {
		key := computePkKey(row, pkCols)
		pkSet[key] = struct{}{}
	}
	return len(pkSet)
}

// buildDBToSource 反转 fieldMap：DB 列名（大写）→ 金蝶源字段名。
func buildDBToSource(fieldMap map[string]string) map[string]string {
	dbToSource := make(map[string]string, len(fieldMap))
	for src, dbCol := range fieldMap {
		dbToSource[strings.ToUpper(dbCol)] = src
	}
	return dbToSource
}

// lookupPKValue 按「DB 列名 → 大写列名 → fieldMap 反查源字段」三级顺序取键值。
// （原因：金蝶返回字段名与 SQL Server 列名常不一致，完整性校验与重复键校验必须同语义）
func lookupPKValue(row map[string]interface{}, col string, dbToSource map[string]string) interface{} {
	if v := row[col]; v != nil {
		return v
	}
	if v := row[strings.ToUpper(col)]; v != nil {
		return v
	}
	if src, ok := dbToSource[strings.ToUpper(col)]; ok {
		return row[src]
	}
	return nil
}

// FindDuplicateBusinessKeys 统计业务键在本批源数据中重复出现的组数，返回至多 limit 个样例。
// 当任一行存在取不到值的键列时返回 (nil, 0)：那种情况属于键缺失，
// 不应被当作重复键报错（原因：无唯一索引的目标表历史上可能已在静默写入空键行，
// 需要单独的排查工单，而不是被本校验一次性改成写入失败）。
func FindDuplicateBusinessKeys(rows []map[string]interface{}, pkCols []string, fieldMap map[string]string, limit int) ([]string, int) {
	if len(rows) == 0 || len(pkCols) == 0 || limit <= 0 {
		return nil, 0
	}
	dbToSource := buildDBToSource(fieldMap)
	counts := make(map[string]int, len(rows))
	for _, row := range rows {
		parts := make([]string, 0, len(pkCols))
		for _, col := range pkCols {
			v := lookupPKValue(row, col, dbToSource)
			if v == nil {
				return nil, 0
			}
			parts = append(parts, fmt.Sprintf("%v", v))
		}
		counts[strings.Join(parts, "|")]++
	}

	dupGroups := 0
	sample := make([]string, 0, limit)
	for key, c := range counts {
		if c < 2 {
			continue
		}
		dupGroups++
		sample = append(sample, fmt.Sprintf("%s×%d", key, c))
	}
	// map 遍历顺序随机，排序后输出才可用于断言与排障
	if dupGroups == 0 {
		return nil, 0
	}
	sort.Slice(sample, func(i, j int) bool { return sample[i] < sample[j] })
	if len(sample) > limit {
		sample = sample[:limit]
	}
	return sample, dupGroups
}

// ValidateSnapshotData checks the source data for completeness before writing.
// fieldMap maps source field names (e.g. "FEntity_FENTRYID") to DB column names (e.g. "FENTRYID").
// （原因：金蝶返回的字段名可能与 SQL Server 列名不一致，需通过映射查找主键值）
func ValidateSnapshotData(rows []map[string]interface{}, pkCols []string, formName string, fieldMap map[string]string) error {
	if len(rows) == 0 {
		return fmt.Errorf("form %s: no source rows for snapshot", formName)
	}
	if len(pkCols) == 0 {
		return fmt.Errorf("form %s: no primary key columns configured", formName)
	}
	dbToSource := buildDBToSource(fieldMap)
	for i, row := range rows {
		for _, col := range pkCols {
			if lookupPKValue(row, col, dbToSource) == nil {
				return fmt.Errorf("form %s: row %d missing primary key values", formName, i)
			}
		}
	}
	return nil
}

func computePkKey(row map[string]interface{}, pkCols []string) string {
	parts := make([]string, 0, len(pkCols))
	for _, col := range pkCols {
		v := row[col]
		if v == nil {
			if colUpper := strings.ToUpper(col); row[colUpper] != nil {
				v = row[colUpper]
			}
		}
		parts = append(parts, fmt.Sprintf("%v", v))
	}
	return strings.Join(parts, "|")
}
