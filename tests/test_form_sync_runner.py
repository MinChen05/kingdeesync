from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import importlib
import logging
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

@contextmanager
def _load_form_sync_runner_module():
    original_modules = {
        name: sys.modules.get(name)
        for name in ("src.core", "src.config", "src.core.form_sync_runner", "requests", "src.core.mysql_manager", "src.config.config_manager")
    }
    core_pkg = original_modules["src.core"]
    config_pkg = original_modules["src.config"]
    core_pkg_attr_present = bool(core_pkg and hasattr(core_pkg, "form_sync_runner"))
    core_pkg_attr_value = getattr(core_pkg, "form_sync_runner", None) if core_pkg_attr_present else None
    config_pkg_attr_present = bool(config_pkg and hasattr(config_pkg, "config_manager"))
    config_pkg_attr_value = getattr(config_pkg, "config_manager", None) if config_pkg_attr_present else None
    for name in original_modules:
        sys.modules.pop(name, None)

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
    config_manager_stub = types.ModuleType("src.config.config_manager")

    config_manager_stub.config_manager = SimpleNamespace(
        get_form_queries=lambda: {},
        get_db_config=lambda: {"type": "mysql", "mysql": {}, "sqlserver": {}},
        get_kingdee_config=lambda: {},
        get_insert_method_map=lambda: {},
        get_increment_field=lambda _key: None,
        set_increment_field=lambda _key, _value: None,
    )

    class _MySQLManager:
        pass

    mysql_manager_stub.MySQLManager = _MySQLManager
    mysql_manager_stub.mysql_manager = SimpleNamespace(pool=None)
    try:
        with patch.dict(
            sys.modules,
            {
                "requests": requests_stub,
                "src.core.mysql_manager": mysql_manager_stub,
                "src.config.config_manager": config_manager_stub,
            },
        ):
            yield importlib.import_module("src.core.form_sync_runner")
    finally:
        live_core_pkg = sys.modules.get("src.core")
        live_config_pkg = sys.modules.get("src.config")
        sys.modules.pop("src.core.form_sync_runner", None)
        for pkg in (live_core_pkg, core_pkg):
            if pkg is None:
                continue
            if core_pkg_attr_present:
                setattr(pkg, "form_sync_runner", core_pkg_attr_value)
            elif hasattr(pkg, "form_sync_runner"):
                delattr(pkg, "form_sync_runner")
        for pkg in (live_config_pkg, config_pkg):
            if pkg is None:
                continue
            if config_pkg_attr_present:
                setattr(pkg, "config_manager", config_pkg_attr_value)
            elif hasattr(pkg, "config_manager"):
                delattr(pkg, "config_manager")
        for name, module in original_modules.items():
            if module is not None:
                sys.modules[name] = module
            else:
                sys.modules.pop(name, None)
from src.core.write_outcome import WriteOutcome
from src.core.metrics import MetricsCollector


