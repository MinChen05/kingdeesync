package syncengine

import (
	"context"
	"fmt"
	"log"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/kingdee-sync/go/internal/gormdb"
)

// SnapshotStatus represents the lifecycle of a per-form snapshot.
type SnapshotStatus string

const (
	SnapshotWriting    SnapshotStatus = "writing"
	SnapshotValidated  SnapshotStatus = "validated"
	SnapshotReconciled SnapshotStatus = "reconciled"
	SnapshotAborted    SnapshotStatus = "aborted"
)

// SnapshotManager coordinates full-sync snapshot metadata: creation,
// validation, safe orphan deletion, and abort paths.
type SnapshotManager struct {
	runID      string
	formName   string
	tableName  string
	snapshotID string
	writer     RowWriter
}

// NewSnapshotManager creates a manager for a single form snapshot.
func NewSnapshotManager(runID, formName, tableName string, writer RowWriter) *SnapshotManager {
	return &SnapshotManager{
		runID:      runID,
		formName:   formName,
		tableName:  tableName,
		snapshotID: "snap-" + uuid.New().String(),
		writer:     writer,
	}
}

// Create persists the initial snapshot metadata.
func (m *SnapshotManager) Create() error {
	meta := gormdb.SnapshotMeta{
		SnapshotID:    m.snapshotID,
		RunID:         m.runID,
		FormName:      m.formName,
		TargetTable:   m.tableName,
		Status:        string(SnapshotWriting),
		FetchedCount:  0,
		WrittenCount:  0,
		DeletedCount:  0,
		PkCount:       0,
		DbCountBefore: 0,
		DbCountAfter:  0,
	}
	if err := gormdb.DB.Create(&meta).Error; err != nil {
		return fmt.Errorf("create snapshot meta for %s: %w", m.formName, err)
	}
	log.Printf("[SNAPSHOT] Created snapshot %s for run=%s form=%s table=%s", m.snapshotID, m.runID, m.formName, m.tableName)
	return nil
}

// UpdateFetched records the number of rows fetched from Kingdee.
func (m *SnapshotManager) UpdateFetched(count int) {
	m.updateStatus(func(meta *gormdb.SnapshotMeta) {
		meta.FetchedCount = int64(count)
	})
}

// UpdateWritten records the number of rows successfully written.
func (m *SnapshotManager) UpdateWritten(count int) {
	m.updateStatus(func(meta *gormdb.SnapshotMeta) {
		meta.WrittenCount = int64(count)
	})
}

// UpdatePkCount records the distinct primary key count from source data.
func (m *SnapshotManager) UpdatePkCount(rows []map[string]interface{}, pkCols []string) {
	pkSet := make(map[string]struct{})
	for _, row := range rows {
		key := m.pkKey(row, pkCols)
		pkSet[key] = struct{}{}
	}
	m.updateStatus(func(meta *gormdb.SnapshotMeta) {
		meta.PkCount = int64(len(pkSet))
	})
}

// Validate checks the snapshot is complete and consistent.
// Returns nil if the snapshot can proceed to orphan deletion.
func (m *SnapshotManager) Validate(rows []map[string]interface{}, pkCols []string) error {
	var meta gormdb.SnapshotMeta
	if err := gormdb.DB.Where("snapshot_id = ?", m.snapshotID).First(&meta).Error; err != nil {
		return fmt.Errorf("load snapshot %s: %w", m.snapshotID, err)
	}

	// Check: fetched rows must be present.
	if meta.FetchedCount == 0 {
		return m.abort("no rows fetched from Kingdee")
	}

	// Check: write must have succeeded.
	if meta.WrittenCount == 0 {
		return m.abort("no rows written to Doris")
	}

	// Check: write count matches fetch count (allow minor tolerance for partial success).
	if meta.WrittenCount < meta.FetchedCount {
		return m.abort(fmt.Sprintf("partial write: fetched=%d written=%d", meta.FetchedCount, meta.WrittenCount))
	}

	// Check: PKs are present in source data.
	if len(pkCols) == 0 {
		return m.abort("no primary key columns configured")
	}

	pkSet := make(map[string]struct{})
	missingPkCount := 0
	for _, row := range rows {
		key := m.pkKey(row, pkCols)
		if key == "" {
			missingPkCount++
			continue
		}
		pkSet[key] = struct{}{}
	}
	if missingPkCount > 0 {
		log.Printf("[SNAPSHOT] Warning: %d rows missing PK values for %s (skipping orphan deletion for those rows)", missingPkCount, m.formName)
	}

	if int64(len(pkSet)) != meta.FetchedCount {
		log.Printf("[SNAPSHOT] Warning: PK count %d differs from fetched %d for %s", len(pkSet), meta.FetchedCount, m.formName)
	}

	m.updateStatus(func(meta *gormdb.SnapshotMeta) {
		meta.Status = string(SnapshotValidated)
		meta.PkCount = int64(len(pkSet))
	})

	log.Printf("[SNAPSHOT] Validated snapshot %s: fetched=%d written=%d pk_count=%d",
		m.snapshotID, meta.FetchedCount, meta.WrittenCount, len(pkSet))
	return nil
}

