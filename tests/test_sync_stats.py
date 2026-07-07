"""Tests for sync stats SQLite recording (direction B).

Verifies the DB schema and query logic without importing data_sync module.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from datetime import datetime
from unittest.mock import Mock, patch


def _create_tables(conn: sqlite3.Connection) -> None:
    """Create the same schema as _record_run_stats in data_sync.py."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS run_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            sync_type TEXT,
            status TEXT,
            total_records INTEGER,
            duration_seconds REAL,
            failed_forms TEXT,
            finished_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS form_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            form_name TEXT,
            table_name TEXT,
            fetched INTEGER,
            inserted INTEGER,
            status TEXT,
            duration_seconds REAL,
            finished_at TEXT
        )
    """)


def _insert_run(conn: sqlite3.Connection, run_id: str,
                sync_type: str = "incremental",
                status: str = "success",
                total_records: int = 100,
                duration: float = 60.0,
                failed_forms: str = "") -> None:
    conn.execute(
        "INSERT INTO run_stats VALUES (NULL,?,?,?,?,?,?,datetime('now','localtime'))",
        (run_id, sync_type, status, total_records, duration, failed_forms),
    )


def _insert_form(conn: sqlite3.Connection, run_id: str,
                 form_name: str = "物料",
                 table_name: str = "bd_material",
                 fetched: int = 10, inserted: int = 10,
                 status: str = "success",
                 duration: float = 1.0) -> None:
    conn.execute(
        "INSERT INTO form_stats (run_id, form_name, table_name, fetched, inserted, "
        "status, duration_seconds, finished_at) VALUES (?,?,?,?,?,?,?,datetime('now','localtime'))",
        (run_id, form_name, table_name, fetched, inserted, status, duration),
    )


class SyncStatsSchemaTests(unittest.TestCase):
    """验证 SQLite 表结构和查询逻辑"""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        self.conn = sqlite3.connect(self.db_path)
        _create_tables(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        try:
            os.unlink(self.db_path)
        except Exception:
            pass

    def test_run_stats_table_created(self):
        """run_stats 表应存在"""
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='run_stats'"
        )
        self.assertIsNotNone(cursor.fetchone())

    def test_form_stats_table_created(self):
        """form_stats 表应存在"""
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='form_stats'"
        )
        self.assertIsNotNone(cursor.fetchone())

    def test_insert_and_query_run(self):
        """插入后应能按时间范围查询"""
        _insert_run(self.conn, "run-001")
        self.conn.commit()
        rows = self.conn.execute(
            "SELECT run_id, status FROM run_stats"
        ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "run-001")
        self.assertEqual(rows[0][1], "success")

    def test_insert_and_query_form(self):
        """插入表单级数据后应能查询"""
        _insert_form(self.conn, "run-001")
        self.conn.commit()
        rows = self.conn.execute(
            "SELECT form_name, inserted FROM form_stats"
        ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "物料")
        self.assertEqual(rows[0][1], 10)

    def test_run_stats_7_days_filter(self):
        """近 7 天查询应只返回有效记录"""
        _insert_run(self.conn, "run-001")
        self.conn.commit()
        rows = self.conn.execute(
            "SELECT COUNT(*) FROM run_stats "
            "WHERE finished_at >= datetime('now','localtime','-7 days')"
        ).fetchall()
        self.assertEqual(rows[0][0], 1)

    def test_form_stats_ranking(self):
        """写入排行查询应按 inserted 降序"""
        _insert_form(self.conn, "run-001", form_name="大表", inserted=500)
        _insert_form(self.conn, "run-001", form_name="中表", inserted=50)
        _insert_form(self.conn, "run-001", form_name="小表", inserted=5)
        self.conn.commit()
        rows = self.conn.execute(
            "SELECT form_name, SUM(inserted) AS total_ins "
            "FROM form_stats GROUP BY form_name ORDER BY total_ins DESC"
        ).fetchall()
        self.assertEqual([r[0] for r in rows], ["大表", "中表", "小表"])

    def test_run_status_grouping(self):
        """按 status 分组应返回正确的计数"""
        _insert_run(self.conn, "r1", status="success")
        _insert_run(self.conn, "r2", status="success")
        _insert_run(self.conn, "r3", status="partial")
        _insert_run(self.conn, "r4", status="failed")
        self.conn.commit()
        rows = dict(
            self.conn.execute(
                "SELECT status, COUNT(*) FROM run_stats GROUP BY status"
            ).fetchall()
        )
        self.assertEqual(rows.get("success"), 2)
        self.assertEqual(rows.get("partial"), 1)
        self.assertEqual(rows.get("failed"), 1)

    def test_record_run_stats_uses_table_mapping_when_result_table_name_missing(self):
        """正式同步结果缺少 table_name 时，应从表单映射补齐本地统计表名。"""
        from src.core.data_sync import DataSyncManager, SyncStatus, SyncType

        with tempfile.TemporaryDirectory() as tmp_dir:
            previous_cwd = os.getcwd()
            os.chdir(tmp_dir)
            try:
                os.mkdir("logs")
                manager = DataSyncManager.__new__(DataSyncManager)
                manager.table_mapping = {"采购入库单": "STK_InStock"}

                manager._record_run_stats(
                    run_id="run-purchase-instock",
                    sync_type=SyncType.INCREMENTAL,
                    run_status=SyncStatus.SUCCESS,
                    total_records=0,
                    duration_seconds=1.0,
                    failed_forms=[],
                    results={
                        "采购入库单": {
                            "status": "success",
                            "fetched": 0,
                            "inserted": 0,
                            "duration_seconds": 0,
                        }
                    },
                )

                conn = sqlite3.connect(os.path.join("logs", "sync_stats.db"))
                try:
                    row = conn.execute(
                        "SELECT form_name, table_name FROM form_stats WHERE run_id=?",
                        ("run-purchase-instock",),
                    ).fetchone()
                finally:
                    conn.close()
            finally:
                os.chdir(previous_cwd)

        self.assertEqual(row, ("采购入库单", "STK_InStock"))


if __name__ == "__main__":
    unittest.main()
