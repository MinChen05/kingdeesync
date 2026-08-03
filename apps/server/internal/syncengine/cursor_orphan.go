package syncengine

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"strings"

	"github.com/jmoiron/sqlx"
)

// sourceKeyCollector accumulates primary-key values of all fetched rows into
// a SQL Server staging table while the cursor pagination loop runs, then
// reconciles (deletes) target rows whose keys are absent from the source.
//
// Why not in-memory? A full sync of 生产用料清单明细表 fetches 4.7M rows;
// holding all PKs in memory is infeasible. A staging table with a clustered
// index on the PK columns lets the anti-join run in the database.
// （原因：百万级 PK 不能放内存，staging 表 + 聚集索引在库里做反连接）
type sourceKeyCollector struct {
	db           *sqlx.DB
	stagingTable string
	pkCols       []string
	// kingdeeField -> db column mapping for value lookup
	fieldMap map[string]string
	total    int
}

func newSourceKeyCollector(ctx context.Context, w *SQLServerWriter, tableName string,
	pkCols []string, fieldMap map[string]string) (*sourceKeyCollector, error) {

	db, databaseName, err := w.openSQL(ctx)
	if err != nil {
		return nil, err
	}
	hash := sha256.Sum256([]byte(tableName + pkCols[0]))
	stagingTable := "srckeys_" + hex.EncodeToString(hash[:8])
	if err := createSourceKeyStaging(ctx, db, databaseName, tableName, stagingTable, pkCols); err != nil {
		return nil, err
	}
	return &sourceKeyCollector{
		db:           db,
		stagingTable: stagingTable,
		pkCols:       pkCols,
		fieldMap:     fieldMap,
	}, nil
}

// Drop removes the staging table.
func (c *sourceKeyCollector) Drop(ctx context.Context) {
	if c.db == nil {
		return
	}
	_, _ = c.db.ExecContext(ctx, "IF OBJECT_ID(N'dbo."+c.stagingTable+"', 'U') IS NOT NULL DROP TABLE dbo."+c.stagingTable)
}

// AddPage extracts PK values from a fetched page and inserts them into the
// staging table. Rows with empty PK values are skipped (header-only rows).
func (c *sourceKeyCollector) AddPage(ctx context.Context, rows []map[string]interface{}) error {
	if len(rows) == 0 {
		return nil
	}
	// Build reverse mapping dbCol -> kingdee fields for lookup
	colToKingdee := make(map[string][]string, len(c.fieldMap))
	for kField, dbCol := range c.fieldMap {
		colToKingdee[strings.ToUpper(dbCol)] = append(colToKingdee[strings.ToUpper(dbCol)], kField)
	}

	keyRows := make([]map[string]interface{}, 0, len(rows))
	for _, row := range rows {
		keyRow := make(map[string]interface{}, len(c.pkCols))
		valid := true
		for _, pk := range c.pkCols {
			value := lookupSourceKeyValue(row, pk, colToKingdee)
			if value == nil || strings.TrimSpace(fmt.Sprint(value)) == "" {
				valid = false
				break
			}
			keyRow[pk] = value
		}
		if valid {
			keyRows = append(keyRows, keyRow)
		}
	}
	if len(keyRows) == 0 {
		return nil
	}
	written, err := batchInsertSourceKeys(ctx, c.db, c.stagingTable, keyRows, c.pkCols)
	if err != nil {
		return err
	}
	c.total += written
	return nil
}

// lookupSourceKeyValue finds a PK column value in a Kingdee row, trying the
// direct key first, then case-insensitive, then the fieldMap reverse mapping.
func lookupSourceKeyValue(row map[string]interface{}, col string, colToKingdee map[string][]string) interface{} {
	if v, ok := row[col]; ok && v != nil {
		return v
	}
	if v, ok := row[strings.ToUpper(col)]; ok && v != nil {
		return v
	}
	for _, kf := range colToKingdee[strings.ToUpper(col)] {
		if v, ok := row[kf]; ok && v != nil {
			return v
		}
	}
	for key, value := range row {
		if value != nil && strings.EqualFold(key, col) {
			return value
		}
	}
	return nil
}

// ReconcileAndDelete verifies the source snapshot is complete (all fetched
// rows were written and staged), then deletes target rows whose PK is absent
// from the staging table. Returns the number of deleted rows.
func (c *sourceKeyCollector) ReconcileAndDelete(ctx context.Context, tableName string,
	fetched, written int) (int, error) {

	// Completeness gate: refuse to delete when the write was partial or the
	// staged key count differs from the fetched count.
	// （原因：源数据不完整时删除会误删，必须先证明快照完整）
	if fetched == 0 || written != fetched {
		return 0, fmt.Errorf("orphan delete blocked: partial write fetched=%d written=%d", fetched, written)
	}
	var stagedCount int
	if err := c.db.GetContext(ctx, &stagedCount, "SELECT COUNT(*) FROM dbo."+c.stagingTable); err != nil {
		return 0, fmt.Errorf("count staged source keys: %w", err)
	}
	if stagedCount != fetched {
		return 0, fmt.Errorf("orphan delete blocked: staged keys=%d fetched=%d", stagedCount, fetched)
	}

	// Anti-join: target rows not present in the source staging table.
	joinClauses := make([]string, len(c.pkCols))
	for i, pk := range c.pkCols {
		joinClauses[i] = fmt.Sprintf("t.[%s] = s.[%s]", pk, pk)
	}
	// Orphan count first (safety/telemetry)
	var orphanCount int
	orphanQuery := fmt.Sprintf(
		"SELECT COUNT(*) FROM dbo.%s t LEFT JOIN dbo.%s s ON %s WHERE s.[%s] IS NULL",
		tableName, c.stagingTable, strings.Join(joinClauses, " AND "), c.pkCols[0],
	)
	if err := c.db.GetContext(ctx, &orphanCount, orphanQuery); err != nil {
		return 0, fmt.Errorf("count orphaned rows: %w", err)
	}
	if orphanCount == 0 {
		return 0, nil
	}

	// Safety cap: never delete more than 10% of the target table without review.
	var targetCount int
	if err := c.db.GetContext(ctx, &targetCount, "SELECT COUNT(*) FROM dbo."+tableName); err != nil {
		return 0, fmt.Errorf("count target rows: %w", err)
	}
	if targetCount > 0 && orphanCount*10 > targetCount {
		return 0, fmt.Errorf("orphan delete blocked: orphans=%d exceed 10%% of target=%d", orphanCount, targetCount)
	}

	// DELETE via the same anti-join.
	deleteSQL := fmt.Sprintf(
		"DELETE t FROM dbo.%s t LEFT JOIN dbo.%s s ON %s WHERE s.[%s] IS NULL",
		tableName, c.stagingTable, strings.Join(joinClauses, " AND "), c.pkCols[0],
	)
	result, err := c.db.ExecContext(ctx, deleteSQL)
	if err != nil {
		return 0, fmt.Errorf("delete orphaned rows from %s: %w", tableName, err)
	}
	n, _ := result.RowsAffected()
	return int(n), nil
}
