# 同步数据真实性校验

## 适用范围

当前能力覆盖采购入库单、采购订单，并已扩展全同步表单的真实性映射 discovery。身份键、单号、分录、物料、往来方、数量和核心金额为阻断项；日期和状态为 warning。

Discovery 只读取配置和 SQL Server 元数据，不写 SQL Server。（原因：先生成字段映射证据，再决定哪些表单可进入正式 dry-run）

## Mapping Discovery

```bash
python scripts/maintenance/audit_sync_data_authenticity.py --discover --out-dir logs/sync_data_authenticity
```

输出：

- `authenticity_mapping_draft.csv`: 全同步表单映射草案，包含表单、目标表、金蝶 FormId、身份键、阻断字段、warning 字段、缺失 DB 字段、缺失 API 字段、unsupported 原因。

关键字段：

- `identity_confirmed`: `true` 表示身份键已确认；`false` 表示该表单只进入报告，不应进入自动回灌候选。
- `identity_kind`: `entry` 为单据分录，`master` 为基础资料，`snapshot` 为快照，`report` 为报表。
- `unsupported_reason`: 暂不支持字段级真实性审计的原因，例如 `report_form_requires_separate_design`。
- `missing_db_fields` / `missing_api_fields`: 当前 spec 需要但目标侧未发现的字段。

## All-Form Dry-run Batches

批次命令：

```bash
python scripts/maintenance/audit_sync_data_authenticity.py --batch business_documents --source logs/all_sync_document_zero_vs_kingdee_detail.csv --mode dry-run --out-dir logs/sync_data_authenticity/business_documents
python scripts/maintenance/audit_sync_data_authenticity.py --batch production_documents --source logs/all_sync_document_zero_vs_kingdee_detail.csv --mode dry-run --out-dir logs/sync_data_authenticity/production_documents
python scripts/maintenance/audit_sync_data_authenticity.py --batch snapshot_master_data --source logs/all_sync_document_zero_vs_kingdee_detail.csv --mode dry-run --out-dir logs/sync_data_authenticity/snapshot_master_data
```

批次说明：

- `business_documents`: 销售、采购、应收应付、委外、发货通知单。
- `production_documents`: 生产订单、生产入库、生产用料清单、预测订单。
- `snapshot_master_data`: 即时库存、客户资料、物料、仓库、BOM。

显式 `--forms` 优先于 `--batch`。（原因：兼容已有采购两单命令，也支持临时单表复核）

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
- `sync_data_authenticity_blockers.csv`: 仅包含阻断状态，便于优先人工处理。

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

## Unsupported Forms

- `科目余额表`: 第一批不做字段级真实性审计，discovery 中标记 `report_form_requires_separate_design`。（原因：报表接口参数和行身份模型不同于普通单据）
