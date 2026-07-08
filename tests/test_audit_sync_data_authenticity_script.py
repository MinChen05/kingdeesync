from scripts.maintenance.audit_sync_data_authenticity import run_audit


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
