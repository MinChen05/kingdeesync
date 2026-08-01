package syncengine

import (
	"fmt"
	"strconv"
	"strings"
)

var standardCursorKeys = map[string][]string{
	"发货通知单": {"FID", "FEntity_FENTRYID"}, "生产入库单": {"FID", "FEntity_FENTRYID"},
	"销售订单": {"FID", "FSaleOrderEntry_FENTRYID"}, "销售出库单": {"FEntity_FENTRYID"},
	"销售退货单": {"FEntity_FENTRYID"}, "预测订单": {"FEntity_FENTRYID"},
	"生产订单主表": {"FID"}, "生产订单明细": {"FID", "FTreeEntity_FENTRYID"},
	"客户资料": {"FNumber"}, "生产用料清单主表": {"FID"}, "生产用料清单明细表": {"FID", "FEntity_FENTRYID"},
	"物料": {"FNUMBER"}, "仓库": {"FSTOCKID"}, "物料清单": {"FID"},
	"物料清单子项": {"FID", "FTreeEntity_FENTRYID"}, "采购订单": {"FID", "FPOOrderEntry_FENTRYID"},
	"采购入库单": {"FID", "FInStockEntry_FENTRYID"}, "委外订单": {"FID", "FTreeEntity_FENTRYID"},
	"应付单": {"FID", "FEntityDetail_FENTRYID"}, "应收单": {"FID", "FEntityDetail_FENTRYID"},
}

func cursorKeysForForm(form string) []string {
	keys := standardCursorKeys[form]
	return append([]string(nil), keys...)
}

// CursorOrderString returns the deterministic source ordering for a cursor.
func CursorOrderString(columns []string) string {
	parts := make([]string, 0, len(columns))
	for _, column := range columns {
		parts = append(parts, column+" ASC")
	}
	return strings.Join(parts, ",")
}

// ValidateCursorKeyFields ensures every cursor key is requested from Kingdee.
func ValidateCursorKeyFields(fieldKeys, cursorKeys []string) error {
	available := make(map[string]struct{}, len(fieldKeys))
	for _, key := range fieldKeys {
		available[strings.ToUpper(strings.TrimSpace(key))] = struct{}{}
	}
	for _, key := range cursorKeys {
		if _, ok := available[strings.ToUpper(key)]; !ok {
			return fmt.Errorf("cursor key %q is not in FieldKeys", key)
		}
	}
	return nil
}

func cursorValues(row map[string]interface{}, columns []string) ([]interface{}, error) {
	values := make([]interface{}, 0, len(columns))
	for _, column := range columns {
		var value interface{}
		found := false
		for key, candidate := range row {
			if strings.EqualFold(key, column) {
				value, found = candidate, true
				break
			}
		}
		if !found || value == nil || strings.TrimSpace(fmt.Sprint(value)) == "" {
			return nil, fmt.Errorf("cursor row missing or empty %s", column)
		}
		values = append(values, value)
	}
	return values, nil
}

type cursorComparable struct {
	numeric bool
	number  float64
	text    string
}

func comparableCursorValue(value interface{}) (cursorComparable, error) {
	switch typed := value.(type) {
	case nil:
		return cursorComparable{}, fmt.Errorf("is null")
	case float64:
		return cursorComparable{numeric: true, number: typed}, nil
	case float32:
		return cursorComparable{numeric: true, number: float64(typed)}, nil
	case int:
		return cursorComparable{numeric: true, number: float64(typed)}, nil
	case int64:
		return cursorComparable{numeric: true, number: float64(typed)}, nil
	case int32:
		return cursorComparable{numeric: true, number: float64(typed)}, nil
	case string:
		if strings.TrimSpace(typed) == "" {
			return cursorComparable{}, fmt.Errorf("is empty")
		}
		return cursorComparable{text: typed}, nil
	default:
		return cursorComparable{}, fmt.Errorf("has unsupported type %T", value)
	}
}

func compareCursorValues(left, right []interface{}) (int, error) {
	if len(left) != len(right) {
		return 0, fmt.Errorf("cursor key arity mismatch: %d != %d", len(left), len(right))
	}
	for index := range left {
		l, err := comparableCursorValue(left[index])
		if err != nil {
			return 0, err
		}
		r, err := comparableCursorValue(right[index])
		if err != nil {
			return 0, err
		}
		if l.numeric != r.numeric {
			return 0, fmt.Errorf("cursor key type changed at index %d", index)
		}
		if l.numeric {
			if l.number < r.number {
				return -1, nil
			}
			if l.number > r.number {
				return 1, nil
			}
			continue
		}
		if l.text < r.text {
			return -1, nil
		}
		if l.text > r.text {
			return 1, nil
		}
	}
	return 0, nil
}

// ValidateCursorPage rejects missing, duplicate, or non-monotonic cursor rows.
// Rows with empty or null cursor key values are skipped (e.g. header-only rows
// without entry lines in Kingdee cutover forms) instead of failing hard.
func ValidateCursorPage(rows []map[string]interface{}, columns []string, previous []interface{}) ([]interface{}, error) {
	last := previous
	for index, row := range rows {
		current, err := cursorValues(row, columns)
		if err != nil {
			// Skip rows with empty cursor keys (e.g. orders without entry lines)
			continue
		}
		if len(last) > 0 {
			comparison, err := compareCursorValues(current, last)
			if err != nil {
				return nil, err
			}
			if comparison <= 0 {
				return nil, fmt.Errorf("row %d: cursor key is not strictly increasing", index)
			}
		}
		last = current
	}
	return last, nil
}

func cursorLiteral(value interface{}) (string, error) {
	comparable, err := comparableCursorValue(value)
	if err != nil {
		return "", err
	}
	if comparable.numeric {
		return strconv.FormatFloat(comparable.number, 'f', -1, 64), nil
	}
	return "'" + strings.ReplaceAll(comparable.text, "'", "''") + "'", nil
}

// BuildCursorFilter returns the strict lexicographic continuation predicate.
func BuildCursorFilter(base string, columns []string, last []interface{}) (string, error) {
	if len(columns) == 0 || len(columns) != len(last) {
		return "", fmt.Errorf("invalid cursor key arity")
	}
	var build func(int) (string, error)
	build = func(index int) (string, error) {
		literal, err := cursorLiteral(last[index])
		if err != nil {
			return "", err
		}
		greater := columns[index] + " > " + literal
		if index == len(columns)-1 {
			return greater, nil
		}
		next, err := build(index + 1)
		if err != nil {
			return "", err
		}
		return fmt.Sprintf("(%s OR (%s = %s AND %s))", greater, columns[index], literal, next), nil
	}
	predicate, err := build(0)
	if err != nil {
		return "", err
	}
	return "(" + base + ") AND " + predicate, nil
}
