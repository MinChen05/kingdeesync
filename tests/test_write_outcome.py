from __future__ import annotations

import unittest
from types import SimpleNamespace

from src.core.mysql_manager import MySQLManager
from src.core.write_outcome import WriteOutcome


class WriteOutcomeTests(unittest.TestCase):
    def test_from_insert_count_clamps_negative_values(self) -> None:
        self.assertEqual(WriteOutcome.from_insert_count(-3), WriteOutcome(inserted=0))


class ExecuteWriterOutcomeTests(unittest.TestCase):
    def test_execute_writer_with_outcome_wraps_legacy_insert_count(self) -> None:
        manager = MySQLManager.__new__(MySQLManager)
        manager.writer_registry = SimpleNamespace(execute=lambda *_args, **_kwargs: 3)
        manager._last_write_outcome = WriteOutcome()

        outcome = MySQLManager.execute_writer_with_outcome(manager, "insert_prd_instock", [])

        self.assertEqual(outcome, WriteOutcome(inserted=3))

    def test_execute_writer_keeps_legacy_insert_count_contract(self) -> None:
        manager = MySQLManager.__new__(MySQLManager)
        manager.writer_registry = SimpleNamespace(execute=lambda *_args, **_kwargs: 5)
        manager._last_write_outcome = WriteOutcome()

        inserted = MySQLManager.execute_writer(manager, "insert_prd_instock", [])

        self.assertEqual(inserted, 5)


if __name__ == "__main__":
    unittest.main()
