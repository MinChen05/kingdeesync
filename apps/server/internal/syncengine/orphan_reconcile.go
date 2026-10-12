package syncengine

import (
	"context"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"sort"
	"strings"

	"github.com/jmoiron/sqlx"
	"github.com/kingdee-sync/go/internal/config"
	"github.com/kingdee-sync/go/internal/db"
	"github.com/kingdee-sync/go/internal/gormdb"
)

// sqlIdentifier 校验已统一至 config.IsSQLIdentifier（原因：多包共享同一标识符规则）

type OrphanReconcileInput struct {
	SnapshotID          string
	TargetTable         string
	SourceRows          []map[string]interface{}
	StorageKeyColumns   []string
	PreviousSourceCount int64
	ExecuteDelete       bool
}

type OrphanReconcileResult struct {
	SnapshotHash  string
	SourceCount   int64
	TargetCount   int64
	OrphanCount   int64
	DuplicateKeys int64
	Decision      OrphanDeleteDecision
	Reason        string
	DeletedCount  int
	OrphanRows    []map[string]interface{}
}

func ValidateSourceStorageKeys(rows []map[string]interface{}, keyColumns []string) (snapshotHash string, distinctCount int, duplicateCount int64, err error) {
	canonical, snapshotHash, duplicateCount, err := canonicalSourceKeys(rows, keyColumns)
	return snapshotHash, len(canonical), duplicateCount, err
}

