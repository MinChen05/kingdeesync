from __future__ import annotations

import unittest
from unittest.mock import Mock

from src.core.masterdata_writer import insert_eng_bom_child
from src.core.mysql_manager import MySQLManager


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
            "MAT-CHILD-006",
            "Child Material 006",
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
        manager.field_mapping_resolver.resolve_field.assert_any_call(
            "eng_bomchild",
            "FCHILDNUMBER",
            unittest.mock.ANY,
        )
        manager.field_mapping_resolver.resolve_field.assert_any_call(
            "eng_bomchild",
            "FCHILDNAME",
            unittest.mock.ANY,
        )
        self.assertEqual(prepared[4], "MAT-CHILD-006")
        self.assertEqual(prepared[5], "Child Material 006")

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
