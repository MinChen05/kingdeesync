import unittest

from src.core.mysql_manager import MySQLManager, WriteOutcome


class PurchaseInstockPrepareTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = MySQLManager.__new__(MySQLManager)
        self.manager._last_write_outcome = WriteOutcome()

    def test_prepare_purchase_instock_data_maps_basic_fields(self) -> None:
        item = {
            "FID": 10,
            "FInStockEntry_FENTRYID": 1001,
            "FInStockEntry_FSEQ": 1,
            "FBillNo": "PI20260708001",
            "FDate": "2026-07-08 08:00:00",
            "FDocumentStatus": "C",
            "FSupplierId.FNAME": "供应商A",
            "FPurchaseOrgId.FNAME": "台州市金宇机电有限公司",
            "FMaterialId.FNUMBER": "MAT-001",
            "FMaterialId.FNAME": "电机",
            "FRealQty": "12.5",
            "FSrcBillNo": "PO20260701001",
            "FSrcEntrySeq": 2,
            "FModifyDate": "2026-07-08 09:00:00",
        }

        prepared = self.manager._prepare_purchase_instock_data(item)

        self.assertIsNotNone(prepared)
        self.assertEqual(prepared[0], 10)
        self.assertEqual(prepared[1], 1001)
        self.assertEqual(prepared[3], "PI20260708001")
        self.assertEqual(prepared[6], "供应商A")
        self.assertEqual(prepared[10], 12.5)

    def test_prepare_purchase_instock_data_skips_blank_entry_id(self) -> None:
        item = {
            "FID": 10,
            "FInStockEntry_FENTRYID": "",
            "FBillNo": "PI20260708001",
        }

        prepared = self.manager._prepare_purchase_instock_data(item)

        self.assertIsNone(prepared)
        self.assertEqual(self.manager._last_write_outcome.invalid, 1)

    def test_prepare_purchase_instock_data_skips_blank_billno(self) -> None:
        item = {
            "FID": 10,
            "FInStockEntry_FENTRYID": 1001,
            "FBillNo": "   ",
        }

        prepared = self.manager._prepare_purchase_instock_data(item)

        self.assertIsNone(prepared)
        self.assertEqual(self.manager._last_write_outcome.invalid, 1)

    def test_prepare_purchase_instock_data_accepts_uppercase_aliases(self) -> None:
        item = {
            "FID": 10,
            "FENTRYID": 1001,
            "FBILLNO": "PI20260708001",
        }

        prepared = self.manager._prepare_purchase_instock_data(item)

        self.assertIsNotNone(prepared)
        self.assertEqual(prepared[1], 1001)
        self.assertEqual(prepared[3], "PI20260708001")

    def test_prepare_purchase_instock_data_maps_instock_entry_fseq_to_source_entry_seq(self) -> None:
        item = {
            "FID": 10,
            "FInStockEntry_FENTRYID": 1001,
            "FInStockEntry_FSEQ": 3,
            "FBillNo": "PI20260708001",
            "FInStockEntry_fseq": 3,
        }

        prepared = self.manager._prepare_purchase_instock_data(item)

        self.assertIsNotNone(prepared)
        self.assertEqual(prepared[12], 3)


if __name__ == "__main__":
    unittest.main()
