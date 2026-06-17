from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tests.test_ap_payable_field_mapping import MySQLManager


class BdMaterialDescriptionTests(unittest.TestCase):
    def test_prepare_bd_material_data_dict_returns_fdescription(self) -> None:
        manager = MySQLManager.__new__(MySQLManager)

        prepared = manager._prepare_bd_material_data(
            {
                "FMATERIALID": 1001,
                "FNUMBER": "MAT-001",
                "FMASTERID": 100,
                "FMATERIALGROUP": {"fname": "原材料"},
                "FCREATEORGID": 171190,
                "FUSEORGID": 171190,
                "FCREATEDATE": "2026-01-01",
                "FMODIFYDATE": "2026-06-01",
                "FDOCUMENTSTATUS": "C",
                "FFORBIDSTATUS": "A",
                "FAPPROVEDATE": "2026-01-02",
                "FREFSTATUS": "A",
                "F_TMHE_TEXT": "",
                "F_JY_TEXT": "",
                "F_JY_TEXT1": "",
                "F_JY_TEXT2": "",
                "F_JYX_TEXT1": "",
                "F_JYX_TEXT2": "",
                "F_JYX_TEXT4": "",
                "F_JYX_TEXT3": "",
                "F_JYX_ASSISTANT": "",
                "F_JYX_ASSISTANT1": "",
                "F_JYX_ASSISTANT2": "",
                "F_JY_QTY": 0,
                "F_JY_QTY1": 0,
                "F_KDKF_HJFS": "",
                "F_ORA_TEXT_9SB": "",
                "F_ORA_TEXT_QTR": "",
                "F_ORA_TEXT_QTR1": "",
                "FERPCLSID": "",
                "FCATEGORYID": None,
                "FTYPEID": None,
                "FBARCODE": "123456",
                "FNAME": "测试物料",
                "FSPECIFICATION": "规格A",
                "FDescription": "这是物料描述",
            }
        )

        self.assertIsNotNone(prepared)
        self.assertEqual(len(prepared), 36)
        self.assertEqual(prepared[35], "这是物料描述")

    def test_prepare_bd_material_data_dict_returns_fdescription_uppercase_key(self) -> None:
        manager = MySQLManager.__new__(MySQLManager)

        prepared = manager._prepare_bd_material_data(
            {
                "FMATERIALID": 1001,
                "FNUMBER": "MAT-001",
                "FDESCRIPTION": "大写key描述",
                "FNAME": "测试物料",
            }
        )

        self.assertIsNotNone(prepared)
        self.assertEqual(prepared[35], "大写key描述")

    def test_prepare_bd_material_data_list_36_fields_returns_description(self) -> None:
        manager = MySQLManager.__new__(MySQLManager)

        row = [None] * 36
        row[0] = 1001
        row[1] = "MAT-001"
        row[33] = "测试物料"
        row[34] = "规格A"
        row[35] = "列表描述"

        prepared = manager._prepare_bd_material_data(row)

        self.assertIsNotNone(prepared)
        self.assertEqual(len(prepared), 36)
        self.assertEqual(prepared[35], "列表描述")

    def test_prepare_bd_material_data_list_35_fields_defaults_description_empty(self) -> None:
        manager = MySQLManager.__new__(MySQLManager)

        row = [None] * 35
        row[0] = 1001
        row[1] = "MAT-001"
        row[33] = "测试物料"
        row[34] = "规格A"

        prepared = manager._prepare_bd_material_data(row)

        self.assertIsNotNone(prepared)
        self.assertEqual(len(prepared), 36)
        self.assertEqual(prepared[35], "")

    def test_insert_bd_material_sql_contains_fdescription(self) -> None:
        from src.core.masterdata_writer import insert_bd_material

        manager = SimpleNamespace(
            connection=Mock(),
            cursor=Mock(),
            _ensure_additional_columns_for_bd_material=Mock(),
            _ensure_bd_material_group_text_column=Mock(),
            _prepare_bd_material_data=Mock(return_value=()),
            _batch_insert=Mock(return_value=1),
        )

        inserted = insert_bd_material(manager, [{"FMATERIALID": 1001}])

        self.assertEqual(inserted, 1)
        sql = manager._batch_insert.call_args.args[0]
        self.assertIn("FDESCRIPTION", sql)
        self.assertIn("FDESCRIPTION = VALUES(FDESCRIPTION)", sql)

    def test_insert_bd_material_sql_column_count_matches_placeholder_count(self) -> None:
        from src.core.masterdata_writer import insert_bd_material

        manager = SimpleNamespace(
            connection=Mock(),
            cursor=Mock(),
            _ensure_additional_columns_for_bd_material=Mock(),
            _ensure_bd_material_group_text_column=Mock(),
            _prepare_bd_material_data=Mock(return_value=()),
            _batch_insert=Mock(return_value=1),
        )

        insert_bd_material(manager, [{"FMATERIALID": 1001}])
        sql = manager._batch_insert.call_args.args[0]

        import re

        insert_match = re.search(r"INSERT INTO bd_material\s*\(([^)]+)\)", sql)
        values_match = re.search(r"VALUES\s*\(([^)]+)\)", sql)
        self.assertIsNotNone(insert_match)
        self.assertIsNotNone(values_match)

        insert_cols = [c.strip() for c in insert_match.group(1).split(",")]
        value_placeholders = [p.strip() for p in values_match.group(1).split(",")]

        self.assertEqual(len(insert_cols), len(value_placeholders))
        self.assertEqual(len(insert_cols), 36)

    def test_type_converter_does_not_generate_char_max(self) -> None:
        from src.core.type_converter import TypeConverter

        cursor = Mock()
        converter = TypeConverter(cursor)

        # char/nchar with max_len=-1 should produce NVARCHAR(MAX), not CHAR(MAX)/NCHAR(MAX)
        for dtype in ("char", "nchar"):
            col_type_map = {"FDESCRIPTION": (dtype, -1)}
            parts = converter.build_source_conversion_parts(["FDESCRIPTION"], col_type_map)
            self.assertEqual(len(parts), 1)
            self.assertIn("NVARCHAR(MAX)", parts[0])
            self.assertNotIn("CHAR(MAX)", parts[0].upper().replace("NVARCHAR", "").replace("NCHAR", ""))
            self.assertNotIn("NCHAR(MAX)", parts[0])

    def test_type_converter_varchar_max_still_works(self) -> None:
        from src.core.type_converter import TypeConverter

        cursor = Mock()
        converter = TypeConverter(cursor)

        for dtype in ("varchar", "nvarchar"):
            col_type_map = {"FDESCRIPTION": (dtype, -1)}
            parts = converter.build_source_conversion_parts(["FDESCRIPTION"], col_type_map)
            self.assertEqual(len(parts), 1)
            self.assertIn(f"{dtype.upper()}(MAX)", parts[0])

    def test_build_write_summary_marks_zero_insert_as_failed_when_no_dedup(self) -> None:
        from src.core.write_outcome import WriteOutcome

        runner = SimpleNamespace(
            owner=SimpleNamespace(DEDUPLICATION_FORMS={"物料"}),
        )

        from src.core.form_sync_runner import FormSyncRunner

        summary = FormSyncRunner._build_write_summary(
            runner,
            "物料",
            fetched=34536,
            outcome=WriteOutcome(inserted=0, invalid=0, deduped=0, failed=0),
        )

        self.assertEqual(summary["fetched"], 34536)
        self.assertEqual(summary["inserted"], 0)
        self.assertEqual(summary["deduped"], 0)
        self.assertEqual(summary["failed"], 34536)

    def test_build_write_summary_allows_dedup_when_engine_reports_it(self) -> None:
        from src.core.write_outcome import WriteOutcome

        runner = SimpleNamespace(
            owner=SimpleNamespace(DEDUPLICATION_FORMS={"物料"}),
        )

        from src.core.form_sync_runner import FormSyncRunner

        summary = FormSyncRunner._build_write_summary(
            runner,
            "物料",
            fetched=100,
            outcome=WriteOutcome(inserted=50, invalid=0, deduped=50, failed=0),
        )

        self.assertEqual(summary["inserted"], 50)
        self.assertEqual(summary["deduped"], 50)
        self.assertEqual(summary["failed"], 0)

    def test_bd_material_staging_disables_fast_executemany(self) -> None:
        from tests.test_upsert_engine_sqlserver import FakeSqlServerManager

        manager = FakeSqlServerManager()
        manager.config["force_staging_tables"] = "bd_material"
        manager.cursor._fetchone_queue = [(1,)]
        manager._parse_insert_sql = lambda sql: ("bd_material", ["FMATERIALID", "FNUMBER", "FNAME"])
        manager._get_table_columns_info = lambda table: {
            "FMATERIALID": "bigint",
            "FNUMBER": "nvarchar",
            "FNAME": "nvarchar",
            "SYNC_TIME": "datetime",
        }
        manager._get_primary_key = lambda table: "FMATERIALID"

        from src.core.upsert_engine_sqlserver import UpsertEngineSqlServer

        engine = UpsertEngineSqlServer(manager)
        manager.cursor.fast_executemany = True

        engine.execute(
            sql="INSERT INTO bd_material (FMATERIALID, FNUMBER, FNAME) VALUES (%s, %s, %s)",
            values=[[1, "MAT-001", "Test"]],
            batch_size=10000,
            commit_every_n_batches=0,
        )

        self.assertFalse(manager.cursor.fast_executemany)

    def test_ensure_fdescription_adds_column_when_missing(self) -> None:
        class FakeCursor:
            def __init__(self):
                self.execute_calls = []
                self._fetchone_result = None

            def execute(self, sql, params=None):
                self.execute_calls.append((sql, params))

            def fetchone(self):
                return self._fetchone_result

        class FakeConnection:
            def __init__(self):
                self.commit_count = 0

            def commit(self):
                self.commit_count += 1

        manager = MySQLManager.__new__(MySQLManager)
        manager.db_type = "sqlserver"
        cursor = FakeCursor()
        manager.cursor = cursor
        manager.connection = FakeConnection()
        manager._invalidate_table_metadata_cache = Mock()

        # First call: column doesn't exist (fetchone returns None for ADD check)
        # Second call: column doesn't exist for FDESCRIPTION check
        cursor._fetchone_result = None

        manager._ensure_bd_material_fdescription_column()

        executed = [sql for sql, _ in cursor.execute_calls]
        self.assertTrue(any("ALTER TABLE bd_material ADD FDESCRIPTION NVARCHAR(MAX) NULL" in sql for sql in executed))

    def test_ensure_fdescription_widens_nvarchar_255_to_max(self) -> None:
        class FakeCursor:
            def __init__(self):
                self.execute_calls = []
                self._fetchone_results = []
                self._fetchone_idx = 0

            def execute(self, sql, params=None):
                self.execute_calls.append((sql, params))

            def fetchone(self):
                result = self._fetchone_results[self._fetchone_idx]
                self._fetchone_idx += 1
                return result

        class FakeConnection:
            def __init__(self):
                self.commit_count = 0

            def commit(self):
                self.commit_count += 1

        manager = MySQLManager.__new__(MySQLManager)
        manager.db_type = "sqlserver"
        cursor = FakeCursor()
        manager.cursor = cursor
        manager.connection = FakeConnection()
        manager._invalidate_table_metadata_cache = Mock()

        # Column exists with nvarchar(255)
        cursor._fetchone_results = [("nvarchar", 255)]

        manager._ensure_bd_material_fdescription_column()

        executed = [sql for sql, _ in cursor.execute_calls]
        self.assertTrue(
            any("ALTER TABLE bd_material ALTER COLUMN FDESCRIPTION NVARCHAR(MAX) NULL" in sql for sql in executed)
        )

    def test_ensure_fdescription_skips_when_already_max(self) -> None:
        class FakeCursor:
            def __init__(self):
                self.execute_calls = []

            def execute(self, sql, params=None):
                self.execute_calls.append((sql, params))

            def fetchone(self):
                return ("nvarchar", -1)

        manager = MySQLManager.__new__(MySQLManager)
        manager.db_type = "sqlserver"
        cursor = FakeCursor()
        manager.cursor = cursor
        manager.connection = Mock()
        manager._invalidate_table_metadata_cache = Mock()

        manager._ensure_bd_material_fdescription_column()

        executed = [sql for sql, _ in cursor.execute_calls]
        self.assertFalse(any("ALTER" in sql for sql in executed))

    def test_ensure_additional_columns_still_checks_fdescription_when_ora_text_exists(self) -> None:
        class FakeCursor:
            def __init__(self):
                self._fetchone_result = None

            def execute(self, sql, params=None):
                pass

            def fetchone(self):
                return self._fetchone_result

        manager = MySQLManager.__new__(MySQLManager)
        manager.db_type = "sqlserver"
        manager.cursor = FakeCursor()
        manager.connection = Mock()
        manager._invalidate_table_metadata_cache = Mock()

        # F_ORA_TEXT_9SB already exists → early path should NOT return before FDESCRIPTION check
        manager.cursor._fetchone_result = ("exists",)
        manager._ensure_bd_material_fdescription_column = Mock()

        manager._ensure_additional_columns_for_bd_material()

        manager._ensure_bd_material_fdescription_column.assert_called_once()


if __name__ == "__main__":
    unittest.main()
