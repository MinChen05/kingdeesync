# 同步数据真实性校验

## 适用范围

第一版覆盖采购入库单和采购订单。身份键、单号、分录、物料、往来方、数量为阻断项；日期和状态为 warning。

## Dry-run

```bash
python scripts/maintenance/audit_sync_data_authenticity.py --forms 采购入库单,采购订单 --source logs/all_sync_document_zero_vs_kingdee_detail.csv --mode dry-run
```

## Verify

```bash
python scripts/maintenance/audit_sync_data_authenticity.py --forms 采购入库单,采购订单 --source logs/all_sync_document_zero_vs_kingdee_detail.csv --mode verify
```

## 报告文件

默认输出目录为 `logs/sync_data_authenticity`。

- `sync_data_authenticity_summary.csv`: 按状态汇总行数和可回灌行数。
- `sync_data_authenticity_detail.csv`: 展开到字段级差异，包含表单、身份键、状态、字段、严重级别、数据库值和金蝶值。

## 状态含义

- `passed`: 阻断字段和 warning 字段均一致。
- `warning_only`: 阻断字段一致，日期或状态存在差异。
- `dimension_mismatch`: 单号、分录、物料或往来方等阻断维度不一致，禁止自动回灌。
- `value_mismatch`: 数量不一致，但身份和维度通过，可进入回灌候选。
- `identity_mismatch`: `FID/FENTRYID` 与金蝶分录身份不一致，禁止自动回灌。
- `missing_db`: 数据库缺行。
- `missing_api`: 金蝶缺行。

## 操作顺序

1. 先执行 dry-run，查看 summary 中的阻断项行数。
2. 只对 `passed`、`warning_only` 和 `value_mismatch` 且业务确认可修复的目标执行回灌。
3. 回灌后对同一批 source 执行 verify，要求阻断项通过；日期和状态差异继续作为 warning 跟踪。

## 预期日志变化

当前脚本只生成审计报告，不写 SQL Server，因此不会出现 SQL Server 写入日志。后续回灌脚本接入该门禁后，应在写入前打印真实性审计 summary，并跳过 `dimension_mismatch`、`identity_mismatch`、`missing_db`、`missing_api` 行。
