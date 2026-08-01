package syncengine

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
)

func validateSourceBusinessDates(rows []map[string]interface{}, businessKeys []string, partitionColumn string) error {
	seen := make(map[string]string, len(rows))
	for index, row := range rows {
		values := make([]interface{}, len(businessKeys))
		for i, column := range businessKeys {
			value := lookupCaseInsensitive(row, column)
			if value == nil || strings.TrimSpace(fmt.Sprint(value)) == "" {
				return fmt.Errorf("source row %d is missing business key %s", index, column)
			}
			values[i] = value
		}
		encoded, _ := json.Marshal(values)
		dateValue := strings.TrimSpace(fmt.Sprint(lookupCaseInsensitive(row, partitionColumn)))
		if dateValue == "" || dateValue == "<nil>" {
			return fmt.Errorf("source row %d is missing partition date %s", index, partitionColumn)
		}
		identity := string(encoded)
		if previous, exists := seen[identity]; exists && previous != dateValue {
			return fmt.Errorf("business key %s changes partition date from %s to %s", identity, previous, dateValue)
		}
		seen[identity] = dateValue
	}
	return nil
}

// ValidateStableBusinessDates blocks writes that would move an existing
// business key to a different physical quarter partition.
func (w *DorisWriter) ValidateStableBusinessDates(
	ctx context.Context,
	targetTable string,
	rows []map[string]interface{},
	businessKeys []string,
	partitionColumn string,
) error {
	if !dorisIdentifier.MatchString(targetTable) || !dorisIdentifier.MatchString(partitionColumn) || len(businessKeys) == 0 {
		return fmt.Errorf("invalid partition-date validation input")
	}
	for _, column := range businessKeys {
		if !dorisIdentifier.MatchString(column) {
			return fmt.Errorf("invalid business key column %q", column)
		}
	}
	if err := validateSourceBusinessDates(rows, businessKeys, partitionColumn); err != nil {
		return err
	}
	storageKeys := append(append([]string{}, businessKeys...), partitionColumn)
	canonical, snapshotHash, _, err := canonicalSourceKeys(rows, storageKeys)
	if err != nil {
		return err
	}
	db, databaseName, err := w.openDorisSQL(ctx)
	if err != nil {
		return err
	}
	defer db.Close()
	stagingTable := "partition_dates_" + snapshotHash[:16]
	if err := createSourceKeyStaging(ctx, db, databaseName, targetTable, stagingTable, storageKeys); err != nil {
		return err
	}
	defer func() { _, _ = db.ExecContext(context.Background(), "DROP TABLE IF EXISTS `"+stagingTable+"`") }()
	identityMap := make(map[string]string, len(storageKeys))
	for _, column := range storageKeys {
		identityMap[column] = column
	}
	written, err := w.Upsert(ctx, stagingTable, canonical, storageKeys, storageKeys, identityMap)
	if err != nil || written != len(canonical) {
		return fmt.Errorf("stage partition dates: written=%d expected=%d: %w", written, len(canonical), err)
	}
	joins := make([]string, len(businessKeys))
	for i, column := range businessKeys {
		joins[i] = "t.`" + column + "` <=> s.`" + column + "`"
	}
	query := fmt.Sprintf(
		"SELECT COUNT(*) FROM `%s` t JOIN `%s` s ON %s WHERE NOT (t.`%s` <=> s.`%s`)",
		targetTable, stagingTable, strings.Join(joins, " AND "), partitionColumn, partitionColumn,
	)
	var mismatches int64
	if err := db.GetContext(ctx, &mismatches, query); err != nil {
		return fmt.Errorf("validate existing partition dates: %w", err)
	}
	if mismatches > 0 {
		return fmt.Errorf("%d existing business keys would move across partitions", mismatches)
	}
	return nil
}
