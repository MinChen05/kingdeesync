from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from tests.test_ap_payable_field_mapping import MySQLManager


class ArReceivableSourceBillNoTests(unittest.TestCase):
    def test_builtin_ar_receivable_query_requests_source_bill_no(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        form_queries = json.loads((repo_root / "src" / "config" / "form-queries.json").read_text(encoding="utf-8"))

        field_keys = form_queries["应收单"]["FieldKeys"].split(",")

        self.assertIn("FSourceBillNo", field_keys)

    def test_prepare_ar_receivable_data_reads_source_bill_no_from_dict_payload(self) -> None:
        manager = MySQLManager.__new__(MySQLManager)

        prepared = manager._prepare_ar_receivable_data(
            {
                "FID": 1001,
                "FEntityDetail_FENTRYID": 2001,
                "FEntityDetail_FSEQ": 1,
                "FBillTypeID.FNAME": "标准应收单",
                "FBillNo": "AR202601001",
                "FDATE": "2026-01-10",
                "FCUSTOMERID.FNAME": "测试客户",
                "FSETACCOUNTTYPE": "3",
                "F_ora_BaseProperty1": "项目A",
                "FSourceBillNo": "SO202601001",
                "FMATERIALID.FNUMBER": "MAT-001",
                "FMATERIALID.FNAME": "测试物料",
                "FTaxPrice": "12.34",
                "FPriceQty": "2",
                "FALLAMOUNTFOR_D": "24.68",
                "FModifyDate": "2026-01-10 10:00:00",
            }
        )

        self.assertIsNotNone(prepared)
        self.assertEqual(prepared[9], "SO202601001")

    def test_insert_ar_receivable_writes_source_bill_no_column(self) -> None:
        from src.core.sales_writer import insert_ar_receivable

        manager = SimpleNamespace(
            _ensure_additional_columns_for_ar_receivable=Mock(),
            _prepare_ar_receivable_data=Mock(return_value=()),
            _batch_insert=Mock(return_value=1),
        )

        inserted = insert_ar_receivable(manager, [{"FID": 1001}])

        self.assertEqual(inserted, 1)
        manager._ensure_additional_columns_for_ar_receivable.assert_called_once()
        sql = manager._batch_insert.call_args.args[0]
        self.assertIn("FSOURCEBILLNO", sql)

    def test_ensure_ar_receivable_adds_source_bill_no_column_when_missing(self) -> None:
        class FakeConnection:
            def __init__(self) -> None:
                self.commit_count = 0

            def commit(self) -> None:
                self.commit_count += 1

        class FakeCursor:
            def __init__(self) -> None:
                self.execute_calls: list[tuple[str, object]] = []

            def execute(self, sql: str, params=None) -> None:
                self.execute_calls.append((sql, params))

            def fetchall(self):
                return [("FID",), ("FENTRYID",)]

        manager = MySQLManager.__new__(MySQLManager)
        manager.db_type = "sqlserver"
        manager.cursor = FakeCursor()
        manager.connection = FakeConnection()
        manager._invalidate_table_metadata_cache = Mock()

        manager._ensure_additional_columns_for_ar_receivable()

        executed_sql = "\n".join(sql for sql, _params in manager.cursor.execute_calls)
        self.assertIn("ALTER TABLE AR_receivable ADD FSOURCEBILLNO NVARCHAR(255) NULL", executed_sql)
        self.assertEqual(manager.connection.commit_count, 1)
        manager._invalidate_table_metadata_cache.assert_called_once_with("AR_receivable")


if __name__ == "__main__":
    unittest.main()
