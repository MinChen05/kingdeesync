package syncengine

import (
	"context"
)

// UpsertResult holds the breakdown of upsert outcomes.
// （原因：SQL Server MERGE 同时完成 INSERT 和 UPDATE，需拆分行级统计供变更审计使用）
type UpsertResult struct {
	Inserted int `json:"inserted"`
	Updated  int `json:"updated"`
	Total    int `json:"total"`
}

// RowWriter abstracts the database write path so the sync engine
// can work with SQL Server or other targets without knowing details.
// （原因：解耦同步引擎与具体数据库，为 SQL Server 改造提供扩展点）
type RowWriter interface {
	// Upsert writes rows into the target table using the configured strategy
	// (e.g., SQL Server MERGE).
	// tableName: target table name (e.g., "bd_stock")
	// rows: Kingdee API rows as map[fieldName]->value
	// cols: DB column names that will be written (ordered)
	// pkCols: primary key column names
	// fieldMap: mapping from Kingdee field names to DB column names (for value lookup)
	Upsert(ctx context.Context, tableName string, rows []map[string]interface{},
		cols []string, pkCols []string, fieldMap map[string]string) (UpsertResult, error)

	// DeleteOrphaned removes rows that exist in DB but not in the provided Kingdee data.
	// Used for full sync to keep DB in sync with Kingdee deletions.
	DeleteOrphaned(ctx context.Context, tableName string, rows []map[string]interface{},
		pkCols []string) (int, error)

	// Close releases any resources held by the writer.
	Close() error
}

// SnapshotReplacer 是 RowWriter 的可选能力：在单个事务内替换目标表内容。
// 实现方必须保证任一步失败即回滚，目标表保持上一轮快照。
// （原因：此前引擎在事务外 TRUNCATE，写入失败就变成"生产表被清空"——
// 2026-11-02 事故中 stk_inventory 连续 5 轮被清空为 0 行，见 ADR-0007）
//
// scopeCols 限定替换作用域：非空时只替换"这些列的组合与本次快照相同"的目标行，
// 使增量窗口不再抹掉窗口外的历史数据（科目余额表按 FACCTYEAR/FACCTPERIOD，
// 见 docs/superpowers/plans/2026-11-02-balance-scoped-snapshot-replace.md）；
// 为空则整表替换（即时库存）。
type SnapshotReplacer interface {
	ReplaceSnapshot(ctx context.Context, tableName string, rows []map[string]interface{},
		cols []string, pkCols []string, fieldMap map[string]string, scopeCols []string) (UpsertResult, error)
}
