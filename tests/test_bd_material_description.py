from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

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


if __name__ == "__main__":
    unittest.main()
