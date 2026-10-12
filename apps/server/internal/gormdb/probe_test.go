package gormdb

import (
	"os"
	"path/filepath"
	"testing"
	"time"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

// setupStateFileTestDB opens a file-backed SQLite state DB so tests can
// exercise ProbeStateDB against a real file (memory mode never touches disk).
// Conn lifetime is set to 1ns so every acquisition recycles the connection,
// forcing a file reopen — the same path production hits after the 30-minute
// ConnMaxLifetime expiry.
// （原因：生产环境句柄保留 fd，读取仅在连接池回收后重新打开路径并失败；
//  测试必须模拟回收触发 reopen 才能复现状态文件删除事故）
func setupStateFileTestDB(t *testing.T, path string) *gorm.DB {
	t.Helper()
	oldDB := DB
	db, err := gorm.Open(sqlite.Open(path + "?_journal_mode=WAL&_busy_timeout=5000"), &gorm.Config{})
	if err != nil {
		t.Fatalf("open sqlite state file: %v", err)
	}
	DB = db
	if sqlDB, err := db.DB(); err == nil {
		sqlDB.SetMaxOpenConns(1)
		sqlDB.SetMaxIdleConns(1)
		sqlDB.SetConnMaxLifetime(time.Nanosecond)
	}
	if err := AutoMigrate(); err != nil {
		t.Fatalf("migrate sqlite state file: %v", err)
	}
	t.Cleanup(func() {
		DB = oldDB
		if sqlDB, err := db.DB(); err == nil {
		_ = sqlDB.Close()
		}
	})
	return db
}

func TestProbeStateDBHealthy(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "go_state.db")
	setupStateFileTestDB(t, path)
	if err := ProbeStateDB(); err != nil {
		t.Fatalf("probe must pass on a healthy state file: %v", err)
	}
}

func TestProbeStateDBDetectsDeletedFile(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "go_state.db")
	setupStateFileTestDB(t, path)
	if err := ProbeStateDB(); err != nil {
		t.Fatalf("sanity probe failed unexpectedly: %v", err)
	}

	// Delete the backing file and WAL sidecars while the DB handle stays open,
	// mirroring the production incident where .run/state was removed underneath.
	// （原因：复现 09-05 状态文件删除事故，证明探针可检测悬失效句柄）
	if err := os.Remove(path); err != nil {
		t.Fatalf("state file must be removable: %v", err)
	}
	_ = os.Remove(path + "-wal")
	_ = os.Remove(path + "-shm")
	if err := ProbeStateDB(); err == nil {
		t.Fatal("probe must detect a deleted state file")
	}
}