// DeleteOrphaned safely removes rows from the target table that are not in the snapshot.
// Uses the RowWriter's DeleteOrphaned method after validation.
func (m *SnapshotManager) DeleteOrphaned(ctx context.Context, rows []map[string]interface{}, pkCols []string) (int, error) {
	var meta gormdb.SnapshotMeta
	if err := gormdb.DB.Where("snapshot_id = ?", m.snapshotID).First(&meta).Error; err != nil {
		return 0, fmt.Errorf("load snapshot %s for deletion: %w", m.snapshotID, err)
	}

	if SnapshotStatus(meta.Status) != SnapshotValidated {
		return 0, fmt.Errorf("cannot delete orphans: snapshot %s is in status %q, not validated", m.snapshotID, meta.Status)
	}

	if m.writer == nil {
		return 0, fmt.Errorf("no writer configured for orphan deletion")
	}

	deleted, err := m.writer.DeleteOrphaned(ctx, m.tableName, rows, pkCols)
	if err != nil {
		_ = m.abort(fmt.Sprintf("orphan deletion failed: %v", err))
		return 0, fmt.Errorf("delete orphaned rows: %w", err)
	}

	m.updateStatus(func(meta *gormdb.SnapshotMeta) {
		meta.DeletedCount = int64(deleted)
		meta.Status = string(SnapshotReconciled)
	})

	log.Printf("[SNAPSHOT] Reconciled snapshot %s: deleted=%d", m.snapshotID, deleted)
	return deleted, nil
}

// Abort marks the snapshot as failed with a reason.
func (m *SnapshotManager) Abort(reason string) error {
	return m.abort(reason)
}

func (m *SnapshotManager) abort(reason string) error {
	m.updateStatus(func(meta *gormdb.SnapshotMeta) {
		meta.Status = string(SnapshotAborted)
		meta.ErrorReason = reason
	})
	log.Printf("[SNAPSHOT] Aborted snapshot %s: %s", m.snapshotID, reason)
	return fmt.Errorf("snapshot aborted for %s: %s", m.formName, reason)
}

// updateStatus atomically updates the snapshot metadata.
func (m *SnapshotManager) updateStatus(fn func(*gormdb.SnapshotMeta)) {
	var meta gormdb.SnapshotMeta
	if err := gormdb.DB.Where("snapshot_id = ?", m.snapshotID).First(&meta).Error; err != nil {
		log.Printf("[SNAPSHOT] Warning: failed to load snapshot %s for update: %v", m.snapshotID, err)
		return
	}
	fn(&meta)
	meta.UpdatedAt = time.Now()
	if err := gormdb.DB.Save(&meta).Error; err != nil {
		log.Printf("[SNAPSHOT] Warning: failed to save snapshot %s: %v", m.snapshotID, err)
	}
}

// pkKey builds a composite key string from the row's primary key columns.
func (m *SnapshotManager) pkKey(row map[string]interface{}, pkCols []string) string {
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

// SnapshotID returns the unique identifier for this snapshot.
func (m *SnapshotManager) SnapshotID() string {
	return m.snapshotID
}
