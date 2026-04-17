from __future__ import annotations

import logging
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from src.core.filter_builder import FilterBuilder


class FilterBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = FilterBuilder(logger_=logging.getLogger("test.filter_builder"))
        self.sales_order = "\u9500\u552e\u8ba2\u5355"

    def test_incremental_filter_uses_inferred_modify_field_and_persists_it(self) -> None:
        fake_db = SimpleNamespace(get_last_modify_time=lambda table_name: datetime(2026, 1, 2, 3, 4, 5))

        with patch("src.core.filter_builder.config_manager") as mock_config_manager:
            mock_config_manager.get_form_queries.return_value = {
                self.sales_order: {
                    "FilterString": "FDocumentStatus='C'",
                    "FieldKeys": "FID,FModifyDate,FBillNo",
                }
            }
            mock_config_manager.get_increment_field.return_value = ""

            result = self.builder.build_filter_string(
                self.sales_order,
                SimpleNamespace(value="incremental"),
                "saleorder",
                db_manager=fake_db,
            )

            self.assertEqual(
                result,
                "FDocumentStatus='C' and FModifyDate > '2026-01-02 03:04:05'",
            )
            mock_config_manager.set_increment_field.assert_called_once_with("saleorder", "FModifyDate")

    def test_incremental_filter_falls_back_to_base_filter_when_no_last_sync_time(self) -> None:
        fake_db = SimpleNamespace(get_last_modify_time=lambda table_name: None)

        with patch("src.core.filter_builder.config_manager") as mock_config_manager:
            mock_config_manager.get_form_queries.return_value = {
                self.sales_order: {
                    "FilterString": "FBillNo like 'SO%'",
                    "FieldKeys": "FID,FMODIFYDATE,FBillNo",
                }
            }
            mock_config_manager.get_increment_field.side_effect = lambda key: "FMODIFYDATE" if key == "saleorder" else ""

            result = self.builder.build_filter_string(
                self.sales_order,
                SimpleNamespace(value="incremental"),
                "saleorder",
                db_manager=fake_db,
            )

            self.assertEqual(result, "FBillNo like 'SO%'")
            mock_config_manager.set_increment_field.assert_not_called()


if __name__ == "__main__":
    unittest.main()

