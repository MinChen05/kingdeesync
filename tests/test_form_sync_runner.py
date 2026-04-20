from __future__ import annotations

import logging
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from src.core.form_sync_runner import FormSyncRunner
from src.core.write_outcome import WriteOutcome


class FormSyncRunnerOutcomeTests(unittest.TestCase):
    def test_build_write_summary_separates_invalid_deduped_and_failed(self) -> None:
        owner = SimpleNamespace(DEDUPLICATION_FORMS={"生产入库单"})
        runner = FormSyncRunner(owner, SimpleNamespace(), logger_=logging.getLogger("test.form_sync_runner"))

        summary = runner._build_write_summary(
            "生产入库单",
            fetched=10,
            outcome=WriteOutcome(inserted=6, invalid=2, deduped=1),
        )

        self.assertEqual(
            summary,
            {
                "fetched": 10,
                "inserted": 6,
                "invalid": 2,
                "deduped": 1,
                "failed": 1,
            },
        )

    def test_insert_database_data_prefers_execute_writer_with_outcome(self) -> None:
        owner = SimpleNamespace(
            DEDUPLICATION_FORMS={"生产入库单"},
            INSERT_METHOD_MAP={"生产入库单": "insert_prd_instock"},
        )
        manager = SimpleNamespace(execute_writer_with_outcome=Mock(return_value=WriteOutcome(inserted=3)))
        runner = FormSyncRunner(owner, SimpleNamespace(), logger_=logging.getLogger("test.form_sync_runner"))

        outcome = runner.insert_database_data("生产入库单", [{"FID": 1}], db_manager=manager)

        self.assertEqual(outcome, WriteOutcome(inserted=3))
        manager.execute_writer_with_outcome.assert_called_once_with("insert_prd_instock", [{"FID": 1}])


if __name__ == "__main__":
    unittest.main()