// ReconcileOrphans stages the immutable source-key snapshot, computes a target
// anti-join, applies safety gates, and optionally deletes only target-only keys.
func (w *SQLServerWriter) ReconcileOrphans(ctx context.Context, input OrphanReconcileInput) (OrphanReconcileResult, error) {
	result := OrphanReconcileResult{}
	if input.SnapshotID == "" || !config.IsSQLIdentifier(input.TargetTable) || len(input.StorageKeyColumns) == 0 {
		return result, fmt.Errorf("invalid orphan reconciliation input")
	}
	for _, column := range input.StorageKeyColumns {
		if !config.IsSQLIdentifier(column) {
			return result, fmt.Errorf("invalid storage key column %q", column)
		}
	}
	canonicalRows, snapshotHash, duplicates, err := canonicalSourceKeys(input.SourceRows, input.StorageKeyColumns)
	if err != nil {
		return result, err
	}
	result.SnapshotHash = snapshotHash
	result.SourceCount = int64(len(canonicalRows))
	result.DuplicateKeys = duplicates

	db, databaseName, err := w.openSQL(ctx)
	if err != nil {
		return result, err
	}
	// db is the shared SQL Server connection; do NOT close it here.
	// （原因：openSQL 返回全局 db.DB，Close 会关闭主连接）

	stagingTable := "snapshot_keys_" + snapshotHash[:16]
	if err := createSourceKeyStaging(ctx, db, databaseName, input.TargetTable, stagingTable, input.StorageKeyColumns); err != nil {
		return result, err
	}
	defer func() {
		_, _ = db.ExecContext(context.Background(), "IF OBJECT_ID(N'dbo."+stagingTable+"', 'U') IS NOT NULL DROP TABLE dbo."+stagingTable)
	}()

	// Insert canonical source keys directly into the staging table
	// (plain INSERT, not the writer's staging MERGE path).
	// （原因：source key 表不是业务表，直接批量 INSERT 即可）
	written, err := batchInsertSourceKeys(ctx, db, stagingTable, canonicalRows, input.StorageKeyColumns)
	if err != nil || written != len(canonicalRows) {
		return result, fmt.Errorf("stage source keys: written=%d expected=%d: %w", written, len(canonicalRows), err)
	}
	if err := db.GetContext(ctx, &result.TargetCount, "SELECT COUNT(*) FROM "+input.TargetTable+""); err != nil {
		return result, fmt.Errorf("count target table: %w", err)
	}
	orphans, err := queryOrphanKeys(ctx, db, input.TargetTable, stagingTable, input.StorageKeyColumns)
	if err != nil {
		return result, err
	}
	result.OrphanRows = orphans
	result.OrphanCount = int64(len(orphans))

	safety := EvaluateOrphanDelete(OrphanSafetyInput{
		SourceCount: result.SourceCount, PreviousSourceCount: input.PreviousSourceCount,
		TargetCount: result.TargetCount, OrphanCount: result.OrphanCount,
		DuplicateKeys: result.DuplicateKeys,
	})
	result.Decision, result.Reason = safety.Decision, safety.Reason
	if !input.ExecuteDelete {
		return result, nil
	}
	if safety.Decision == OrphanDeleteBlocked {
		return result, fmt.Errorf("orphan delete blocked: %s", safety.Reason)
	}
	if safety.Decision == OrphanDeleteApprovalRequired {
		if err := gormdb.ConsumeOrphanDeleteApproval(
			input.SnapshotID, input.TargetTable, snapshotHash, result.OrphanCount,
		); err != nil {
			return result, fmt.Errorf("orphan delete approval required: %w", err)
		}
	}
	deleted, err := w.DeleteKeys(ctx, input.TargetTable, orphans, input.StorageKeyColumns)
	if err != nil {
		return result, err
	}
	result.DeletedCount = deleted
	if int64(deleted) != result.OrphanCount {
		return result, fmt.Errorf("orphan delete incomplete: deleted=%d expected=%d", deleted, result.OrphanCount)
	}
	return result, nil
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

func canonicalSourceKeys(rows []map[string]interface{}, keyColumns []string) ([]map[string]interface{}, string, int64, error) {
	encoded := make([]string, 0, len(rows))
	canonical := make([]map[string]interface{}, 0, len(rows))
	seen := make(map[string]struct{}, len(rows))
	var duplicates int64
	for index, row := range rows {
		keyRow := make(map[string]interface{}, len(keyColumns))
		values := make([]interface{}, len(keyColumns))
		for i, column := range keyColumns {
			value := lookupCaseInsensitive(row, column)
			if value == nil || strings.TrimSpace(fmt.Sprint(value)) == "" {
				return nil, "", duplicates, fmt.Errorf("source key row %d is missing %s", index, column)
			}
			keyRow[column] = value
			values[i] = value
		}
		data, err := json.Marshal(values)
		if err != nil {
			return nil, "", duplicates, fmt.Errorf("encode source key row %d: %w", index, err)
		}
		identity := string(data)
		if _, exists := seen[identity]; exists {
			duplicates++
			continue
		}
		seen[identity] = struct{}{}
		encoded = append(encoded, identity)
		canonical = append(canonical, keyRow)
	}
	sort.Strings(encoded)
	hash := sha256.Sum256([]byte(strings.Join(encoded, "\n")))
	return canonical, hex.EncodeToString(hash[:]), duplicates, nil
}

func (w *SQLServerWriter) openSQL(ctx context.Context) (*sqlx.DB, string, error) {
	// Reuse the global SQL Server connection (db.DB).
	// （原因：Doris 时代的独立 9030 连接已废弃；SQL Server 目标库就是主连接）
	if db.DB == nil {
		return nil, "", fmt.Errorf("database not initialized")
	}
	databaseName := "kingdee_sync"
	if cfg := config.Get(); cfg != nil && cfg.GetEffectiveDatabase().DBName != "" {
		databaseName = cfg.GetEffectiveDatabase().DBName
	}
	return db.DB, databaseName, nil
}

func createSourceKeyStaging(ctx context.Context, db *sqlx.DB, databaseName, targetTable, stagingTable string, keyColumns []string) error {
	// Load target key column types from INFORMATION_SCHEMA (SQL Server).
	// Use @p1 named parameter — go-mssqldb rejects "?" placeholders.
	// （原因：mssql 驱动只认 @pN，"?" 会语法错误导致 staging 建表失败）
	types := make(map[string]string, len(keyColumns))
	rows, err := db.QueryxContext(ctx, `SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE
		FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = @p1`, targetTable)
	if err != nil {
		return fmt.Errorf("load target key types: %w", err)
	}
	defer rows.Close()
	for rows.Next() {
		var name, dataType string
		var maxLen sql.NullInt64
		var precision, scale sql.NullInt64
		if err := rows.Scan(&name, &dataType, &maxLen, &precision, &scale); err != nil {
			return err
		}
		types[strings.ToUpper(name)] = mapSourceKeyType(dataType, maxLen, precision, scale)
	}
	definitions := make([]string, len(keyColumns))
	quotedKeys := make([]string, len(keyColumns))
	for i, column := range keyColumns {
		columnType := types[strings.ToUpper(column)]
		if columnType == "" {
			return fmt.Errorf("target table %s lacks storage key column %s", targetTable, column)
		}
		definitions[i] = fmt.Sprintf("[%s] %s NOT NULL", column, columnType)
		quotedKeys[i] = "[" + column + "]"
	}
	_, _ = db.ExecContext(ctx, "IF OBJECT_ID(N'dbo."+stagingTable+"', 'U') IS NOT NULL DROP TABLE dbo."+stagingTable)
	ddl := fmt.Sprintf(
		"CREATE TABLE dbo.%s (%s, SYNC_TIME DATETIME NULL)",
		stagingTable, strings.Join(definitions, ", "),
	)
	if _, err := db.ExecContext(ctx, ddl); err != nil {
		return fmt.Errorf("create source key staging table: %w", err)
	}
	// Clustered index on the key columns speeds up the anti-join below.
	idxSQL := fmt.Sprintf("CREATE CLUSTERED INDEX [IX_%s] ON dbo.%s (%s)",
		stagingTable, stagingTable, strings.Join(quotedKeys, ", "))
	if _, err := db.ExecContext(ctx, idxSQL); err != nil {
		return fmt.Errorf("create source key staging index: %w", err)
	}
	return nil
}

// mapSourceKeyType maps an INFORMATION_SCHEMA column type to a SQL Server DDL type.
func mapSourceKeyType(dataType string, maxLen sql.NullInt64, precision, scale sql.NullInt64) string {
	switch strings.ToLower(dataType) {
	case "nvarchar", "varchar":
		if maxLen.Valid && maxLen.Int64 > 0 && maxLen.Int64 != 2147483647 {
			return strings.ToUpper(dataType) + fmt.Sprintf("(%d)", maxLen.Int64)
		}
		return "NVARCHAR(MAX)"
	case "nchar", "char":
		if maxLen.Valid && maxLen.Int64 > 0 {
			return strings.ToUpper(dataType) + fmt.Sprintf("(%d)", maxLen.Int64)
		}
		return "NVARCHAR(500)"
	case "decimal", "numeric":
		if precision.Valid && scale.Valid {
			return fmt.Sprintf("DECIMAL(%d,%d)", precision.Int64, scale.Int64)
		}
		return "DECIMAL(18,4)"
	default:
		return strings.ToUpper(dataType)
	}
}

// batchInsertSourceKeys inserts canonical key rows into the staging table
// using a plain parameter-free VALUES insert (small key sets).
func batchInsertSourceKeys(ctx context.Context, db *sqlx.DB, stagingTable string,
	rows []map[string]interface{}, keyColumns []string) (int, error) {

	if len(rows) == 0 {
		return 0, nil
	}
	colList := "[" + strings.Join(keyColumns, "], [") + "]"
	const batchSize = 1000
	total := 0
	for start := 0; start < len(rows); start += batchSize {
		end := start + batchSize
		if end > len(rows) {
			end = len(rows)
		}
		batch := rows[start:end]
		var builder strings.Builder
		builder.WriteString("INSERT INTO dbo.")
		builder.WriteString(stagingTable)
		builder.WriteString(" (")
		builder.WriteString(colList)
		builder.WriteString(") VALUES ")
		for i, row := range batch {
			if i > 0 {
				builder.WriteString(",")
			}
			builder.WriteString("(")
			for j, col := range keyColumns {
				if j > 0 {
					builder.WriteString(",")
				}
				value := lookupCaseInsensitive(row, col)
				if value == nil {
					value = ""
				}
				builder.WriteString(renderKeyLiteral(value))
			}
			builder.WriteString(")")
		}
		if _, err := db.ExecContext(ctx, builder.String()); err != nil {
			return total, fmt.Errorf("insert source keys into %s: %w", stagingTable, err)
		}
		total += len(batch)
	}
	return total, nil
}

// renderKeyLiteral renders a key value as a SQL literal (strings quoted, numbers raw).
func renderKeyLiteral(value interface{}) string {
	switch val := value.(type) {
	case string:
		return "N'" + strings.ReplaceAll(val, "'", "''") + "'"
	case int64:
		return fmt.Sprintf("%d", val)
	case float64:
		return fmt.Sprintf("%v", val)
	case bool:
		if val {
			return "1"
		}
		return "0"
	default:
		s := fmt.Sprintf("%v", val)
		return "N'" + strings.ReplaceAll(s, "'", "''") + "'"
	}
}

func queryOrphanKeys(ctx context.Context, db *sqlx.DB, targetTable, stagingTable string, keyColumns []string) ([]map[string]interface{}, error) {
	selectColumns := make([]string, len(keyColumns))
	joins := make([]string, len(keyColumns))
	for i, column := range keyColumns {
		selectColumns[i] = "t." + column + ""
		joins[i] = "t." + column + " = s." + column + ""
	}
	query := fmt.Sprintf(
		"SELECT %s FROM %s t LEFT JOIN %s s ON %s WHERE s.%s IS NULL",
		strings.Join(selectColumns, ", "), targetTable, stagingTable, strings.Join(joins, " AND "), keyColumns[0],
	)
	rows, err := db.QueryxContext(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("query target-only keys: %w", err)
	}
	defer rows.Close()
	result := []map[string]interface{}{}
	for rows.Next() {
		values, err := rows.SliceScan()
		if err != nil {
			return nil, err
		}
		item := make(map[string]interface{}, len(keyColumns))
		for i, column := range keyColumns {
			if bytesValue, ok := values[i].([]byte); ok {
				item[column] = string(bytesValue)
			} else {
				item[column] = values[i]
			}
		}
		result = append(result, item)
	}
	return result, rows.Err()
}