class FormSyncRunnerOutcomeTests(unittest.TestCase):
    def test_package_attr_cleanup_does_not_leave_detached_form_sync_runner(self) -> None:
        core_pkg = sys.modules.get("src.core")
        if core_pkg is not None and hasattr(core_pkg, "form_sync_runner"):
            delattr(core_pkg, "form_sync_runner")

        with _load_form_sync_runner_module():
            pass

        core_pkg = sys.modules.get("src.core")
        self.assertTrue(core_pkg is None or not hasattr(core_pkg, "form_sync_runner"))

    def test_build_write_summary_separates_invalid_deduped_and_failed(self) -> None:
        with _load_form_sync_runner_module() as form_sync_runner:
            runner_cls = form_sync_runner.FormSyncRunner
            owner = SimpleNamespace(DEDUPLICATION_FORMS={"生产入库单"})
            runner = runner_cls(owner, SimpleNamespace(), logger_=logging.getLogger("test.form_sync_runner"))

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
        with _load_form_sync_runner_module() as form_sync_runner:
            runner_cls = form_sync_runner.FormSyncRunner
            owner = SimpleNamespace(
                DEDUPLICATION_FORMS={"生产入库单"},
                INSERT_METHOD_MAP={"生产入库单": "insert_prd_instock"},
            )
            manager = SimpleNamespace(execute_writer_with_outcome=Mock(return_value=WriteOutcome(inserted=3)))
            runner = runner_cls(owner, SimpleNamespace(), logger_=logging.getLogger("test.form_sync_runner"))

            outcome = runner.insert_database_data("生产入库单", [{"FID": 1}], db_manager=manager)

        self.assertEqual(outcome, WriteOutcome(inserted=3))
        manager.execute_writer_with_outcome.assert_called_once_with("insert_prd_instock", [{"FID": 1}])

    def test_sync_single_form_marks_partial_when_rows_fail_to_write(self) -> None:
        with _load_form_sync_runner_module() as form_sync_runner:
            runner_cls = form_sync_runner.FormSyncRunner
            partial_status = form_sync_runner.PARTIAL_STATUS
            owner = SimpleNamespace(
                DEDUPLICATION_FORMS=set(),
                INSERT_METHOD_MAP={"销售订单": "insert_sales_orders"},
                table_mapping={"销售订单": "saleorder"},
                _notify_progress=Mock(),
                _checkpoint_manager=SimpleNamespace(load_checkpoint=Mock(return_value=None), clear_checkpoint=Mock()),
            )
            filter_builder = SimpleNamespace(build_filter_string=Mock(return_value=""))
            fake_db = SimpleNamespace(disconnect=Mock())
            runner = runner_cls(owner, filter_builder, logger_=logging.getLogger("test.form_sync_runner"))

            captured_sync_log: dict[str, object] = {}

            def log_sync_operation(sync_type, table_name, operation, record_count, status, *args, **kwargs):
                captured_sync_log["status"] = status

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
                fake_db.log_sync_operation = Mock(side_effect=log_sync_operation)

                result = runner.sync_single_form("销售订单", "full")

        self.assertEqual(result["status"], partial_status)
        self.assertEqual(result["fetched"], 2)
        self.assertEqual(result["inserted"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(captured_sync_log["status"], partial_status)

    def test_sync_single_form_normalizes_legacy_outcome_before_metrics(self) -> None:
        with _load_form_sync_runner_module() as form_sync_runner:
            runner_cls = form_sync_runner.FormSyncRunner
            owner = SimpleNamespace(
                DEDUPLICATION_FORMS=set(),
                INSERT_METHOD_MAP={"销售订单": "insert_sales_orders"},
                table_mapping={"销售订单": "saleorder"},
                _notify_progress=Mock(),
                _checkpoint_manager=SimpleNamespace(load_checkpoint=Mock(return_value=None), clear_checkpoint=Mock()),
            )
            filter_builder = SimpleNamespace(build_filter_string=Mock(return_value=""))
            fake_db = SimpleNamespace(disconnect=Mock(), log_sync_operation=Mock())
            runner = runner_cls(owner, filter_builder, logger_=logging.getLogger("test.form_sync_runner"))

            with (
                patch.object(form_sync_runner, "create_shared_db_manager", return_value=fake_db),
                patch.object(form_sync_runner, "emit_audit_log"),
                patch.object(form_sync_runner, "metrics_collector", create=True) as mock_metrics,
                patch.object(form_sync_runner, "config_manager") as mock_config_manager,
            ):
                mock_config_manager.get_form_queries.return_value = {"销售订单": {"FieldKeys": "FID,FBillNo"}}
                runner.query_kingdee_data = Mock(
                    side_effect=lambda *args, **kwargs: kwargs["page_callback"](
                        [{"FID": 1, "FBillNo": "SO001"}, {"FID": 2, "FBillNo": "SO002"}]
                    )
                    or []
                )
                runner.insert_database_data = Mock(return_value=WriteOutcome(inserted=1))

                result = runner.sync_single_form("销售订单", "full")

        recorded_outcome = mock_metrics.record_write_outcome.call_args.args[2]
        self.assertEqual(result["failed"], 1)
        self.assertEqual(sum(result["failure_categories"].values()), 1)
        self.assertEqual(recorded_outcome.failed, 1)
        self.assertTrue(recorded_outcome.failure_details)
        self.assertEqual(recorded_outcome.failure_details[0].category, "sql_error")

    def test_sync_single_form_emits_write_failure_audit_and_metrics(self) -> None:
        with _load_form_sync_runner_module() as form_sync_runner:
            runner_cls = form_sync_runner.FormSyncRunner
            owner = SimpleNamespace(
                DEDUPLICATION_FORMS=set(),
                INSERT_METHOD_MAP={"销售订单": "insert_sales_orders"},
                table_mapping={"销售订单": "saleorder"},
                _notify_progress=Mock(),
                _checkpoint_manager=SimpleNamespace(load_checkpoint=Mock(return_value=None), clear_checkpoint=Mock()),
            )
            filter_builder = SimpleNamespace(build_filter_string=Mock(return_value=""))
            fake_db = SimpleNamespace(disconnect=Mock())
            runner = runner_cls(owner, filter_builder, logger_=logging.getLogger("test.form_sync_runner"))

            captured_sync_log: dict[str, object] = {}

            def log_sync_operation(sync_type, table_name, operation, record_count, status, *args, **kwargs):
                captured_sync_log["status"] = status

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
                fake_db.log_sync_operation = Mock(side_effect=log_sync_operation)

                result = runner.sync_single_form("销售订单", "full")

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["failed"], 1)
        self.assertIn("failure_categories", result)
        self.assertEqual(sum(result["failure_categories"].values()), 1)
        self.assertEqual(captured_sync_log["status"], "failed")
        mock_metrics.record_write_outcome.assert_called_once()
        recorded_outcome = mock_metrics.record_write_outcome.call_args.args[2]
        self.assertTrue(recorded_outcome.failure_details)
        self.assertEqual(recorded_outcome.failure_details[0].category, "sql_error")
        self.assertTrue(any(len(call.args) >= 3 and call.args[2] == "write_failure_detail" for call in mock_audit.mock_calls))

    def test_sync_single_form_query_failure_preserves_accumulated_failure_telemetry(self) -> None:
        with _load_form_sync_runner_module() as form_sync_runner:
            runner_cls = form_sync_runner.FormSyncRunner
            owner = SimpleNamespace(
                DEDUPLICATION_FORMS=set(),
                INSERT_METHOD_MAP={"销售订单": "insert_sales_orders"},
                table_mapping={"销售订单": "saleorder"},
                _notify_progress=Mock(),
                _checkpoint_manager=SimpleNamespace(load_checkpoint=Mock(return_value=None), clear_checkpoint=Mock()),
            )
            filter_builder = SimpleNamespace(build_filter_string=Mock(return_value=""))
            fake_db = SimpleNamespace(disconnect=Mock(), log_sync_operation=Mock())
            runner = runner_cls(owner, filter_builder, logger_=logging.getLogger("test.form_sync_runner"))

            attempts = {"count": 0}

            def query_side_effect(*args, **kwargs):
                attempts["count"] += 1
                if attempts["count"] == 1:
                    kwargs["page_callback"]([{"FID": 1, "FBillNo": "SO001"}, {"FID": 2, "FBillNo": "SO002"}])
                return None

            with (
                patch.object(form_sync_runner, "create_shared_db_manager", return_value=fake_db),
                patch.object(form_sync_runner, "emit_audit_log"),
                patch.object(form_sync_runner, "metrics_collector", create=True),
                patch.object(form_sync_runner, "config_manager") as mock_config_manager,
                patch.object(form_sync_runner.time, "sleep", return_value=None),
            ):
                mock_config_manager.get_form_queries.return_value = {"销售订单": {"FieldKeys": "FID,FBillNo"}}
                runner.query_kingdee_data = Mock(side_effect=query_side_effect)
                runner.insert_database_data = Mock(return_value=WriteOutcome(inserted=1))

                result = runner.sync_single_form("销售订单", "full")

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_type"], "query_error")
        self.assertEqual(sum(result["failure_categories"].values()), 1)
        self.assertTrue(result["failure_details"])
        self.assertEqual(result["failure_details"][0]["category"], "sql_error")

    def test_metrics_collector_export_run_snapshot_is_scoped_by_run_id(self) -> None:
        collector = MetricsCollector()
        form_name = "销售订单"

        collector.start_sync("run-a", form_name)
        collector.record_write_outcome("run-a", form_name, WriteOutcome(inserted=3), 0.1)
        collector.end_sync("run-a", form_name, success=True)

        collector.start_sync("run-b", form_name)
        collector.record_write_outcome("run-b", form_name, WriteOutcome(inserted=7), 0.2)
        collector.end_sync("run-b", form_name, success=True)

        snapshot_a = collector.export_run_snapshot("run-a", [form_name])
        snapshot_b = collector.export_run_snapshot("run-b", [form_name])

        self.assertEqual(snapshot_a[form_name]["records_inserted"], 3)
        self.assertEqual(snapshot_b[form_name]["records_inserted"], 7)

    def test_metrics_collector_export_run_snapshot_does_not_leak_other_run_metrics(self) -> None:
        collector = MetricsCollector()
        form_name = "销售订单"

        collector.start_sync("run-a", form_name)
        collector.record_write_outcome("run-a", form_name, WriteOutcome(inserted=5), 0.1)
        collector.end_sync("run-a", form_name, success=True)

        snapshot = collector.export_run_snapshot("run-empty", [form_name])

        self.assertEqual(snapshot, {})

    @patch("src.core.data_sync.mysql_manager.finish_sync_run")
    @patch("src.core.data_sync.metrics_collector")
    @patch("src.core.data_sync.config_manager.get_sync_config", return_value={})
    def test_z_finalize_run_writes_metrics_snapshot_into_task_details(
        self,
        _mock_sync_config: Mock,
        mock_metrics_collector: Mock,
        mock_finish_sync_run: Mock,
    ) -> None:
        from src.core.data_sync import DataSyncManager, SyncStatus, SyncType

        manager = DataSyncManager()
        start_time = datetime(2026, 5, 18, 10, 0, 0)
        end_time = datetime(2026, 5, 18, 10, 0, 3)
        results = {
            "销售订单": {
                "status": "success",
                "record_count": 3,
            }
        }
        metrics_snapshot = {
            "销售订单": {
                "records_inserted": 3,
                "records_failed": 0,
            }
        }
        mock_metrics_collector.export_run_snapshot.return_value = metrics_snapshot

        manager._finalize_run(
            run_id="run-1",
            sync_type=SyncType.INCREMENTAL,
            requested_forms=["销售订单"],
            results=results,
            total_records=3,
            failed_tables=[],
            run_status=SyncStatus.SUCCESS,
            message="所有表同步成功，共同步 3 条记录",
            start_time=start_time,
            end_time=end_time,
        )

        finish_kwargs = mock_finish_sync_run.call_args.kwargs
        self.assertEqual(
            finish_kwargs["details"],
            {
                "results": results,
                "metrics": metrics_snapshot,
                "failed_forms": [],
            },
        )
        mock_metrics_collector.export_run_snapshot.assert_called_once_with("run-1", ["销售订单"])

    @patch("src.core.data_sync.mysql_manager.finish_sync_run")
    @patch("src.core.data_sync.metrics_collector")
    @patch("src.core.data_sync.config_manager.get_sync_config", return_value={})
    def test_z_finalize_run_does_not_leak_stale_metrics_when_results_are_empty(
        self,
        _mock_sync_config: Mock,
        mock_metrics_collector: Mock,
        mock_finish_sync_run: Mock,
    ) -> None:
        from src.core.data_sync import DataSyncManager, SyncStatus, SyncType

        manager = DataSyncManager()
        start_time = datetime(2026, 5, 18, 10, 0, 0)
        end_time = datetime(2026, 5, 18, 10, 0, 1)
        mock_metrics_collector.export_run_snapshot.side_effect = (
            lambda run_id, form_names: {} if not form_names else {"销售订单": {"records_inserted": 99}}
        )

        manager._finalize_run(
            run_id="run-2",
            sync_type=SyncType.INCREMENTAL,
            requested_forms=["销售订单"],
            results={},
            total_records=0,
            failed_tables=[],
            run_status=SyncStatus.FAILED,
            message="连接检查失败",
            start_time=start_time,
            end_time=end_time,
        )

        finish_kwargs = mock_finish_sync_run.call_args.kwargs
        mock_metrics_collector.export_run_snapshot.assert_called_once_with("run-2", [])
        self.assertEqual(finish_kwargs["details"]["metrics"], {})


if __name__ == "__main__":
    unittest.main()
