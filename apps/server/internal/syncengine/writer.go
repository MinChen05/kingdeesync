package syncengine

import (
	"context"
)

// RowWriter abstracts the database write path so the sync engine
// can work with Doris (Stream Load) or other targets without knowing details.
// （原因：解耦同步引擎与具体数据库，为 Doris-only 改造提供扩展点）
type RowWriter interface {
	// Upsert writes rows into the target table using the configured strategy
	// (e.g., Doris Stream Load with UNIQUE KEY merge-on-write).
	// tableName: target table name (e.g., "bd_stock")
	// rows: Kingdee API rows as map[fieldName]->value
	// cols: DB column names that will be written (ordered)
	// pkCols: primary key column names
	// fieldMap: mapping from Kingdee field names to DB column names (for value lookup)
	Upsert(ctx context.Context, tableName string, rows []map[string]interface{},
		cols []string, pkCols []string, fieldMap map[string]string) (int, error)

	// DeleteOrphaned removes rows that exist in DB but not in the provided Kingdee data.
	// Used for full sync to keep DB in sync with Kingdee deletions.
	DeleteOrphaned(ctx context.Context, tableName string, rows []map[string]interface{},
		pkCols []string) (int, error)

	// Close releases any resources held by the writer.
	Close() error
}
