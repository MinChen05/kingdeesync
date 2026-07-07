from __future__ import annotations

import unittest

from src.core.field_mapping_resolver import FieldMappingResolver
from src.core.mysql_manager import MySQLManager
from src.core.upsert_engine_sqlserver import UpsertEngineSqlServer


class FakeConnection:
    def __init__(self) -> None:
        self.autocommit = True
        self.commit_count = 0
        self.rollback_count = 0

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1


class FakeCursor:
    def __init__(self) -> None:
        self.fast_executemany = False
        self._fetchall_queue: list[list[object]] = []
        self._fetchone_queue: list[object] = []
        self.execute_calls: list[tuple[str, object]] = []
        self.executemany_calls: list[tuple[str, list[list[object]]]] = []

    def execute(self, sql: str, params=None) -> None:
        self.execute_calls.append((sql, params))

    def executemany(self, sql: str, params) -> None:
        self.executemany_calls.append((sql, list(params)))

    def fetchall(self):
        if self._fetchall_queue:
            return self._fetchall_queue.pop(0)
        return []

    def fetchone(self):
        if self._fetchone_queue:
            return self._fetchone_queue.pop(0)
        return None


class FakeSqlServerManager:
    def __init__(self) -> None:
        self.db_type = "sqlserver"
        self.config = {
            "driver": "ODBC Driver 17 for SQL Server",
            "insert_threads": "1",
            "use_staging": "false",
            "batch_size": "10000",
            "commit_every_n_batches": "0",
            "source_dedup_enabled": "true",
        }
        self.cursor = FakeCursor()
        self.connection = FakeConnection()

    def _parse_insert_sql(self, sql: str):
        return "bd_material", ["FMATERIALID", "FNUMBER", "FNAME"]

    def _get_table_columns_info(self, table: str):
        return {"FMATERIALID": "bigint", "FNUMBER": "nvarchar", "FNAME": "nvarchar", "SYNC_TIME": "datetime"}

    def _get_primary_key(self, table: str):
        return "FMATERIALID"

    def _hashable_key(self, value):
        return value

    def _table_has_column(self, table: str, column: str) -> bool:
        return column.upper() == "SYNC_TIME"

    def _get_identity_columns(self, table: str):
        return None

    def _diagnose_data_type_error(self, table: str, columns, values) -> None:
        return None

    def _diagnose_string_truncation(self, table: str, columns, batch) -> None:
        return None

    def _maybe_create_stage_index(self, stage_ref: str, base_name: str, pk_cols_stage, loaded: int) -> None:
        return None


