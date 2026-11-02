package db

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/kingdee-sync/go/internal/config"
)

// acceptedKeyDrift 记录 issue #3 实测对账中被确认保留的业务键偏差及其定性。
// 出现表外的新偏差会让测试失败（原因：A/B/C/D 类各自的取舍需要人来判定，
// 不允许映射与目标库约束之间发生静默漂移）。
var acceptedKeyDrift = map[string]string{
	// A 类：代码键是库内唯一键的超集，匹配更严格，不改
	"ap_payable":     "A: PK(FENTRYID) 的超集",
	"ar_receivable":  "A: UQ(FENTRYID) 的超集",
	"prd_moentry":    "A: UQ(FENTRYID) 的超集",
	"prd_ppbomentry": "A: UQ(FENTRYID) 的超集",
	"saleorder":      "A: PK(FENTRYID) 的超集",
	"stk_instock":    "A: UQ(FENTRYID) 的超集",
	// B 类：按业务码匹配的既有口径，库内无对应唯一索引（唯一性仅靠约定）
	"bd_material": "B: 按 FNUMBER 匹配，库内无该唯一索引，见 issue #3",
	"customer":    "B: 按 FNUMBER 匹配，库内无该唯一索引，见 issue #3",
	// C 类：目标表完全没有 PK/唯一索引
	"gl_rpt_accountbalance": "C: 堆表无索引，且实测业务键 FBALANCEID 不唯一（318 组重复，最大值 5145 次）→ 键本身也需修正，见 issue #3",
	"sal_returnstock":       "C: 堆表无索引，但实测 FENTRYID 106087 行 0 重复 → 可直接建唯一索引，见 issue #3",
	// D 类：业务粒度决策，转 issue #4
	"stk_inventory": "D: 目标表 PK(FID)，聚合粒度待决策，见 issue #4",
}

// TestPrimaryKeyContractAgainstTargetSchema 对账 primaryKeyMap 与目标库真实约束。
// 只读查询 sys.indexes，需要 MSSQL_INTEGRATION=1（默认跳过，避免连生产库）。
func TestPrimaryKeyContractAgainstTargetSchema(t *testing.T) {
	if os.Getenv("MSSQL_INTEGRATION") != "1" {
		t.Skip("set MSSQL_INTEGRATION=1 to reconcile the key contract against the real target schema")
	}
	if _, err := config.Load(findContractConfigPath(t)); err != nil {
		t.Fatal(err)
	}
	if err := Init(); err != nil {
		t.Fatal(err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()

	rows, err := DB.QueryContext(ctx, `
SELECT LOWER(t.name), CAST(i.is_primary_key AS int), ISNULL(STUFF((SELECT ',' + c.name
        FROM sys.index_columns ic JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
        WHERE ic.object_id = i.object_id AND ic.index_id = i.index_id AND ic.is_included_column = 0
        ORDER BY ic.key_ordinal FOR XML PATH('')), 1, 1, ''), '')
FROM sys.indexes i JOIN sys.tables t ON t.object_id = i.object_id
WHERE i.is_primary_key = 1 OR i.is_unique = 1`)
	if err != nil {
		t.Fatalf("query indexes: %v", err)
	}
	defer rows.Close()

	constraints := map[string][][]string{}
	for rows.Next() {
		var table, cols string
		var isPK int
		if err := rows.Scan(&table, &isPK, &cols); err != nil {
			t.Fatalf("scan: %v", err)
		}
		constraints[table] = append(constraints[table], splitKey(cols))
	}
	if err := rows.Err(); err != nil {
		t.Fatalf("iterate: %v", err)
	}
	rows.Close()

	// 存在性单独取：没有任何 PK/唯一索引的堆表在 sys.indexes 的过滤结果里不会出现，
	// 不能把"无约束"误判成"表不存在"（原因：C 类两张表正是这种堆表）
	existing := map[string]bool{}
	exRows, err := DB.QueryContext(ctx, "SELECT LOWER(name) FROM sys.tables WHERE type = 'U'")
	if err != nil {
		t.Fatalf("query tables: %v", err)
	}
	defer exRows.Close()
	for exRows.Next() {
		var name string
		if err := exRows.Scan(&name); err != nil {
			t.Fatalf("scan tables: %v", err)
		}
		existing[name] = true
	}
	if err := exRows.Err(); err != nil {
		t.Fatalf("iterate tables: %v", err)
	}

	contract := PrimaryKeyContract()
	tables := make([]string, 0, len(contract))
	for tbl := range contract {
		tables = append(tables, tbl)
	}
	sort.Strings(tables)

	unexpected := []string{}
	for _, tbl := range tables {
		key := splitKey(contract[tbl])
		if !existing[tbl] {
			unexpected = append(unexpected, fmt.Sprintf("%s: 目标库不存在该表", tbl))
			continue
		}
		if matchesAnyConstraint(key, constraints[tbl]) {
			continue
		}
		if _, accepted := acceptedKeyDrift[tbl]; accepted {
			continue
		}
		msg := fmt.Sprintf("%s: 业务键 %s 与目标库约束不一致且未被记录", tbl, strings.Join(key, ","))
		if len(constraints[tbl]) == 0 {
			msg = fmt.Sprintf("%s: 目标表没有任何 PK/唯一索引，业务键 %s 无约束兜底", tbl, strings.Join(key, ","))
		}
		unexpected = append(unexpected, msg)
	}

	// 反向漂移：被登记的偏差不再成立（例如 DBA 补建了索引），必须显式更新记录
	for tbl, reason := range acceptedKeyDrift {
		key := splitKey(contract[tbl])
		if len(key) == 0 {
			continue
		}
		if matchesAnyConstraint(key, constraints[tbl]) {
			t.Errorf("%s: 已登记的偏差已不存在（%s），请从 acceptedKeyDrift 中移除", tbl, reason)
		}
	}

	if len(unexpected) > 0 {
		t.Errorf("发现未记录的主键契约漂移：\n  %s", strings.Join(unexpected, "\n  "))
	}
	t.Logf("对账完成：%d 张表，其中 %d 张为已记录偏差", len(tables), len(acceptedKeyDrift))
}

func matchesAnyConstraint(key []string, list [][]string) bool {
	for _, cols := range list {
		if sameKeySet(key, cols) {
			return true
		}
	}
	return false
}

func sameKeySet(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	set := map[string]bool{}
	for _, c := range a {
		set[c] = true
	}
	for _, c := range b {
		if !set[c] {
			return false
		}
	}
	return true
}

func splitKey(s string) []string {
	out := []string{}
	for _, c := range strings.Split(s, ",") {
		c = strings.ToUpper(strings.TrimSpace(c))
		if c != "" {
			out = append(out, c)
		}
	}
	return out
}

// findContractConfigPath 向上查找仓库根的 config.local.ini
// （原因：go test 的 CWD 是包目录，且 apps/server 下存在旧副本，必须取仓库根那一份）
func findContractConfigPath(t *testing.T) string {
	t.Helper()
	dir, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	found := ""
	for i := 0; i < 8; i++ {
		candidate := filepath.Join(dir, "config.local.ini")
		if _, err := os.Stat(candidate); err == nil {
			found = candidate
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	if found == "" {
		t.Fatal("未找到 config.local.ini")
	}
	return found
}
