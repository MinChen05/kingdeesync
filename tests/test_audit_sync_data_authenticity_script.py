import csv

from src.core.sync_data_authenticity import AUDIT_SPECS
from scripts.maintenance.audit_sync_data_authenticity import (
    _execute_query,
    fetch_db_columns,
    iter_db_queries,
    build_api_filter,
    build_db_query,
    main,
    run_audit,
    run_discovery,
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


def test_run_audit_writes_blockers_when_requested(tmp_path):
    source = tmp_path / "targets.csv"
    source.write_text(
        "form,db_key,status\n采购订单,1|1,needs_fix\n采购订单,1|2,needs_fix\n",
        encoding="utf-8-sig",
    )
    out_dir = tmp_path / "out"
    db_rows = {
        "采购订单": {
            ("1", "1"): {
                "FID": 1,
                "FENTRYID": 1,
                "FBillNo": "PO1",
                "FNUMBER": "A",
                "FSupplier": "S",
                "FQTY": "10",
            },
            ("1", "2"): {
                "FID": 1,
                "FENTRYID": 2,
                "FBillNo": "PO2",
                "FNUMBER": "A",
                "FSupplier": "S",
                "FQTY": "10",
            },
        }
    }
    api_rows = {
        "采购订单": {
            ("1", "1"): {
                "FID": 1,
                "FPOOrderEntry_FENTRYID": 1,
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
        write_blockers=True,
    )

    blockers_path = out_dir / "sync_data_authenticity_blockers.csv"
    with blockers_path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    assert result["blockers"] == blockers_path
    assert [row["status"] for row in rows] == ["missing_api"]


def test_main_uses_batch_when_forms_are_omitted(monkeypatch):
    calls = []

    def fake_run_audit(source, forms, out_dir, write_blockers=False):
        calls.append((source, forms, out_dir, write_blockers))
        return {"total": 0, "summary": "summary.csv", "detail": "detail.csv"}

    monkeypatch.setattr("scripts.maintenance.audit_sync_data_authenticity.run_audit", fake_run_audit)

    exit_code = main(["--batch", "production_documents", "--source", "source.csv"])

    assert exit_code == 0
    assert calls[0][1] == {
        "生产入库单",
        "生产订单主表",
        "生产订单明细",
        "生产用料清单主表",
        "生产用料清单明细表",
        "预测订单",
    }
    assert calls[0][3] is True


def test_main_explicit_forms_override_batch(monkeypatch):
    calls = []

    def fake_run_audit(source, forms, out_dir, write_blockers=False):
        calls.append(forms)
        return {"total": 0, "summary": "summary.csv", "detail": "detail.csv"}

    monkeypatch.setattr("scripts.maintenance.audit_sync_data_authenticity.run_audit", fake_run_audit)

    exit_code = main(["--batch", "production_documents", "--forms", "采购订单", "--source", "source.csv"])

    assert exit_code == 0
    assert calls == [{"采购订单"}]


def test_run_discovery_writes_mapping_draft(tmp_path):
    form_queries = {
        "采购订单": {
            "FormId": "PUR_PurchaseOrder",
            "FieldKeys": "FID,FPOOrderEntry_FENTRYID,FBillNo",
        }
    }
    tables = {"采购订单": {"table": "PUR_PurchaseOrder", "insert_method": "insert_purchase_order"}}
    db_columns = {"PUR_PurchaseOrder": {"FID", "FENTRYID", "FBillNo"}}

    result = run_discovery(
        tmp_path,
        form_queries=form_queries,
        tables=tables,
        db_columns=db_columns,
    )

    draft_path = tmp_path / "authenticity_mapping_draft.csv"
    assert result["rows"] == 1
    assert result["mapping_draft"] == draft_path
    assert draft_path.exists()
    content = draft_path.read_text(encoding="utf-8-sig")
    assert "form,table,form_id" in content
    assert "采购订单,PUR_PurchaseOrder,PUR_PurchaseOrder" in content


def test_fetch_db_columns_uses_information_schema_select(monkeypatch):
    class Cursor:
        description = [("TABLE_NAME",), ("COLUMN_NAME",)]

        def __init__(self):
            self.sql = ""

        def execute(self, sql):
            self.sql = sql

        def fetchall(self):
            return [("PUR_PurchaseOrder", "FID"), ("PUR_PurchaseOrder", "FBillNo")]

    class Manager:
        instances = []

        def __init__(self):
            self.cursor = Cursor()
            self.disconnected = False
            Manager.instances.append(self)

        def connect(self):
            return True

        def disconnect(self):
            self.disconnected = True

    monkeypatch.setattr("src.core.mysql_manager.MySQLManager", Manager)

    columns = fetch_db_columns()

    sql = Manager.instances[0].cursor.sql.lower()
    assert columns == {"PUR_PurchaseOrder": {"FID", "FBillNo"}}
    assert "information_schema.columns" in sql
    assert sql.lstrip().startswith("select")
    assert not any(keyword in sql for keyword in ("insert", "update", "delete", "merge", "truncate", "drop"))
    assert Manager.instances[0].disconnected is True


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
