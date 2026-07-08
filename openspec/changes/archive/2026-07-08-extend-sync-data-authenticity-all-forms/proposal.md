## Why

当前同步数据真实性校验只覆盖采购订单和采购入库单，无法对销售、生产、应收应付、库存、基础资料等已同步表单形成统一 dry-run 证据。（原因：历史差异检查如果只看 0/非 0，会遗漏错单、错分录、错物料、错往来方等真实性风险）

需要先扩展 schema discovery 和映射报告能力，再逐步把所有同步表单纳入真实性 dry-run，不执行任何写库。（原因：全表单字段口径复杂，先生成映射证据能降低误报和错配风险）

## What Changes

- 增加全同步表单的真实性字段映射设计，覆盖身份键、阻断字段、warning 字段和暂缓字段。（原因：不同表单真实性字段不同，需要显式配置）
- 增加 schema discovery 产物，自动汇总 `form-queries.json`、`tables.json`、数据库列和现有 `AuthenticitySpec` 覆盖情况。（原因：避免靠人工猜测 DB 字段名和 API 字段名）
- 扩展 dry-run 执行计划，按业务批次输出 summary/detail/blockers 报告。（原因：全量一次执行风险高，分批更容易定位问题）
- 明确第一阶段不写 SQL Server、不执行自动回灌、不处理科目余额表报表类深度校验。（原因：本 change 目标是验证口径和报告，不改变生产数据）

## Capabilities

### New Capabilities

### Modified Capabilities

- `sync-data-authenticity`: 将真实性校验从采购订单和采购入库单扩展到所有同步表单的 schema discovery、映射报告和分批 dry-run 计划。

## Impact

- 影响 `src/core/sync_data_authenticity.py` 的表单规格配置和报告模型。
- 影响 `scripts/maintenance/audit_sync_data_authenticity.py` 或新增 discovery 脚本，用于输出映射报告和分批 dry-run 输入。
- 影响 `docs/sync-data-authenticity.md`，需要补充全表单 dry-run 使用说明。
- 不新增数据库结构，不修改报表表结构，不写生产数据。（原因：当前阶段只读发现和审计）
