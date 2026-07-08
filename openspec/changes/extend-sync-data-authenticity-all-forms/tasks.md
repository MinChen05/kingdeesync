## 1. Mapping Discovery

- [ ] 1.1 Implement a read-only schema discovery report that joins `form-queries.json`, `tables.json`, current database columns, and existing `AUDIT_SPECS` coverage。（原因：先形成字段证据，避免人工猜测）
- [ ] 1.2 Output `logs/sync_data_authenticity/authenticity_mapping_draft.csv` with form, table, FormId, identity candidates, blocker candidates, warning candidates, missing DB fields, and missing API fields。（原因：给人工审阅统一口径）
- [ ] 1.3 Add tests for discovery using fixture configs and fake database columns。（原因：锁定报告格式和只读行为）

## 2. All-Form Specs

- [ ] 2.1 Extend `AuthenticitySpec` to support unconfirmed identity keys and snapshot identity keys without marking rows eligible for automated rehydration。（原因：部分表单身份键需要人工确认）
- [ ] 2.2 Add specs for sales, production, payable/receivable, subcontract, delivery notice, inventory, master data, and BOM forms。（原因：覆盖所有同步表单）
- [ ] 2.3 Keep `科目余额表` out of first-batch field-level audit and report it as unsupported with a reason。（原因：报表接口身份模型不同）

## 3. Batched Dry-run Reports

- [ ] 3.1 Add form batch definitions for business documents, production documents, and snapshot/master-data forms。（原因：分批降低 API 超时和排障成本）
- [ ] 3.2 Extend the audit script to accept batch names and write per-batch summary/detail/blockers CSV files。（原因：全表单 dry-run 需要可定位报告）
- [ ] 3.3 Ensure all dry-run and discovery paths are read-only and do not call SQL Server write methods。（原因：本 change 不允许写生产数据）

## 4. Documentation And Verification

- [ ] 4.1 Update `docs/sync-data-authenticity.md` with all-form mapping fields, batch commands, and unsupported-form handling。（原因：操作人员需要明确执行顺序）
- [ ] 4.2 Run targeted tests and `python -m compileall -q src tests scripts`。（原因：验证实现没有语法和回归问题）
- [ ] 4.3 Execute discovery dry-run only and attach report paths in the verification report。（原因：本阶段先交付映射报告，不执行写库）
