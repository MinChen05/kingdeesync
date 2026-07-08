from src.core.sync_data_authenticity import (
    AUDIT_SPECS,
    AuditStatus,
    audit_row,
    compare_date,
    compare_decimal,
    compare_string,
)


def test_compare_decimal_accepts_equivalent_scale():
    assert compare_decimal("12.500000", "12.5").matched is True


def test_compare_decimal_reports_difference():
    result = compare_decimal("0", "1872000.0000000000")
    assert result.matched is False
    assert result.db_value == "0"
    assert result.api_value == "1872000.0000000000"


def test_compare_string_trims_spaces():
    assert compare_string(" MAT-001 ", "MAT-001").matched is True


def test_compare_date_compares_to_seconds():
    result = compare_date("2026-07-08 10:20:07.833333", "2026-07-08T10:20:07.833")
    assert result.matched is True


def test_purchase_instock_spec_marks_date_as_warning():
    spec = AUDIT_SPECS["采购入库单"]
    assert spec.fields["FDATE"].severity == "warning"
    assert spec.fields["FREALQTY"].severity == "blocker"


def test_audit_row_blocks_on_material_mismatch():
    spec = AUDIT_SPECS["采购入库单"]
    db_row = {
        "FID": 1,
        "FENTRYID": 2,
        "FBILLNO": "RK1",
        "FSEQ": 1,
        "FMATERIALNUMBER": "A",
        "FSUPPLIERNAME": "S",
        "FREALQTY": "10",
    }
    api_row = {
        "FID": 1,
        "FInStockEntry_FENTRYID": 2,
        "FBillNo": "RK1",
        "FInStockEntry_FSEQ": 1,
        "FMaterialId.FNUMBER": "B",
        "FSupplierId.FNAME": "S",
        "FRealQty": "10",
    }
    result = audit_row(spec, db_row, api_row)
    assert result.status == AuditStatus.DIMENSION_MISMATCH
    assert result.eligible_for_rehydration is False


def test_audit_row_allows_warning_only_date_mismatch():
    spec = AUDIT_SPECS["采购订单"]
    db_row = {
        "FID": 1,
        "FENTRYID": 2,
        "FBillNo": "PO1",
        "FNUMBER": "A",
        "FSupplier": "S",
        "FQTY": "10",
        "FModifyDate": "2026-07-01 00:00:00",
    }
    api_row = {
        "FID": 1,
        "FPOOrderEntry_FENTRYID": 2,
        "FBillNo": "PO1",
        "FMaterialId.FNUMBER": "A",
        "FSupplierId.FNAME": "S",
        "FQTY": "10",
        "FModifyDate": "2026-07-02 00:00:00",
    }
    result = audit_row(spec, db_row, api_row)
    assert result.status == AuditStatus.WARNING_ONLY
    assert result.eligible_for_rehydration is True
