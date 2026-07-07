# Verification Report: add-purchase-instock-sync

## Summary

| Dimension | Status |
| --- | --- |
| Completeness | 23/23 tasks complete, 5 requirements checked |
| Correctness | 5/5 requirements covered by implementation evidence and tests |
| Coherence | Follows OpenSpec design and technical Design Doc |

## Verification Evidence

- `openspec status --change "add-purchase-instock-sync" --json`: `isComplete=true`, 23/23 tasks complete.
- `openspec validate add-purchase-instock-sync --strict`: `Change 'add-purchase-instock-sync' is valid`.
- Build guard command: `/mnt/c/Users/Administrator/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/test_config_manager.py::ConfigManagerTests::test_builtin_tables_json_registers_purchase_instock_sync tests/test_writers_registry.py tests/test_purchase_instock_write_validation.py tests/test_upsert_engine_sqlserver.py tests/test_sqlserver_business_layout.py tests/test_prd_instock_write_validation.py tests/test_ap_payable_field_mapping.py -q`
  - Result from Comet build guard: PASS.
- Additional verification runs:
  - Purchase instock focused tests: `6 passed`.
  - SQL Server upsert/layout tests: `20 passed`.
  - Adjacent form regression tests: `10 passed`.
- 2026-07-08 real Kingdee dry-run and SQL Server write verification:
  - `STK_InStock` query with `Limit=10` returned 10 rows.
  - `FSrcEntrySeq` was rejected by Kingdee metadata; `FInStockEntry_fseq` was accepted and matched `FInStockEntry_FSEQ` for the sampled rows.
  - `FInStockEntry_fseq` now feeds target column `FSRCENTRYSEQ`.
  - SQL Server target table `dbo.STK_InStock` did not exist before the write verification, so the non-report business table and unique index `UX_STK_InStock_fentryid` were created.
  - Before write: 0 matching `FENTRYID` rows. Writer result: 10 rows. After write: 10 matching rows and 10 total rows.
  - SQL Server log evidence: `成功插入/更新 10 条记录 (SQL Server)`.
- 2026-07-08 expanded incremental write verification:
  - `STK_InStock` query with `Limit=1000` returned 1000 rows.
  - Prepared rows: 1000 valid, 0 invalid/skipped, 0 duplicate source `FENTRYID`.
  - Before expanded write: target total rows 10, matching rows 10.
  - First write result: writer returned 1000, target total rows became 1000, matching rows became 1000, and total row delta was +990.
  - Idempotency check: second write returned 1000, target total rows stayed 1000, matching rows stayed 1000, and total row delta was 0.
  - Target validation: 0 rows with missing key fields, 0 duplicate `FENTRYID` groups, and `FSRCENTRYSEQ` values were populated from `FInStockEntry_fseq`.
  - Command stdout showed `成功插入/更新 1000 条记录 (SQL Server)` twice; `logs/app.log` did not capture this run because the verification harness logged to stdout instead of the application file handler.
- 2026-07-08 formal incremental sync entrypoint verification:
  - Ran the normal `run_sync` / `DataSyncManager.sync_data` path for `采购入库单` with mode `incremental`, with application file logging enabled.
  - `run_id=453d49a964dd476ba5ab49c5dc11d263`; sync status was `success`.
  - Incremental filter used `FModifyDate`; Kingdee returned 0 new rows, so `dbo.STK_InStock` remained at 1000 rows.
  - SQL Server `sync_runs` recorded the run with `total_records=0`, `success_count=1`, and `failure_count=0`.
  - SQL Server `sync_logs` recorded `table_name=STK_InStock`, `record_count=0`, and `status=success`.
  - Local `logs/sync_stats.db` recorded both `run_stats` and `form_stats` for the same run; `form_stats.table_name` was empty in the current implementation.
  - `logs/app.log` captured 19 matching lines and `logs/app.jsonl` captured 5 matching audit/completion lines for the run.
  - No pending checkpoint files remained after the successful 0-row incremental sync.
