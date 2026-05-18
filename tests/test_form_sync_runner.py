from __future__ import annotations

import importlib
import logging
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

def _load_form_sync_runner_module():
    if "src.core.form_sync_runner" in sys.modules:
        return sys.modules["src.core.form_sync_runner"]

    requests_stub = types.ModuleType("requests")

    class _RequestException(Exception):
        pass

    class _Timeout(_RequestException):
        pass

    class _ConnectionError(_RequestException):
        pass

    class _Session:
        def __init__(self) -> None:
            self.verify = True
            self.headers = {}

        def post(self, *args, **kwargs):
            raise NotImplementedError

        def close(self) -> None:
            pass

    requests_stub.exceptions = types.SimpleNamespace(
        RequestException=_RequestException,
        Timeout=_Timeout,
        ConnectionError=_ConnectionError,
    )
    requests_stub.Session = _Session
    mysql_manager_stub = types.ModuleType("src.core.mysql_manager")

    class _MySQLManager:
        pass

    mysql_manager_stub.MySQLManager = _MySQLManager
    mysql_manager_stub.mysql_manager = SimpleNamespace(pool=None)
    with patch.dict(
        sys.modules,
        {
            "requests": requests_stub,
            "src.core.mysql_manager": mysql_manager_stub,
        },
    ):
        return importlib.import_module("src.core.form_sync_runner")


form_sync_runner = _load_form_sync_runner_module()
FormSyncRunner = form_sync_runner.FormSyncRunner
PARTIAL_STATUS = form_sync_runner.PARTIAL_STATUS
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

    def test_sync_single_form_marks_partial_when_rows_fail_to_write(self) -> None:
        owner = SimpleNamespace(
            DEDUPLICATION_FORMS=set(),
            INSERT_METHOD_MAP={"销售订单": "insert_sales_orders"},
            table_mapping={"销售订单": "saleorder"},
            _notify_progress=Mock(),
            _checkpoint_manager=SimpleNamespace(load_checkpoint=Mock(return_value=None), clear_checkpoint=Mock()),
        )
        filter_builder = SimpleNamespace(build_filter_string=Mock(return_value=""))
        fake_db = SimpleNamespace(log_sync_operation=Mock(), disconnect=Mock())
        runner = FormSyncRunner(owner, filter_builder, logger_=logging.getLogger("test.form_sync_runner"))

        with (
            patch.object(form_sync_runner, "create_shared_db_manager", return_value=fake_db),
            patch.object(form_sync_runner, "emit_audit_log"),
            patch.object(form_sync_runner, "config_manager") as mock_config_manager,
        ):
            mock_config_manager.get_form_queries.return_value = {"销售订单": {"FieldKeys": "FID,FBillNo"}}
            runner.query_kingdee_data = Mock(
                side_effect=lambda *args, **kwargs: kwargs["page_callback"]([{"FID": 1}, {"FID": 2}]) or []
            )
            runner.insert_database_data = Mock(return_value=WriteOutcome(inserted=1))

            result = runner.sync_single_form("销售订单", "full")

        self.assertEqual(result["status"], PARTIAL_STATUS)
        self.assertEqual(result["fetched"], 2)
        self.assertEqual(result["inserted"], 1)
        self.assertEqual(result["failed"], 1)
        fake_db.log_sync_operation.assert_called_once()
        self.assertEqual(result["status"], PARTIAL_STATUS)

    def test_sync_single_form_emits_write_failure_audit_and_metrics(self) -> None:
        owner = SimpleNamespace(
            DEDUPLICATION_FORMS=set(),
            INSERT_METHOD_MAP={"销售订单": "insert_sales_orders"},
            table_mapping={"销售订单": "saleorder"},
            _notify_progress=Mock(),
            _checkpoint_manager=SimpleNamespace(load_checkpoint=Mock(return_value=None), clear_checkpoint=Mock()),
        )
        filter_builder = SimpleNamespace(build_filter_string=Mock(return_value=""))
        fake_db = SimpleNamespace(log_sync_operation=Mock(), disconnect=Mock())
        runner = FormSyncRunner(owner, filter_builder, logger_=logging.getLogger("test.form_sync_runner"))

        with (
            patch.object(form_sync_runner, "create_shared_db_manager", return_value=fake_db),
            patch.object(form_sync_runner, "emit_audit_log") as mock_audit,
            patch.object(form_sync_runner, "metrics_collector", create=True) as mock_metrics,
            patch.object(form_sync_runner, "config_manager") as mock_config_manager,
        ):
            mock_config_manager.get_form_queries.return_value = {"销售订单": {"FieldKeys": "FID,FBillNo"}}
            runner.query_kingdee_data = Mock(
                side_effect=lambda *args, **kwargs: kwargs["page_callback"]([{"FID": 1, "FBillNo": "SO001"}]) or []
            )
            runner.insert_database_data = Mock(
                return_value=WriteOutcome(inserted=0, failed=1),
            )

            result = runner.sync_single_form("销售订单", "full")

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["failure_categories"]["sql_error"], 1)
        self.assertIn("failure_details", result)
        mock_metrics.record_write_outcome.assert_called_once()
        self.assertTrue(any(call.kwargs.get("event") == "write_failure_detail" for call in mock_audit.mock_calls))


if __name__ == "__main__":
    unittest.main()
