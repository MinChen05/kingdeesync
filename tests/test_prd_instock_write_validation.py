from __future__ import annotations

import unittest

from src.core.mysql_manager import MySQLManager
from src.core.write_outcome import WriteOutcome


class PrdInstockPrepareTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = MySQLManager.__new__(MySQLManager)
        self.manager._last_write_outcome = WriteOutcome()

    def test_prepare_prd_instock_data_skips_blank_billno(self) -> None:
        row = {
            "FID": 1,
            "FEntity_FENTRYID": 2,
            "FBILLNO": "   ",
            "FDATE": "2026-04-20 08:00:00",
        }

        prepared = MySQLManager._prepare_prd_instock_data(self.manager, row)

        self.assertIsNone(prepared)
        self.assertEqual(self.manager._last_write_outcome.invalid, 1)

    def test_prepare_prd_instock_data_skips_blank_primary_key(self) -> None:
        row = {
            "FID": "",
            "FEntity_FENTRYID": 2,
            "FBILLNO": "RK20260420",
        }

        prepared = MySQLManager._prepare_prd_instock_data(self.manager, row)

        self.assertIsNone(prepared)
        self.assertEqual(self.manager._last_write_outcome.invalid, 1)


if __name__ == "__main__":
    unittest.main()
