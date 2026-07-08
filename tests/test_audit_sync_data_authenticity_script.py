from src.core.sync_data_authenticity import AUDIT_SPECS
from scripts.maintenance.audit_sync_data_authenticity import (
    _execute_query,
    iter_db_queries,
    build_api_filter,
    build_db_query,
    run_audit,
)


def test_run_audit_writes_summary_and_detail(tmp_path):
    source = tmp_path / "targets.csv"
    source.write_text("form,db_key,status\n采购订单,1|2,needs_fix\n", encoding="utf-8-sig")
    out_dir = tmp_path / "out"
    db_rows = {
        "采购订单": {
            ("1", "2"): {
                "FID": 1,
                "FENTRYID": 2,
                "FBillNo": "PO1",
                "FNUMBER": "A",
                "FSupplier": "S",
                "FQTY": "10",
            }
        }
    }
    api_rows = {
        "采购订单": {
            ("1", "2"): {
                "FID": 1,
                "FPOOrderEntry_FENTRYID": 2,
                "FBillNo": "PO1",
                "FMaterialId.FNUMBER": "A",
                "FSupplierId.FNAME": "S",
                "FQTY": "10",
            }
        }
    }
    result = run_audit(
        source,
        {"采购订单"},
        out_dir,
        db_fetcher=lambda *_: db_rows,
        api_fetcher=lambda *_: api_rows,
    )
    assert result["total"] == 1
    assert (out_dir / "sync_data_authenticity_summary.csv").exists()
    assert (out_dir / "sync_data_authenticity_detail.csv").exists()


def test_build_db_query_uses_fid_and_fentryid():
    spec = AUDIT_SPECS["采购订单"]
    sql, params = build_db_query(spec, {("1", "2"), ("3", "4")})
    assert "FROM [PUR_PurchaseOrder]" in sql
    assert "[FID] = ? AND [FENTRYID] = ?" in sql
    assert params == ["1", "2", "3", "4"]


def test_build_api_filter_uses_fid_in_clause():
    spec = AUDIT_SPECS["采购入库单"]
    filter_string = build_api_filter(spec, {"100", "200"}, "FPurchaseOrgId = 171190")
    assert "FPurchaseOrgId = 171190" in filter_string
    assert "FID IN (100,200)" in filter_string


def test_iter_db_queries_chunks_large_identity_sets_under_sqlserver_param_limit():
    spec = AUDIT_SPECS["采购订单"]
    keys = {(str(fid), "1") for fid in range(1060)}
    queries = list(iter_db_queries(spec, keys, max_params=2000))
    assert len(queries) == 2
    assert all(len(params) <= 2000 for _, params in queries)


def test_execute_query_expands_pyodbc_params():
    class Cursor:
        def __init__(self):
            self.calls = []

        def execute(self, *args):
            self.calls.append(args)

    cursor = Cursor()
    _execute_query(cursor, "SELECT ? WHERE ? = ?", ["1", "2", "3"])
    assert cursor.calls == [("SELECT ? WHERE ? = ?", "1", "2", "3")]
