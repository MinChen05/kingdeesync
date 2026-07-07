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

### 无效采购入库单记录处理

- Evidence:
  - `_prepare_purchase_instock_data` skips missing `FID`, missing entry id, and blank bill no with warning logs and invalid-row accounting.
  - `tests/test_purchase_instock_write_validation.py` covers blank entry id and blank bill no.

### SQL Server 写入验证

- Evidence:
  - Writer registry tests confirm `insert_purchase_instock` is registered and bound to the expected callable.
  - SQL Server upsert and layout tests pass.
  - Real write verification created `dbo.STK_InStock` and `UX_STK_InStock_fentryid`, inserted/updated 10 sampled rows, and confirmed 10 matching target rows after the write.

## Issues

### CRITICAL

None.

### WARNING

- Existing dirty worktree content was intentionally included in this change after explicit user confirmation. `src/core/mysql_manager.py` also contains previously existing production-order related changes that were committed during Task 4. This is documented in `openspec/changes/add-purchase-instock-sync/tasks.md` and `openspec/changes/add-purchase-instock-sync/verification-report.md` (reason: preserve user-authorized work while keeping provenance visible).

### SUGGESTION

- For production-scale enablement, run a larger incremental batch after confirming the first 10-row write sample with the business owner (reason: the target field path has been calibrated, but broader data distribution may expose optional/custom fields).

## Final Assessment

No critical issues found. Implementation matches the OpenSpec capability, follows the approved technical design, and has focused regression evidence. Ready for archive after branch handling.
