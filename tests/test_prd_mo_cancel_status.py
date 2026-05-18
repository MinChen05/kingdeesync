from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock


class _DummyUpsertEngine:
    def __init__(self, *args, **kwargs):
        pass


class _DummyRepository:
    def __init__(self, *args, **kwargs):
        pass

    def reset(self):
        return None

    def missing_methods(self, *args, **kwargs):
        return []


class _DummyPool:
    def __init__(self, *args, **kwargs):
        pass


class _DummyConfigManager:
    def get_db_config(self):
        return {
            "type": "mysql",
            "mysql": {
                "host": "localhost",
                "user": "test",
                "password": "",
                "database": "test",
            },
        }

    def get_insert_method_map(self):
        return {}


@contextmanager
def _temporary_modules(stubs: dict[str, object]):
    sentinel = object()
    original: dict[str, object] = {}
    try:
        for module_name, module in stubs.items():
            original[module_name] = sys.modules.get(module_name, sentinel)
            sys.modules[module_name] = module
        yield
    finally:
        for module_name, previous in original.items():
            if previous is sentinel:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = previous


def _load_mysql_manager_class():
    stubs = {
        "pyodbc": types.SimpleNamespace(),
        "pymysql": types.SimpleNamespace(cursors=types.SimpleNamespace(DictCursor=object)),
        "dbutils": types.SimpleNamespace(),
        "dbutils.pooled_db": types.SimpleNamespace(PooledDB=_DummyPool),
        "src.config.config_manager": types.SimpleNamespace(config_manager=_DummyConfigManager()),
        "src.core.performance_logging": types.SimpleNamespace(log_prepare_metrics=lambda *args, **kwargs: None),
        "src.core.sync_log_repository": types.SimpleNamespace(SyncLogRepository=_DummyRepository),
        "src.core.sync_run_repository": types.SimpleNamespace(SyncRunRepository=_DummyRepository),
        "src.core.upsert_engine_mysql": types.SimpleNamespace(UpsertEngineMySQL=_DummyUpsertEngine),
        "src.core.upsert_engine_sqlserver": types.SimpleNamespace(UpsertEngineSqlServer=_DummyUpsertEngine),
        "src.core.write_outcome": types.SimpleNamespace(WriteOutcome=object),
        "src.core.writers_registry": types.SimpleNamespace(WriterRegistry=_DummyRepository),
    }
    module_path = Path(__file__).resolve().parents[1] / "src" / "core" / "mysql_manager.py"
    module_name = "_prd_mo_cancel_status_mysql_manager"

    with _temporary_modules(stubs):
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Unable to load src.core.mysql_manager for tests")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        finally:
            sys.modules.pop(module_name, None)

    return module.MySQLManager


MySQLManager = _load_mysql_manager_class()


class PrdMoCancelStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = MySQLManager.__new__(MySQLManager)

    def test_prepare_production_order_data_defaults_cancel_status_to_empty_string(self) -> None:
        prepared = self.manager._prepare_production_order_data(
            {
                "FID": 1,
                "FBILLNO": "MO20260518001",
                "FBILLTYPE.FNAME": "生产订单",
                "FDATE": "2026-05-18 08:00:00",
                "FPRDORGID": 100,
                "FWORKSHOPID": 200,
                "FDocumentStatus": "A",
                "FCREATEDATE": "2026-05-18 08:00:00",
                "FMODIFYDATE": "2026-05-18 09:00:00",
                "FCANCELSTATUS": None,
            }
        )

        self.assertIsNotNone(prepared)
        self.assertEqual(prepared[-1], "")

    def test_prepare_production_order_data_keeps_non_empty_cancel_status(self) -> None:
        prepared = self.manager._prepare_production_order_data(
            {
                "FID": 2,
                "FBILLNO": "MO20260518002",
                "FBILLTYPE.FNAME": "生产订单",
                "FDATE": "2026-05-18 08:00:00",
                "FPRDORGID": 100,
                "FWORKSHOPID": 200,
                "FDocumentStatus": "A",
                "FCREATEDATE": "2026-05-18 08:00:00",
                "FMODIFYDATE": "2026-05-18 09:00:00",
                "FCANCELSTATUS": "B",
            }
        )

        self.assertIsNotNone(prepared)
        self.assertEqual(prepared[-1], "B")

    def test_prepare_production_order_data_defaults_cancel_status_to_empty_string_for_new_field_list(self) -> None:
        prepared = self.manager._prepare_production_order_data(
            [
                1,
                "MO20260518003",
                "生产订单",
                "2026-05-18 08:00:00",
                100,
                200,
                "A",
                "2026-05-18 08:00:00",
                "2026-05-18 09:00:00",
                None,
            ]
        )

        self.assertIsNotNone(prepared)
        self.assertEqual(prepared[-1], "")

    def test_prepare_production_order_data_defaults_cancel_status_to_empty_string_for_legacy_field_list(self) -> None:
        prepared = self.manager._prepare_production_order_data(
            [
                1,
                None,
                None,
                "MO20260518004",
                "生产订单",
                None,
                None,
                None,
                "2026-05-18 08:00:00",
                None,
                None,
                None,
                None,
                None,
                "2026-05-18 09:00:00",
                None,
            ]
        )

        self.assertIsNotNone(prepared)
        self.assertEqual(prepared[-1], "")

    def test_prepare_production_order_data_uses_field_mapping_resolver_for_cancel_status(self) -> None:
        self.manager.field_mapping_resolver = Mock()
        self.manager.field_mapping_resolver.resolve_field.return_value = "B"

        prepared = self.manager._prepare_production_order_data(
            {
                "FID": 3,
                "FBILLNO": "MO20260518005",
                "FBILLTYPE.FNAME": "生产订单",
                "FDATE": "2026-05-18 08:00:00",
                "FPRDORGID": 100,
                "FWORKSHOPID": 200,
                "FDocumentStatus": "A",
                "FCREATEDATE": "2026-05-18 08:00:00",
                "FMODIFYDATE": "2026-05-18 09:00:00",
                "FCANCELSTATUS": "B",
            }
        )

        self.assertIsNotNone(prepared)
        self.manager.field_mapping_resolver.resolve_field.assert_any_call(
            "prd_mo",
            "FCANCELSTATUS",
            unittest.mock.ANY,
        )
        self.assertEqual(prepared[-1], "B")


if __name__ == "__main__":
    unittest.main()
