package syncengine

import (
	"fmt"
	"math"
	"regexp"
	"strings"
	"time"
)

// controlCharRe matches ASCII control characters (except normal whitespace).
var controlCharRe = regexp.MustCompile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

// normalizeValue converts float64 whole numbers to int64 and applies the
// project's text convention: leading/trailing whitespace is removed and an
// empty result is stored as NULL.
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
		// Strip control characters that cause Doris JSON parse errors.
		s = controlCharRe.ReplaceAllString(s, "")
		if s == "" {
			return nil
		}
		return s
	}
	return v
}

// NormalizeRow applies consistent normalization to a Kingdee row before
// Doris Stream Load: uppercase column names, null/blank string handling,
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

// ValidateSnapshotData checks the source data for completeness before writing.
func ValidateSnapshotData(rows []map[string]interface{}, pkCols []string, formName string) error {
	if len(rows) == 0 {
		return fmt.Errorf("form %s: no source rows for snapshot", formName)
	}
	if len(pkCols) == 0 {
		return fmt.Errorf("form %s: no primary key columns configured", formName)
	}
	for i, row := range rows {
		for _, col := range pkCols {
			v := row[col]
			if v == nil {
				if colUpper := strings.ToUpper(col); row[colUpper] != nil {
					v = row[colUpper]
				}
			}
			if v == nil {
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