- 2026-07-08 `sync_stats.form_stats.table_name` fix verification:
  - Commit `c073c3b0` updates local stats recording to fall back to `DataSyncManager.table_mapping` when a form result omits `table_name`.
  - Regression test first reproduced the empty `table_name`, then passed after the fix.
  - Focused regression command result: `27 passed in 0.39s`.
  - Formal entrypoint re-run `run_id=da2a2b6a0c5f40b5a86cd39a8174f026` succeeded with 0 new rows, and `logs/sync_stats.db.form_stats.table_name` recorded `STK_InStock`.
  - `dbo.STK_InStock` remained at 1000 rows after the re-run.

## Requirement Mapping

### 采购入库单可配置同步

- Evidence:
  - `src/config/form-queries.json` registers `采购入库单` with `FormId=STK_InStock`.
  - `src/config/tables.json` maps `采购入库单` to `STK_InStock` and `insert_purchase_instock`.
  - `config.example.ini` includes `stk_instock` in `force_staging_tables`.
  - `tests/test_config_manager.py` validates config, table mapping, and staging list parsing.

### 采购入库单基础明细字段

- Evidence:
  - `src/core/sales_writer.py` writes the basic detail columns to `STK_InStock`.
  - `src/core/mysql_manager.py` maps `FID`, entry id, sequence, bill no, date, status, supplier, purchase org, material, quantity, source bill, source entry, and modify date.
  - Real dry-run calibrated the source-entry sequence path to `FInStockEntry_fseq`; the writer also keeps `FSrcEntrySeq`, `FSRCENTRYSEQ`, and `FInStockEntry_FSEQ` aliases for compatibility.
  - `tests/test_purchase_instock_write_validation.py` covers normal field conversion.

### 分录级幂等写入

- Evidence:
  - `src/core/mysql_manager.py` maps `stk_instock` primary key to `FENTRYID`.
  - `src/core/upsert_engine_sqlserver.py` requires `FID` and `FENTRYID` for `stk_instock`.
  - `src/tools/sqlserver_business_layout.py` defines `UX_STK_InStock_fentryid`.
  - `tests/test_upsert_engine_sqlserver.py` verifies blank entry ids are filtered.
  - Expanded SQL Server verification wrote the same 1000-row sample twice; the second write left `dbo.STK_InStock` at 1000 rows with 0 duplicate `FENTRYID` groups.

### 无效采购入库单记录处理

- Evidence:
  - `_prepare_purchase_instock_data` skips missing `FID`, missing entry id, and blank bill no with warning logs and invalid-row accounting.
  - `tests/test_purchase_instock_write_validation.py` covers blank entry id and blank bill no.

### SQL Server 写入验证

- Evidence:
  - Writer registry tests confirm `insert_purchase_instock` is registered and bound to the expected callable.
  - SQL Server upsert and layout tests pass.
  - Real write verification created `dbo.STK_InStock` and `UX_STK_InStock_fentryid`, inserted/updated 10 sampled rows, and confirmed 10 matching target rows after the write.
  - Expanded write verification inserted/updated 1000 sampled rows, confirmed 0 invalid rows, 0 failed rows, 0 duplicate source keys, 0 duplicate target `FENTRYID` groups, and repeat-write row delta 0.
  - Formal incremental sync entrypoint verification recorded success in `sync_runs`, `sync_logs`, `logs/sync_stats.db`, `logs/app.log`, and `logs/app.jsonl`.
  - Local form stats now record `table_name=STK_InStock` for purchase instock formal sync runs.

## Issues

### CRITICAL

None.

### WARNING

- Existing dirty worktree content was intentionally included in this change after explicit user confirmation. `src/core/mysql_manager.py` also contains previously existing production-order related changes that were committed during Task 4. This is documented in `openspec/changes/add-purchase-instock-sync/tasks.md` and `openspec/changes/add-purchase-instock-sync/verification-report.md` (reason: preserve user-authorized work while keeping provenance visible).

### SUGGESTION

None.

## Final Assessment

No critical issues found. Implementation matches the OpenSpec capability, follows the approved technical design, and has focused regression evidence. Ready for archive after branch handling.
