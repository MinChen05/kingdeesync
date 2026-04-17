from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta

from src.core.sync_run_repository import SyncRunRepository


class FakeCursor:
    def __init__(self) -> None:
        self.executed: list[tuple[str, object]] = []
        self.rowcount = 0
        self._rowcount_sequence: list[int] = []

    def execute(self, sql: str, params=None) -> None:
        self.executed.append((sql, params))
        if self._rowcount_sequence and sql.lstrip().upper().startswith("UPDATE"):
            self.rowcount = self._rowcount_sequence.pop(0)

    def fetchone(self):
        return None


class FakeManager:
    def __init__(self, db_type: str = "mysql") -> None:
        self.db_type = db_type
        self.connection = object()
        self.cursor = FakeCursor()
        self._table_exists_values = [True]

    def connect(self) -> bool:
        self.connection = object()
        return True

    def table_exists(self, table_name: str) -> bool:
        if self._table_exists_values:
            return self._table_exists_values.pop(0)
        return True


class SyncRunRepositoryTests(unittest.TestCase):
    def test_start_run_inserts_initial_row(self) -> None:
        sales_order = "\u9500\u552e\u8ba2\u5355"
        manager = FakeManager("mysql")
        repository = SyncRunRepository(manager)

        ok = repository.start_run(
            run_id="run-1",
            sync_type="incremental",
            forms=[sales_order],
            start_time=datetime(2026, 4, 17, 12, 0, 0),
        )

        self.assertTrue(ok)
        sql, params = manager.cursor.executed[-1]
        self.assertIn("INSERT INTO sync_runs", sql)
        self.assertEqual(params[0], "run-1")
        self.assertEqual(params[1], "incremental")
        self.assertEqual(params[2], sales_order)
        self.assertEqual(params[3], 1)
        self.assertEqual(params[4:7], (0, 0, 0))
        self.assertEqual(params[7], "running")

    def test_finish_run_inserts_snapshot_when_update_misses(self) -> None:
        sales_order = "\u9500\u552e\u8ba2\u5355"
        manager = FakeManager("mysql")
        manager.cursor._rowcount_sequence = [0]
        repository = SyncRunRepository(manager)

        start_time = datetime(2026, 4, 17, 12, 0, 0)
        end_time = start_time + timedelta(seconds=12)

        ok = repository.finish_run(
            run_id="run-2",
            sync_type="full",
            forms=[sales_order],
            total_records=10,
            success_count=9,
            failure_count=1,
            status="partial",
            message="done",
            start_time=start_time,
            end_time=end_time,
            failed_forms=[sales_order],
            details={"records": 10},
        )

        self.assertTrue(ok)
        self.assertEqual(len(manager.cursor.executed), 2)
        update_sql, _ = manager.cursor.executed[0]
        insert_sql, insert_params = manager.cursor.executed[1]
        self.assertIn("UPDATE sync_runs", update_sql)
        self.assertIn("INSERT INTO sync_runs", insert_sql)
        self.assertEqual(insert_params[0], "run-2")
        self.assertEqual(insert_params[4], 10)
        self.assertEqual(insert_params[5], 9)
        self.assertEqual(insert_params[6], 1)
        self.assertEqual(insert_params[7], "partial")
        self.assertEqual(insert_params[9], sales_order)
        self.assertEqual(json.loads(insert_params[10]), {"records": 10})
        self.assertAlmostEqual(insert_params[13], 12.0)


if __name__ == "__main__":
    unittest.main()
