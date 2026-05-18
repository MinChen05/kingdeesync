from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock

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
    module_name = "src.core.mysql_manager"
    sentinel = object()
    previous_module = sys.modules.get(module_name, sentinel)

    with _temporary_modules(stubs):
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Unable to load src.core.mysql_manager for tests")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        finally:
            if previous_module is sentinel:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = previous_module

    return module.MySQLManager


def _load_insert_eng_bom_child():
    stubs = {
        "src.core.mysql_manager": types.SimpleNamespace(MySQLManager=object),
        "src.config.config_manager": types.SimpleNamespace(config_manager=_DummyConfigManager()),
    }
    module_path = Path(__file__).resolve().parents[1] / "src" / "core" / "masterdata_writer.py"
    module_name = "_eng_bomchild_masterdata_writer"
    sentinel = object()
    previous_module = sys.modules.get(module_name, sentinel)

    with _temporary_modules(stubs):
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Unable to load src.core.masterdata_writer for tests")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        finally:
            if previous_module is sentinel:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = previous_module

    return module.insert_eng_bom_child


MySQLManager = _load_mysql_manager_class()
insert_eng_bom_child = _load_insert_eng_bom_child()


class FakeCursor:
    def __init__(
        self,
        fetchone_results: list[object],
        execute_side_effects: list[object] | None = None,
    ) -> None:
        self.fetchone_results = list(fetchone_results)
        self.execute_side_effects = list(execute_side_effects or [])
        self.execute_calls: list[tuple[str, object]] = []

    def execute(self, sql: str, params=None) -> None:
        if self.execute_side_effects:
            effect = self.execute_side_effects.pop(0)
            if effect is not None:
                raise effect
        self.execute_calls.append((sql, params))

    def fetchone(self):
        if self.fetchone_results:
            return self.fetchone_results.pop(0)
        return None


class FakeConnection:
    def __init__(self) -> None:
        self.commit_count = 0

    def commit(self) -> None:
        self.commit_count += 1


class FakeEngBomChildWriteManager(MySQLManager):
    def __init__(self) -> None:
        pass