class UpsertEngineSqlServerTests(unittest.TestCase):
    def test_string_truncation_diagnosis_skips_trimmed_fields_but_reports_other_overlong_fields(self) -> None:
        manager = MySQLManager.__new__(MySQLManager)
        manager.db_type = "sqlserver"
        manager.cursor = FakeCursor()
        manager.cursor._fetchall_queue = [
            [
                ("FCHILDNAME", "nvarchar", 10),
                ("FBILLNO", "nvarchar", 6),
            ]
        ]
        manager.field_mapping_resolver = FieldMappingResolver(
            {
                "eng_bomchild": {
                    "FCHILDNAME": {
                        "sources": ["FCHILDNAME"],
                        "type": "string",
                        "max_length": 5,
                        "truncate_policy": "trim",
                    }
                }
            }
        )

        with self.assertLogs("src.core.mysql_manager", level="ERROR") as captured:
            MySQLManager._diagnose_string_truncation(
                manager,
                "eng_bomchild",
                ["FCHILDNAME", "FBILLNO"],
                [["ABCDEFG", "TOO-LONG"]],
            )

        output = "\n".join(captured.output)
        self.assertNotIn("FCHILDNAME", output)
        self.assertIn("FBILLNO", output)

    def test_bd_material_branch_initializes_batch_exec_seconds(self) -> None:
        manager = FakeSqlServerManager()
        manager.cursor._fetchall_queue = [
            [("FMATERIALID", "bigint"), ("FNUMBER", "nvarchar"), ("FNAME", "nvarchar"), ("SYNC_TIME", "datetime")],
            [(1,), (2,)],
        ]
        engine = UpsertEngineSqlServer(manager)

        inserted = engine.execute(
            sql="INSERT INTO bd_material (FMATERIALID, FNUMBER, FNAME) VALUES (%s, %s, %s)",
            values=[
                [1, "A001", "Material A"],
                [2, "A002", "Material B"],
                [3, "A003", "Material C"],
            ],
            batch_size=10000,
            commit_every_n_batches=0,
        )

        self.assertEqual(inserted, 3)
        self.assertGreaterEqual(len(manager.cursor.executemany_calls), 1)
        self.assertGreaterEqual(manager.connection.commit_count, 1)

    def test_uses_real_text_column_length_in_sqlserver_source_cast(self) -> None:
        manager = FakeSqlServerManager()
        manager.cursor._fetchall_queue = [
            [
                ("FMATERIALID", "bigint", None),
                ("FNUMBER", "nvarchar", 80),
                ("F_KDKF_HJFS", "nvarchar", 600),
                ("SYNC_TIME", "datetime", None),
            ],
            [],
        ]
        manager._parse_insert_sql = lambda sql: ("bd_material", ["FMATERIALID", "FNUMBER", "F_KDKF_HJFS"])
        manager._get_table_columns_info = lambda table: {
            "FMATERIALID": "bigint",
            "FNUMBER": "nvarchar",
            "F_KDKF_HJFS": "nvarchar",
            "SYNC_TIME": "datetime",
        }
        engine = UpsertEngineSqlServer(manager)

        inserted = engine.execute(
            sql="INSERT INTO bd_material (FMATERIALID, FNUMBER, F_KDKF_HJFS) VALUES (%s, %s, %s)",
            values=[[3, "A003", "X" * 300]],
            batch_size=10000,
            commit_every_n_batches=0,
        )

        self.assertEqual(inserted, 1)
        merge_sql = manager.cursor.executemany_calls[0][0]
        self.assertIn("TRY_CONVERT(NVARCHAR(600), ?) AS F_KDKF_HJFS", merge_sql)

    def test_bd_material_update_only_merge_uses_typed_source_casts(self) -> None:
        manager = FakeSqlServerManager()
        manager.cursor._fetchall_queue = [
            [
                ("FMATERIALID", "bigint", None),
                ("FNUMBER", "nvarchar", 80),
                ("F_JY_TEXT2", "nvarchar", 600),
                ("SYNC_TIME", "datetime", None),
            ],
            [("A003",)],
        ]
        manager._parse_insert_sql = lambda sql: ("bd_material", ["FMATERIALID", "FNUMBER", "F_JY_TEXT2"])
        manager._get_table_columns_info = lambda table: {
            "FMATERIALID": "bigint",
            "FNUMBER": "nvarchar",
            "F_JY_TEXT2": "nvarchar",
            "SYNC_TIME": "datetime",
        }
        engine = UpsertEngineSqlServer(manager)

        inserted = engine.execute(
            sql="INSERT INTO bd_material (FMATERIALID, FNUMBER, F_JY_TEXT2) VALUES (%s, %s, %s)",
            values=[[3, "A003", "X" * 256]],
            batch_size=10000,
            commit_every_n_batches=0,
        )

        self.assertEqual(inserted, 1)
        update_only_merge_sql = manager.cursor.executemany_calls[0][0]
        self.assertIn("ON t.FNUMBER = s.FNUMBER", update_only_merge_sql)
        self.assertIn("TRY_CONVERT(NVARCHAR(600), ?) AS F_JY_TEXT2", update_only_merge_sql)

    def test_filters_missing_entryid_for_ar_receivable(self) -> None:
        manager = FakeSqlServerManager()
        manager.cursor._fetchall_queue = [
            [
                ("FID", "bigint", None),
                ("FENTRYID", "bigint", None),
                ("FSEQ", "int", None),
                ("FBILLNO", "nvarchar", 80),
                ("SYNC_TIME", "datetime", None),
            ],
            [],
        ]
        manager._parse_insert_sql = lambda sql: ("AR_receivable", ["FID", "FENTRYID", "FSEQ", "FBILLNO"])
        manager._get_table_columns_info = lambda table: {
            "FID": "bigint",
            "FENTRYID": "bigint",
            "FSEQ": "int",
            "FBILLNO": "nvarchar",
            "SYNC_TIME": "datetime",
        }
        manager._get_primary_key = lambda table: "FENTRYID"
        engine = UpsertEngineSqlServer(manager)

        inserted = engine.execute(
            sql="INSERT INTO AR_receivable (FID, FENTRYID, FSEQ, FBILLNO) VALUES (%s, %s, %s, %s)",
            values=[
                [10, None, 1, "AR20260422001"],
                [10, 1001, 1, "AR20260422001"],
            ],
            batch_size=10000,
            commit_every_n_batches=0,
        )

        self.assertEqual(inserted, 1)
        self.assertEqual(len(manager.cursor.executemany_calls[0][1]), 1)

    def test_stk_instock_filters_missing_entryid(self) -> None:
        manager = FakeSqlServerManager()
        manager.cursor._fetchall_queue = [
            [
                ("FID", "bigint", None),
                ("FENTRYID", "bigint", None),
                ("FSEQ", "int", None),
                ("FBILLNO", "nvarchar", 80),
                ("SYNC_TIME", "datetime", None),
            ],
            [],
        ]
        manager._parse_insert_sql = lambda sql: ("STK_InStock", ["FID", "FENTRYID", "FSEQ", "FBILLNO"])
        manager._get_table_columns_info = lambda table: {
            "FID": "bigint",
            "FENTRYID": "bigint",
            "FSEQ": "int",
            "FBILLNO": "nvarchar",
            "SYNC_TIME": "datetime",
        }
        manager._get_primary_key = lambda table: "FENTRYID"
        engine = UpsertEngineSqlServer(manager)

        inserted = engine.execute(
            sql="INSERT INTO STK_InStock (FID, FENTRYID, FSEQ, FBILLNO) VALUES (%s, %s, %s, %s)",
            values=[
                [10, None, 1, "PI20260708001"],
                [10, 1001, 1, "PI20260708001"],
            ],
            batch_size=10000,
            commit_every_n_batches=0,
        )

        self.assertEqual(inserted, 1)
        self.assertEqual(len(manager.cursor.executemany_calls[0][1]), 1)

    def test_ar_receivable_staging_allows_omitted_sync_time(self) -> None:
        manager = FakeSqlServerManager()
        manager.config["force_staging_tables"] = "ar_receivable"
        manager.cursor._fetchone_queue = [(1,)]
        manager._parse_insert_sql = lambda sql: ("AR_receivable", ["FID", "FENTRYID", "FSEQ", "FBILLNO"])
        manager._get_table_columns_info = lambda table: {
            "FID": "bigint",
            "FENTRYID": "bigint",
            "FSEQ": "int",
            "FBILLNO": "nvarchar",
            "SYNC_TIME": "datetime",
        }
        manager._get_primary_key = lambda table: "FENTRYID"
        engine = UpsertEngineSqlServer(manager)

        inserted = engine.execute(
            sql="INSERT INTO AR_receivable (FID, FENTRYID, FSEQ, FBILLNO) VALUES (%s, %s, %s, %s)",
            values=[[10, 1001, 1, "AR20260422001"]],
            batch_size=10000,
            commit_every_n_batches=0,
        )

        self.assertEqual(inserted, 1)
        executed_sql = "\n".join(sql for sql, _params in manager.cursor.execute_calls)
        self.assertIn("ALTER COLUMN SYNC_TIME DATETIME NULL", executed_sql)

    def test_ar_receivable_staging_uses_type_safe_source_conversions(self) -> None:
        manager = FakeSqlServerManager()
        manager.config["force_staging_tables"] = "ar_receivable"
        manager.cursor._fetchone_queue = [(1,)]
        manager.cursor._fetchall_queue = [
            [
                ("FID", "bigint", None),
                ("FENTRYID", "bigint", None),
                ("FDATE", "date", None),
                ("FTAXPRICE", "numeric", None),
                ("FPRICEQTY", "decimal", None),
                ("FALLAMOUNTFOR_D", "decimal", None),
                ("FModifyDate", "datetime2", None),
                ("SYNC_TIME", "datetime", None),
            ]
        ]
        manager._parse_insert_sql = lambda sql: (
            "AR_receivable",
            ["FID", "FENTRYID", "FDATE", "FTAXPRICE", "FPRICEQTY", "FALLAMOUNTFOR_D", "FModifyDate"],
        )
        manager._get_table_columns_info = lambda table: {
            "FID": "bigint",
            "FENTRYID": "bigint",
            "FDATE": "date",
            "FTAXPRICE": "numeric",
            "FPRICEQTY": "decimal",
            "FALLAMOUNTFOR_D": "decimal",
            "FMODIFYDATE": "datetime2",
            "SYNC_TIME": "datetime",
        }
        manager._get_primary_key = lambda table: "FENTRYID"
        engine = UpsertEngineSqlServer(manager)

        inserted = engine.execute(
            sql=(
                "INSERT INTO AR_receivable "
                "(FID, FENTRYID, FDATE, FTAXPRICE, FPRICEQTY, FALLAMOUNTFOR_D, FModifyDate) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)"
            ),
            values=[[10, 1001, "2026-04-22", "12.34", "2", "24.68", "2026-04-22 10:00:00"]],
            batch_size=10000,
            commit_every_n_batches=0,
        )

        self.assertEqual(inserted, 1)
        staging_sql = manager.cursor.executemany_calls[0][0]
        self.assertIn("INSERT INTO [dbo].[__stage_", staging_sql)
        self.assertIn("TRY_CONVERT(DATETIME, ?) AS FDATE", staging_sql)
        self.assertIn("TRY_CONVERT(DECIMAL(23,10), CONVERT(NVARCHAR(64), ?)), 0) AS FTAXPRICE", staging_sql)
        self.assertIn("TRY_CONVERT(DECIMAL(23,10), CONVERT(NVARCHAR(64), ?)), 0) AS FPRICEQTY", staging_sql)
        self.assertIn("TRY_CONVERT(DATETIME, ?) AS FModifyDate", staging_sql)

    def test_ap_payable_uses_manager_column_types_when_information_schema_type_map_is_empty(self) -> None:
        manager = FakeSqlServerManager()
        manager.config["force_staging_tables"] = "ap_payable"
        manager.cursor._fetchone_queue = [(1,)]
        manager.cursor._fetchall_queue = [[]]
        manager._parse_insert_sql = lambda sql: (
            "AP_Payable",
            ["FID", "FENTRYID", "FDATE", "FPRICEQTY", "FALLAMOUNTFOR_D", "FModifyDate"],
        )
        manager._get_table_columns_info = lambda table: {
            "FID": "bigint",
            "FENTRYID": "bigint",
            "FDATE": "datetime",
            "FPRICEQTY": "numeric",
            "FALLAMOUNTFOR_D": "numeric",
            "FMODIFYDATE": "datetime",
            "SYNC_TIME": "datetime",
        }
        manager._get_primary_key = lambda table: "FENTRYID"
        engine = UpsertEngineSqlServer(manager)

        inserted = engine.execute(
            sql=(
                "INSERT INTO AP_Payable "
                "(FID, FENTRYID, FDATE, FPRICEQTY, FALLAMOUNTFOR_D, FModifyDate) "
                "VALUES (%s, %s, %s, %s, %s, %s)"
            ),
            values=[[10, 1001, "2026-04-22", "2", "24.68", "2026-04-22 10:00:00"]],
            batch_size=10000,
            commit_every_n_batches=0,
        )

        self.assertEqual(inserted, 1)
        staging_sql = manager.cursor.executemany_calls[0][0]
        self.assertIn("TRY_CONVERT(DATETIME, ?) AS FDATE", staging_sql)
        self.assertIn("TRY_CONVERT(DECIMAL(23,10), CONVERT(NVARCHAR(64), ?)), 0) AS FPRICEQTY", staging_sql)
        self.assertIn("TRY_CONVERT(DATETIME, ?) AS FModifyDate", staging_sql)

    def test_ap_payable_parameter_merge_uses_manager_column_type_fallback(self) -> None:
        manager = FakeSqlServerManager()
        manager.cursor._fetchall_queue = [[]]
        manager._parse_insert_sql = lambda sql: (
            "AP_Payable",
            ["FID", "FENTRYID", "FDATE", "FPRICEQTY", "FALLAMOUNTFOR_D", "FModifyDate"],
        )
        manager._get_table_columns_info = lambda table: {
            "FID": "bigint",
            "FENTRYID": "bigint",
            "FDATE": "datetime",
            "FPRICEQTY": "numeric",
            "FALLAMOUNTFOR_D": "numeric",
            "FMODIFYDATE": "datetime",
            "SYNC_TIME": "datetime",
        }
        manager._get_primary_key = lambda table: "FENTRYID"
        engine = UpsertEngineSqlServer(manager)

        inserted = engine.execute(
            sql=(
                "INSERT INTO AP_Payable "
                "(FID, FENTRYID, FDATE, FPRICEQTY, FALLAMOUNTFOR_D, FModifyDate) "
                "VALUES (%s, %s, %s, %s, %s, %s)"
            ),
            values=[[10, 1001, "2026-04-22", "2", "24.68", "2026-04-22 10:00:00"]],
            batch_size=10000,
            commit_every_n_batches=0,
        )

        self.assertEqual(inserted, 1)
        merge_sql = manager.cursor.executemany_calls[0][0]
        self.assertIn("TRY_CONVERT(DATETIME, ?) AS FDATE", merge_sql)
        self.assertIn("TRY_CONVERT(DECIMAL(23,10), CONVERT(NVARCHAR(64), ?)), 0) AS FALLAMOUNTFOR_D", merge_sql)

    def test_text_fallback_uses_max_length_when_information_schema_map_is_empty(self) -> None:
        manager = FakeSqlServerManager()
        manager.cursor._fetchall_queue = [[]]
        manager._parse_insert_sql = lambda sql: (
            "BD_Material",
            ["FMATERIALID", "F_JY_TEXT2"],
        )
        manager._get_table_columns_info = lambda table: {
            "FMATERIALID": "bigint",
            "F_JY_TEXT2": "nvarchar",
            "SYNC_TIME": "datetime",
        }
        manager._get_primary_key = lambda table: "FMATERIALID"
        engine = UpsertEngineSqlServer(manager)

        inserted = engine.execute(
            sql="INSERT INTO BD_Material (FMATERIALID, F_JY_TEXT2) VALUES (%s, %s)",
            values=[[3, "X" * 600]],
            batch_size=10000,
            commit_every_n_batches=0,
        )

        self.assertEqual(inserted, 1)
        merge_sql = manager.cursor.executemany_calls[0][0]
        self.assertIn("TRY_CONVERT(NVARCHAR(MAX), ?) AS F_JY_TEXT2", merge_sql)

    def test_eng_bomchild_staging_sql_includes_child_name(self) -> None:
        manager = FakeSqlServerManager()
        manager.config["force_staging_tables"] = "eng_bomchild"
        manager.cursor._fetchone_queue = [(1,)]
        manager.cursor._fetchall_queue = [[]]
        manager._parse_insert_sql = lambda sql: (
            "eng_bomchild",
            [
                "FID",
                "FENTRYID",
                "FSEQ",
                "FMATERIALID",
                "FCHILDNUMBER",
                "FCHILDNAME",
                "FNUMERATOR",
                "FDENOMINATOR",
                "FISSUETYPE",
                "FBACKFLUSHTYPE",
                "FSUPPLYORG",
                "FSTOCKID",
                "FENTRYROWID",
                "FREPLACEGROUP",
                "FQTY",
                "FACTUALQTY",
                "FMASTERID",
                "FMATERIALTYPE",
                "FMODIFYDATE",
            ],
        )
        manager._get_table_columns_info = lambda table: {
            "FID": "int",
            "FENTRYID": "int",
            "FSEQ": "int",
            "FMATERIALID": "nvarchar",
            "FCHILDNUMBER": "nvarchar",
            "FCHILDNAME": "nvarchar",
            "FNUMERATOR": "decimal",
            "FDENOMINATOR": "decimal",
            "FISSUETYPE": "nvarchar",
            "FBACKFLUSHTYPE": "nvarchar",
            "FSUPPLYORG": "int",
            "FSTOCKID": "int",
            "FENTRYROWID": "nvarchar",
            "FREPLACEGROUP": "int",
            "FQTY": "decimal",
            "FACTUALQTY": "decimal",
            "FMASTERID": "int",
            "FMATERIALTYPE": "nvarchar",
            "FMODIFYDATE": "datetime",
        }
        manager._get_primary_key = lambda table: "FID,FENTRYID"
        engine = UpsertEngineSqlServer(manager)

        inserted = engine.execute(
            sql=(
                "INSERT INTO eng_bomchild (FID, FENTRYID, FSEQ, FMATERIALID, FCHILDNUMBER, FCHILDNAME, FNUMERATOR, "
                "FDENOMINATOR, FISSUETYPE, FBACKFLUSHTYPE, FSUPPLYORG, FSTOCKID, FENTRYROWID, FREPLACEGROUP, "
                "FQTY, FACTUALQTY, FMASTERID, FMATERIALTYPE, FMODIFYDATE) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            ),
            values=[
                [
                    10,
                    1001,
                    1,
                    "MAT-001",
                    "CHILD-001",
                    "Child Name 001",
                    2,
                    1,
                    "1",
                    "2",
                    200,
                    300,
                    "ROW-1",
                    0,
                    5,
                    4,
                    900,
                    "1",
                    "2026-04-23 10:00:00",
                ]
            ],
            batch_size=10000,
            commit_every_n_batches=0,
        )

        self.assertEqual(inserted, 1)
        staging_sql = manager.cursor.executemany_calls[0][0]
        self.assertIn("FCHILDNUMBER", staging_sql)
        self.assertIn("FCHILDNAME", staging_sql)
        self.assertIn("INSERT INTO [dbo].[__stage_", staging_sql)
        self.assertIn("FCHILDNUMBER, FCHILDNAME, FNUMERATOR", staging_sql)
        self.assertRegex(
            staging_sql,
            (
                r"TRY_CAST\(\? AS NVARCHAR\(64\)\),\s*"
                r"TRY_CAST\(\? AS NVARCHAR\(255\)\),\s*"
                r"TRY_CAST\(\? AS NVARCHAR\(255\)\),\s*"
                r"COALESCE\(TRY_CAST\(\? AS DECIMAL\(23,10\)\), 0\)"
            ),
        )

    def test_eng_bomchild_staging_raises_when_column_order_mismatches(self) -> None:
        manager = FakeSqlServerManager()
        manager.config["force_staging_tables"] = "eng_bomchild"
        manager.cursor._fetchone_queue = [(1,)]
        manager.cursor._fetchall_queue = [[]]
        manager._parse_insert_sql = lambda sql: (
            "eng_bomchild",
            [
                "FID",
                "FENTRYID",
                "FSEQ",
                "FMATERIALID",
                "FCHILDNAME",
                "FCHILDNUMBER",
                "FNUMERATOR",
                "FDENOMINATOR",
                "FISSUETYPE",
                "FBACKFLUSHTYPE",
                "FSUPPLYORG",
                "FSTOCKID",
                "FENTRYROWID",
                "FREPLACEGROUP",
                "FQTY",
                "FACTUALQTY",
                "FMASTERID",
                "FMATERIALTYPE",
                "FMODIFYDATE",
            ],
        )
        manager._get_table_columns_info = lambda table: {
            "FID": "int",
            "FENTRYID": "int",
            "FSEQ": "int",
            "FMATERIALID": "nvarchar",
            "FCHILDNUMBER": "nvarchar",
            "FCHILDNAME": "nvarchar",
            "FNUMERATOR": "decimal",
            "FDENOMINATOR": "decimal",
            "FISSUETYPE": "nvarchar",
            "FBACKFLUSHTYPE": "nvarchar",
            "FSUPPLYORG": "int",
            "FSTOCKID": "int",
            "FENTRYROWID": "nvarchar",
            "FREPLACEGROUP": "int",
            "FQTY": "decimal",
            "FACTUALQTY": "decimal",
            "FMASTERID": "int",
            "FMATERIALTYPE": "nvarchar",
            "FMODIFYDATE": "datetime",
        }
        manager._get_primary_key = lambda table: "FID,FENTRYID"
        engine = UpsertEngineSqlServer(manager)

        with self.assertRaisesRegex(ValueError, "eng_bomchild staging column order mismatch"):
            engine.execute(
                sql=(
                    "INSERT INTO eng_bomchild (FID, FENTRYID, FSEQ, FMATERIALID, FCHILDNAME, FCHILDNUMBER, FNUMERATOR, "
                    "FDENOMINATOR, FISSUETYPE, FBACKFLUSHTYPE, FSUPPLYORG, FSTOCKID, FENTRYROWID, FREPLACEGROUP, "
                    "FQTY, FACTUALQTY, FMASTERID, FMATERIALTYPE, FMODIFYDATE) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                ),
                values=[
                    [
                        10,
                        1001,
                        1,
                        "MAT-001",
                        "Child Name 001",
                        "CHILD-001",
                        2,
                        1,
                        "1",
                        "2",
                        200,
                        300,
                        "ROW-1",
                        0,
                        5,
                        4,
                        900,
                        "1",
                        "2026-04-23 10:00:00",
                    ]
                ],
                batch_size=10000,
                commit_every_n_batches=0,
            )


if __name__ == "__main__":
    unittest.main()
