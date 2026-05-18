from __future__ import annotations

import sys
import types
import unittest

_STUBBED_MODULES: list[str] = []


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


def _install_stub(module_name: str, module: object) -> None:
    if module_name in sys.modules:
        return

    sys.modules[module_name] = module
    _STUBBED_MODULES.append(module_name)


_install_stub("pyodbc", types.SimpleNamespace())
_install_stub("pymysql", types.SimpleNamespace(cursors=types.SimpleNamespace(DictCursor=object)))
_install_stub("dbutils", types.SimpleNamespace())
_install_stub("dbutils.pooled_db", types.SimpleNamespace(PooledDB=_DummyPool))
_install_stub("src.config.config_manager", types.SimpleNamespace(config_manager=_DummyConfigManager()))
_install_stub("src.core.performance_logging", types.SimpleNamespace(log_prepare_metrics=lambda *args, **kwargs: None))
_install_stub("src.core.sync_log_repository", types.SimpleNamespace(SyncLogRepository=_DummyRepository))
_install_stub("src.core.sync_run_repository", types.SimpleNamespace(SyncRunRepository=_DummyRepository))
_install_stub("src.core.upsert_engine_mysql", types.SimpleNamespace(UpsertEngineMySQL=_DummyUpsertEngine))
_install_stub("src.core.upsert_engine_sqlserver", types.SimpleNamespace(UpsertEngineSqlServer=_DummyUpsertEngine))
_install_stub("src.core.write_outcome", types.SimpleNamespace(WriteOutcome=object))
_install_stub("src.core.writers_registry", types.SimpleNamespace(WriterRegistry=_DummyRepository))

from src.core.mysql_manager import MySQLManager  # noqa: E402

sys.modules.pop("src.core.mysql_manager", None)
for _module_name in _STUBBED_MODULES:
    sys.modules.pop(_module_name, None)


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


if __name__ == "__main__":
    unittest.main()
