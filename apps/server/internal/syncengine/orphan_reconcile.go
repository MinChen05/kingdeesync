package syncengine

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"regexp"
	"sort"
	"strings"

	"github.com/jmoiron/sqlx"
	"github.com/kingdee-sync/go/internal/config"
	"github.com/kingdee-sync/go/internal/gormdb"
)

var dorisIdentifier = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]*$`)

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
func (w *DorisWriter) ReconcileOrphans(ctx context.Context, input OrphanReconcileInput) (OrphanReconcileResult, error) {
	result := OrphanReconcileResult{}
	if input.SnapshotID == "" || !dorisIdentifier.MatchString(input.TargetTable) || len(input.StorageKeyColumns) == 0 {
		return result, fmt.Errorf("invalid orphan reconciliation input")
	}
	for _, column := range input.StorageKeyColumns {
		if !dorisIdentifier.MatchString(column) {
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

	db, databaseName, err := w.openDorisSQL(ctx)
	if err != nil {
		return result, err
	}
	defer db.Close()

	stagingTable := "snapshot_keys_" + snapshotHash[:16]
	if err := createSourceKeyStaging(ctx, db, databaseName, input.TargetTable, stagingTable, input.StorageKeyColumns); err != nil {
		return result, err
	}
	defer func() { _, _ = db.ExecContext(context.Background(), "DROP TABLE IF EXISTS `"+stagingTable+"`") }()

	identityMap := make(map[string]string, len(input.StorageKeyColumns))
	for _, column := range input.StorageKeyColumns {
		identityMap[column] = column
	}
	written, err := w.Upsert(ctx, stagingTable, canonicalRows, input.StorageKeyColumns, input.StorageKeyColumns, identityMap)
	if err != nil || written != len(canonicalRows) {
		return result, fmt.Errorf("stage source keys: written=%d expected=%d: %w", written, len(canonicalRows), err)
	}
	if err := db.GetContext(ctx, &result.TargetCount, "SELECT COUNT(*) FROM `"+input.TargetTable+"`"); err != nil {
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

func (w *DorisWriter) openDorisSQL(ctx context.Context) (*sqlx.DB, string, error) {
	host, user, password, err := w.dorisTarget()
	if err != nil {
		return nil, "", err
	}
	databaseName := "kingdee_sync"
	if cfg := config.Get(); cfg != nil && cfg.GetEffectiveDatabase().DBName != "" {
		databaseName = cfg.GetEffectiveDatabase().DBName
	}
	dsn := fmt.Sprintf("%s:%s@tcp(%s:9030)/%s", user, password, host, databaseName)
	db, err := sqlx.ConnectContext(ctx, "mysql", dsn)
	if err != nil {
		return nil, "", fmt.Errorf("connect to Doris MySQL protocol: %w", err)
	}
	return db, databaseName, nil
}

func createSourceKeyStaging(ctx context.Context, db *sqlx.DB, databaseName, targetTable, stagingTable string, keyColumns []string) error {
	types := make(map[string]string, len(keyColumns))
	rows, err := db.QueryxContext(ctx, `SELECT COLUMN_NAME, COLUMN_TYPE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?`, databaseName, targetTable)
	if err != nil {
		return fmt.Errorf("load target key types: %w", err)
	}
	defer rows.Close()
	for rows.Next() {
		var name, columnType string
		if err := rows.Scan(&name, &columnType); err != nil {
			return err
		}
		types[strings.ToUpper(name)] = columnType
	}
	definitions := make([]string, len(keyColumns))
	quotedKeys := make([]string, len(keyColumns))
	for i, column := range keyColumns {
		columnType := types[strings.ToUpper(column)]
		if columnType == "" {
			return fmt.Errorf("target table %s lacks storage key column %s", targetTable, column)
		}
		definitions[i] = fmt.Sprintf("`%s` %s NOT NULL", column, columnType)
		quotedKeys[i] = "`" + column + "`"
	}
	_, _ = db.ExecContext(ctx, "DROP TABLE IF EXISTS `"+stagingTable+"`")
	ddl := fmt.Sprintf(
		"CREATE TABLE `%s` (%s, `SYNC_TIME` DATETIME NULL) UNIQUE KEY(%s) DISTRIBUTED BY HASH(%s) BUCKETS 1 PROPERTIES (\"enable_unique_key_merge_on_write\"=\"true\", \"replication_num\"=\"1\")",
		stagingTable, strings.Join(definitions, ", "), strings.Join(quotedKeys, ", "), quotedKeys[0],
	)
	if _, err := db.ExecContext(ctx, ddl); err != nil {
		return fmt.Errorf("create source key staging table: %w", err)
	}
	return nil
}

func queryOrphanKeys(ctx context.Context, db *sqlx.DB, targetTable, stagingTable string, keyColumns []string) ([]map[string]interface{}, error) {
	selectColumns := make([]string, len(keyColumns))
	joins := make([]string, len(keyColumns))
	for i, column := range keyColumns {
		selectColumns[i] = "t.`" + column + "`"
		joins[i] = "t.`" + column + "` <=> s.`" + column + "`"
	}
	query := fmt.Sprintf(
		"SELECT %s FROM `%s` t LEFT JOIN `%s` s ON %s WHERE s.`%s` IS NULL",
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
