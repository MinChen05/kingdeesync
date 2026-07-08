from src.core.sync_data_authenticity import (
    AUDIT_SPECS,
    AuditStatus,
    RowAuditResult,
    audit_row,
    build_mapping_draft_rows,
    compare_date,
    compare_decimal,
    compare_string,
    detail_rows,
    load_targets_from_difference_csv,
    summarize_results,
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


def test_build_mapping_draft_rows_reports_supported_purchase_form():
    form_queries = {
        "采购订单": {"FormId": "PUR_PurchaseOrder", "FieldKeys": "FID,FPOOrderEntry_FENTRYID,FBillNo,FQTY"}
    }
    tables = {"采购订单": {"table": "PUR_PurchaseOrder", "insert_method": "insert_purchase_order"}}
    db_columns = {"PUR_PurchaseOrder": {"FID", "FENTRYID", "FBillNo", "FQTY"}}

    rows = build_mapping_draft_rows(form_queries, tables, db_columns)

    assert rows[0]["form"] == "采购订单"
    assert rows[0]["identity_confirmed"] == "true"
    assert rows[0]["missing_db_fields"] == ""
    assert rows[0]["missing_api_fields"] == ""


def test_build_mapping_draft_rows_marks_unsupported_report_form():
    form_queries = {"科目余额表": {"FormId": "GL_RPT_AccountBalance", "FieldKeys": "FBALANCEID"}}
    tables = {"科目余额表": {"table": "GL_RPT_AccountBalance", "insert_method": None}}

    rows = build_mapping_draft_rows(form_queries, tables, {})

    assert rows[0]["form"] == "科目余额表"
    assert rows[0]["unsupported_reason"] == "report_form_requires_separate_design"


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


def test_audit_row_marks_quantity_difference_as_value_mismatch():
    spec = AUDIT_SPECS["采购订单"]
    db_row = {
        "FID": 1,
        "FENTRYID": 2,
        "FBillNo": "PO1",
        "FNUMBER": "A",
        "FSupplier": "S",
        "FQTY": "0",
    }
    api_row = {
        "FID": 1,
        "FPOOrderEntry_FENTRYID": 2,
        "FBillNo": "PO1",
        "FMaterialId.FNUMBER": "A",
        "FSupplierId.FNAME": "S",
        "FQTY": "10",
    }
    result = audit_row(spec, db_row, api_row)
    assert result.status == AuditStatus.VALUE_MISMATCH
    assert result.eligible_for_rehydration is True
    assert result.differences[0].field == "FQTY"


def test_audit_row_blocks_missing_api_row():
    spec = AUDIT_SPECS["采购订单"]
    db_row = {"FID": 1, "FENTRYID": 2}
    result = audit_row(spec, db_row, None)
    assert result.status == AuditStatus.MISSING_API
    assert result.eligible_for_rehydration is False


def test_audit_row_blocks_missing_db_row():
    spec = AUDIT_SPECS["采购订单"]
    api_row = {"FID": 1, "FPOOrderEntry_FENTRYID": 2}
    result = audit_row(spec, None, api_row)
    assert result.status == AuditStatus.MISSING_DB
    assert result.eligible_for_rehydration is False


def test_load_targets_from_difference_csv_filters_forms(tmp_path):
    csv_path = tmp_path / "diff.csv"
    csv_path.write_text(
        "form,db_key,status\n采购订单,1|2,needs_fix\n销售订单,3|4,needs_fix\n",
        encoding="utf-8-sig",
    )
    targets = load_targets_from_difference_csv(csv_path, {"采购订单"})
    assert targets == {"采购订单": {("1", "2")}}


def test_summarize_results_counts_statuses():
    results = [
        RowAuditResult("采购订单", ("1", "1"), AuditStatus.PASSED, True, tuple()),
        RowAuditResult("采购订单", ("1", "2"), AuditStatus.WARNING_ONLY, True, tuple()),
        RowAuditResult("采购订单", ("1", "3"), AuditStatus.DIMENSION_MISMATCH, False, tuple()),
    ]
    rows = summarize_results(results)
    counts = {row["status"]: row["count"] for row in rows}
    assert counts["passed"] == 1
    assert counts["warning_only"] == 1
    assert counts["dimension_mismatch"] == 1


def test_detail_rows_keeps_passed_rows_visible():
    result = RowAuditResult("采购订单", ("1", "2"), AuditStatus.PASSED, True, tuple())
    rows = detail_rows([result])
    assert rows == [
        {
            "form": "采购订单",
            "key": "1|2",
            "status": "passed",
            "eligible_for_rehydration": "true",
            "field": "",
            "severity": "",
            "db_value": "",
            "api_value": "",
        }
    ]