class EngBomChildFieldMappingTests(unittest.TestCase):
    def _build_manager(self) -> MySQLManager:
        manager = MySQLManager.__new__(MySQLManager)
        manager.connection = None
        manager.cursor = None
        manager.db_type = "sqlserver"
        return manager

    def test_prepare_eng_bom_child_data_reads_child_number_from_dict_payload(self) -> None:
        manager = self._build_manager()

        prepared = manager._prepare_eng_bom_child_data(
            {
                "FID": 101,
                "FTreeEntity_FENTRYID": 202,
                "FTreeEntity_FSEQ": 3,
                "FMATERIALID": "MAT-PARENT",
                "FMATERIALIDCHILD.FNUMBER": "MAT-CHILD-001",
                "FMATERIALIDCHILD.FNAME": "Child Material 001",
                "FNUMERATOR": "2",
                "FDENOMINATOR": "1",
                "FISSUETYPE": "1",
                "FBACKFLUSHTYPE": "2",
                "FSUPPLYORG": 171190,
                "FSTOCKID": 88,
                "FENTRYROWID": "ROW-1",
                "FREPLACEGROUP": 0,
                "FQTY": "6.5",
                "FACTUALQTY": "6.0",
                "FMASTERID": 303,
                "FMATERIALTYPE": "1",
                "FMODIFYDATE": "2026-04-23 09:30:00",
            }
        )

        self.assertEqual(prepared[4], "MAT-CHILD-001")
        self.assertEqual(prepared[5], "Child Material 001")
        self.assertEqual(prepared[17], "1")

    def test_prepare_eng_bom_child_data_reads_child_number_from_list_payload(self) -> None:
        manager = self._build_manager()

        prepared = manager._prepare_eng_bom_child_data(
            [
                101,
                202,
                3,
                "MAT-PARENT",
                "MAT-CHILD-002",
                "Child Material 002",
                "2",
                "1",
                "1",
                "2",
                171190,
                88,
                "ROW-2",
                0,
                "7.5",
                "7.0",
                303,
                "2",
                "2026-04-23 10:00:00",
            ]
        )

        self.assertEqual(prepared[4], "MAT-CHILD-002")
        self.assertEqual(prepared[5], "Child Material 002")
        self.assertEqual(prepared[17], "2")

    def test_prepare_eng_bom_child_data_reads_child_number_from_fchildnumber_fallback(self) -> None:
        manager = self._build_manager()

        prepared = manager._prepare_eng_bom_child_data(
            {
                "FID": 101,
                "FTreeEntity_FENTRYID": 202,
                "FTreeEntity_FSEQ": 3,
                "FMATERIALID": "MAT-PARENT",
                "FCHILDNUMBER": "MAT-CHILD-003",
                "FCHILDNAME": "Child Material 003",
                "FNUMERATOR": "2",
                "FDENOMINATOR": "1",
                "FMATERIALTYPE": "3",
            }
        )

        self.assertEqual(prepared[4], "MAT-CHILD-003")
        self.assertEqual(prepared[5], "Child Material 003")
        self.assertEqual(prepared[17], "3")

    def test_prepare_eng_bom_child_data_reads_child_number_from_fnumber_case_variant_fallback(self) -> None:
        manager = self._build_manager()

        prepared = manager._prepare_eng_bom_child_data(
            {
                "FID": 101,
                "FTreeEntity_FENTRYID": 202,
                "FTreeEntity_FSEQ": 3,
                "FMATERIALID": "MAT-PARENT",
                "FMATERIALIDCHILD.FNumber": "MAT-CHILD-004",
                "FNUMERATOR": "2",
                "FDENOMINATOR": "1",
                "FMATERIALTYPE": "4",
            }
        )

        self.assertEqual(prepared[4], "MAT-CHILD-004")
        self.assertEqual(prepared[17], "4")

    def test_prepare_eng_bom_child_data_uses_field_mapping_resolver_for_child_fields(self) -> None:
        manager = self._build_manager()
        manager.field_mapping_resolver = Mock()
        manager.field_mapping_resolver.resolve_field.side_effect = [
            "RESOLVED-CHILD-006",
            "RESOLVED-CHILD-NAME-006",
        ]

        prepared = manager._prepare_eng_bom_child_data(
            {
                "FID": 101,
                "FTreeEntity_FENTRYID": 202,
                "FTreeEntity_FSEQ": 3,
                "FMATERIALID": "MAT-PARENT",
                "FCHILDNUMBER": "MAT-CHILD-006",
                "FCHILDNAME": "Child Material 006",
                "FNUMERATOR": "2",
                "FDENOMINATOR": "1",
                "FMATERIALTYPE": "6",
            }
        )

        self.assertIsNotNone(prepared)
        child_number_call = manager.field_mapping_resolver.resolve_field.call_args_list[0]
        child_name_call = manager.field_mapping_resolver.resolve_field.call_args_list[1]
        self.assertEqual(child_number_call.args[0], "eng_bomchild")
        self.assertEqual(child_number_call.args[1], "FCHILDNUMBER")
        self.assertEqual(child_number_call.args[2]["FCHILDNUMBER"], "MAT-CHILD-006")
        self.assertEqual(child_name_call.args[0], "eng_bomchild")
        self.assertEqual(child_name_call.args[1], "FCHILDNAME")
        self.assertEqual(child_name_call.args[2]["FCHILDNAME"], "Child Material 006")
        self.assertEqual(prepared[4], "RESOLVED-CHILD-006")
        self.assertEqual(prepared[5], "RESOLVED-CHILD-NAME-006")

    def test_prepare_eng_bom_child_data_uses_field_mapping_resolver_for_child_fields_on_list_payload(self) -> None:
        manager = self._build_manager()
        manager.field_mapping_resolver = Mock()
        manager.field_mapping_resolver.resolve_field.side_effect = [
            "RESOLVED-CHILD-007",
            "RESOLVED-CHILD-NAME-007",
        ]

        prepared = manager._prepare_eng_bom_child_data(
            [
                101,
                202,
                3,
                "MAT-PARENT",
                "MAT-CHILD-007",
                "Child Material 007",
                "2",
                "1",
                "1",
                "2",
                171190,
                88,
                "ROW-7",
                0,
                "7.5",
                "7.0",
                303,
                "7",
                "2026-04-23 10:30:00",
            ]
        )

        self.assertIsNotNone(prepared)
        self.assertEqual(manager.field_mapping_resolver.resolve_field.call_count, 2)
        child_number_call = manager.field_mapping_resolver.resolve_field.call_args_list[0]
        child_name_call = manager.field_mapping_resolver.resolve_field.call_args_list[1]
        self.assertEqual(child_number_call.args[0], "eng_bomchild")
        self.assertEqual(child_number_call.args[1], "FCHILDNUMBER")
        self.assertEqual(child_number_call.args[2]["FMATERIALIDCHILD.FNUMBER"], "MAT-CHILD-007")
        self.assertEqual(child_name_call.args[0], "eng_bomchild")
        self.assertEqual(child_name_call.args[1], "FCHILDNAME")
        self.assertEqual(child_name_call.args[2]["FMATERIALIDCHILD.FNAME"], "Child Material 007")
        self.assertEqual(prepared[4], "RESOLVED-CHILD-007")
        self.assertEqual(prepared[5], "RESOLVED-CHILD-NAME-007")

    def test_ensure_additional_columns_for_eng_bomchild_adds_child_number_column_on_sqlserver(self) -> None:
        manager = self._build_manager()
        manager.cursor = FakeCursor(fetchone_results=[None, None])
        manager.connection = FakeConnection()
        manager._invalidate_table_metadata_cache = lambda _table: None

        manager._ensure_additional_columns_for_eng_bomchild()

        self.assertEqual(manager.connection.commit_count, 2)
        self.assertEqual(len(manager.cursor.execute_calls), 4)
        self.assertIn("INFORMATION_SCHEMA.COLUMNS", manager.cursor.execute_calls[0][0])
        self.assertIn(
            "ALTER TABLE eng_bomchild ADD FCHILDNUMBER NVARCHAR(255) NULL",
            manager.cursor.execute_calls[1][0],
        )
        self.assertIn("INFORMATION_SCHEMA.COLUMNS", manager.cursor.execute_calls[2][0])
        self.assertIn(
            "ALTER TABLE eng_bomchild ADD FCHILDNAME NVARCHAR(255) NULL",
            manager.cursor.execute_calls[3][0],
        )

    def test_ensure_additional_columns_for_eng_bomchild_adds_child_number_column_on_mysql(self) -> None:
        manager = self._build_manager()
        manager.db_type = "mysql"
        manager.cursor = FakeCursor(fetchone_results=[None, None])
        manager.connection = FakeConnection()
        manager._invalidate_table_metadata_cache = lambda _table: None

        manager._ensure_additional_columns_for_eng_bomchild()

        self.assertEqual(manager.connection.commit_count, 2)
        self.assertEqual(len(manager.cursor.execute_calls), 4)
        self.assertIn("INFORMATION_SCHEMA.COLUMNS", manager.cursor.execute_calls[0][0])
        self.assertIn(
            "ALTER TABLE eng_bomchild ADD COLUMN FCHILDNUMBER VARCHAR(255) NULL",
            manager.cursor.execute_calls[1][0],
        )
        self.assertIn("INFORMATION_SCHEMA.COLUMNS", manager.cursor.execute_calls[2][0])
        self.assertIn(
            "ALTER TABLE eng_bomchild ADD COLUMN FCHILDNAME VARCHAR(255) NULL",
            manager.cursor.execute_calls[3][0],
        )

    def test_ensure_additional_columns_for_eng_bomchild_logs_visible_error_when_alter_fails(self) -> None:
        manager = self._build_manager()
        manager.cursor = FakeCursor(fetchone_results=[], execute_side_effects=[RuntimeError("alter failed")])
        manager.connection = FakeConnection()
        manager._invalidate_table_metadata_cache = lambda _table: None

        with self.assertLogs("src.core.mysql_manager", level="ERROR") as captured:
            manager._ensure_additional_columns_for_eng_bomchild()

        self.assertIn("eng_bomchild", "\n".join(captured.output))
        self.assertIn("alter failed", "\n".join(captured.output))

    def test_insert_eng_bom_child_locks_sql_order_with_prepare_mapping(self) -> None:
        manager = FakeEngBomChildWriteManager.__new__(FakeEngBomChildWriteManager)
        manager.connection = object()
        manager.cursor = object()
        manager.ensure_called = False
        manager.captured_sql = None
        manager.captured_prepared_row = None

        def ensure_columns() -> None:
            manager.ensure_called = True

        def batch_insert(sql, data, prepare_func) -> int:
            manager.captured_sql = sql
            manager.captured_prepared_row = prepare_func(data[0])
            return 1

        manager._ensure_additional_columns_for_eng_bomchild = ensure_columns
        manager._batch_insert = batch_insert

        inserted = insert_eng_bom_child(
            manager,
            [
                {
                    "FID": 101,
                    "FTreeEntity_FENTRYID": 202,
                    "FTreeEntity_FSEQ": 3,
                    "FMATERIALID": "MAT-PARENT",
                    "FMATERIALIDCHILD.FNUMBER": "MAT-CHILD-005",
                    "FMATERIALIDCHILD.FNAME": "Child Material 005",
                    "FNUMERATOR": "2",
                    "FDENOMINATOR": "1",
                    "FMATERIALTYPE": "5",
                }
            ],
        )

        self.assertEqual(inserted, 1)
        self.assertTrue(manager.ensure_called)
        self.assertIn(
            "(FID, FENTRYID, FSEQ, FMATERIALID, FCHILDNUMBER, FCHILDNAME, FNUMERATOR, FDENOMINATOR",
            manager.captured_sql,
        )
        self.assertEqual(manager.captured_prepared_row[3], "MAT-PARENT")
        self.assertEqual(manager.captured_prepared_row[4], "MAT-CHILD-005")
        self.assertEqual(manager.captured_prepared_row[5], "Child Material 005")
        self.assertEqual(manager.captured_prepared_row[6], 2.0)


if __name__ == "__main__":
    unittest.main()
