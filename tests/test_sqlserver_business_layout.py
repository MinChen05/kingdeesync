from __future__ import annotations

import unittest

from src.tools.sqlserver_business_layout import resolve_desired_order


class SqlServerBusinessLayoutTests(unittest.TestCase):
    def test_prd_mo_places_created_and_sync_columns_last(self) -> None:
        existing = [
            "FID",
            "FBILLNO",
            "FBILLTYPE",
            "FDATE",
            "FPRDORGID",
            "FWORKSHOPID",
            "FDOCUMENTSTATUS",
            "FMODIFYDATE",
            "FCANCELSTATUS",
            "SYNC_TIME",
            "FCREATEDATE",
        ]

        ordered = resolve_desired_order("prd_mo", existing)

        self.assertEqual(
            ordered,
            [
                "FID",
                "FBILLNO",
                "FBILLTYPE",
                "FDATE",
                "FPRDORGID",
                "FWORKSHOPID",
                "FDOCUMENTSTATUS",
                "FCANCELSTATUS",
                "FCREATEDATE",
                "FMODIFYDATE",
                "SYNC_TIME",
            ],
        )

    def test_eng_bomchild_moves_material_block_forward(self) -> None:
        existing = [
            "FID",
            "FENTRYID",
            "FSEQ",
            "FNUMERATOR",
            "FDENOMINATOR",
            "FISSUETYPE",
            "FBACKFLUSHTYPE",
            "FSUPPLYORG",
            "FSTOCKID",
            "FENTRYROWID",
            "FREPLACEGROUP",
            "FACTUALQTY",
            "FMASTERID",
            "FMATERIALID",
            "FCHILDNUMBER",
            "FCHILDNAME",
            "FQTY",
            "SYNC_TIME",
            "FMATERIALTYPE",
            "FMODIFYDATE",
        ]

        ordered = resolve_desired_order("eng_bomchild", existing)

        self.assertEqual(
            ordered,
            [
                "FID",
                "FENTRYID",
                "FSEQ",
                "FMASTERID",
                "FMATERIALID",
                "FCHILDNUMBER",
                "FCHILDNAME",
                "FMATERIALTYPE",
                "FNUMERATOR",
                "FDENOMINATOR",
                "FQTY",
                "FACTUALQTY",
                "FISSUETYPE",
                "FBACKFLUSHTYPE",
                "FSUPPLYORG",
                "FSTOCKID",
                "FENTRYROWID",
                "FREPLACEGROUP",
                "FMODIFYDATE",
                "SYNC_TIME",
            ],
        )

    def test_unknown_columns_are_preserved_at_end(self) -> None:
        existing = ["FENTRYID", "FBILLNO", "SYNC_TIME", "FEXTRA"]

        ordered = resolve_desired_order("pln_forecast", existing)

        self.assertEqual(ordered[-1], "FEXTRA")
        self.assertIn("FENTRYID", ordered)
        self.assertIn("SYNC_TIME", ordered)

    def test_bd_material_places_return_fee_between_hjfs_and_ora_text(self) -> None:
        existing = [
            "FMATERIALID",
            "FNUMBER",
            "FMASTERID",
            "FNAME",
            "FSPECIFICATION",
            "FDESCRIPTION",
            "FBARCODE",
            "FMATERIALGROUP",
            "FCREATEORGID",
            "FUSEORGID",
            "FCATEGORYID",
            "FTYPEID",
            "FERPCLSID",
            "FDOCUMENTSTATUS",
            "FFORBIDSTATUS",
            "FREFSTATUS",
            "F_TMHE_TEXT",
            "F_JY_TEXT",
            "F_JY_TEXT1",
            "F_JY_TEXT2",
            "F_JYX_TEXT1",
            "F_JYX_TEXT2",
            "F_JYX_TEXT3",
            "F_JYX_TEXT4",
            "F_JYX_ASSISTANT",
            "F_JYX_ASSISTANT1",
            "F_JYX_ASSISTANT2",
            "F_JY_QTY",
            "F_JY_QTY1",
            "F_KDKF_HJFS",
            "F_ORA_TEXT_QTR",
            "F_ORA_TEXT_QTR1",
            "FCREATEDATE",
            "FAPPROVEDATE",
            "FMODIFYDATE",
            "SYNC_TIME",
            "F_ORA_TEXT_9SB",
        ]

        ordered = resolve_desired_order("bd_material", existing)

        self.assertEqual(
            ordered,
            [
                "FMATERIALID",
                "FNUMBER",
                "FMASTERID",
                "FNAME",
                "FSPECIFICATION",
                "FDESCRIPTION",
                "FBARCODE",
                "FMATERIALGROUP",
                "FCREATEORGID",
                "FUSEORGID",
                "FCATEGORYID",
                "FTYPEID",
                "FERPCLSID",
                "FDOCUMENTSTATUS",
                "FFORBIDSTATUS",
                "FREFSTATUS",
                "F_TMHE_TEXT",
                "F_JY_TEXT",
                "F_JY_TEXT1",
                "F_JY_TEXT2",
                "F_JYX_TEXT1",
                "F_JYX_TEXT2",
                "F_JYX_TEXT3",
                "F_JYX_TEXT4",
                "F_JYX_ASSISTANT",
                "F_JYX_ASSISTANT1",
                "F_JYX_ASSISTANT2",
                "F_JY_QTY",
                "F_JY_QTY1",
                "F_KDKF_HJFS",
                "F_ORA_TEXT_9SB",
                "F_ORA_TEXT_QTR",
                "F_ORA_TEXT_QTR1",
                "FCREATEDATE",
                "FAPPROVEDATE",
                "FMODIFYDATE",
                "SYNC_TIME",
            ],
        )

    def test_customer_places_custpype_before_createdate(self) -> None:
        existing = [
            "FCUSTID",
            "FNUMBER",
            "FNAME",
            "FGROUP",
            "FSELLERNAME",
            "FSTAFF",
            "FCUSTLEVEL",
            "FCREATEDATE",
            "FMODIFYDATE",
            "SYNC_TIME",
            "FCUSTPYPE",
        ]

        ordered = resolve_desired_order("customer", existing)

        self.assertEqual(
            ordered,
            [
                "FCUSTID",
                "FNUMBER",
                "FNAME",
                "FGROUP",
                "FSELLERNAME",
                "FSTAFF",
                "FCUSTLEVEL",
                "FCUSTPYPE",
                "FCREATEDATE",
                "FMODIFYDATE",
                "SYNC_TIME",
            ],
        )

    def test_ar_receivable_places_material_and_amount_fields_before_modifydate(self) -> None:
        existing = [
            "FID",
            "FENTRYID",
            "FSEQ",
            "FBILLNAME",
            "FBILLNO",
            "FDATE",
            "FCUSTOMERNAME",
            "FSETACCOUNTTYPE",
            "FBASEPROPERTY1",
            "FSOURCEBILLNO",
            "FMODIFYDATE",
            "SYNC_TIME",
            "FMATERIALNUMBER",
            "FMATERIALNAME",
            "FTAXPRICE",
            "FPRICEQTY",
            "FALLAMOUNTFOR_D",
        ]

        ordered = resolve_desired_order("AR_receivable", existing)

        self.assertEqual(
            ordered,
            [
                "FID",
                "FENTRYID",
                "FSEQ",
                "FBILLNAME",
                "FBILLNO",
                "FDATE",
                "FCUSTOMERNAME",
                "FSETACCOUNTTYPE",
                "FBASEPROPERTY1",
                "FSOURCEBILLNO",
                "FMATERIALNUMBER",
                "FMATERIALNAME",
                "FTAXPRICE",
                "FPRICEQTY",
                "FALLAMOUNTFOR_D",
                "FMODIFYDATE",
                "SYNC_TIME",
            ],
        )

    def test_stk_instock_places_material_and_source_fields_before_modifydate(self) -> None:
        existing = [
            "FID",
            "FENTRYID",
            "FSEQ",
            "FBILLNO",
            "FDATE",
            "FDOCUMENTSTATUS",
            "FSUPPLIERNAME",
            "FPURCHASEORGNAME",
            "FMODIFYDATE",
            "SYNC_TIME",
            "FMATERIALNUMBER",
            "FMATERIALNAME",
            "FREALQTY",
            "FSRCBILLNO",
            "FSRCENTRYSEQ",
        ]

        ordered = resolve_desired_order("STK_InStock", existing)

        self.assertEqual(
            ordered,
            [
                "FID",
                "FENTRYID",
                "FSEQ",
                "FBILLNO",
                "FDATE",
                "FDOCUMENTSTATUS",
                "FSUPPLIERNAME",
                "FPURCHASEORGNAME",
                "FMATERIALNUMBER",
                "FMATERIALNAME",
                "FREALQTY",
                "FSRCBILLNO",
                "FSRCENTRYSEQ",
                "FMODIFYDATE",
                "SYNC_TIME",
            ],
        )


if __name__ == "__main__":
    unittest.main()
