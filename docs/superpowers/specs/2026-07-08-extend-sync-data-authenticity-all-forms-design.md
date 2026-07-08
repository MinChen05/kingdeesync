---
comet_change: extend-sync-data-authenticity-all-forms
role: technical-design
canonical_spec: openspec
---

# 全同步表单真实性校验扩展设计

## 背景

现有真实性校验已覆盖采购订单和采购入库单，核心能力包括字段比较器、声明式 `AuthenticitySpec`、行级分类、CSV summary/detail 报告，以及 SQL Server 大批量参数拆批。（原因：这些能力可直接复用于更多同步表单）

全同步表单的字段来源分散在 `src/config/form-queries.json`、`src/config/tables.json`、SQL Server 当前表结构和 writer 准备函数中。若直接手写所有表单规格，容易出现 DB 字段名或 API 字段名错配，导致审计假通过或误阻断。（原因：真实性校验必须先证明字段映射真实）

## 目标

- 新增只读 schema discovery，输出全同步表单真实性映射草案。（原因：实现前先形成可审阅字段证据）
- 扩展 `AuthenticitySpec`，支持全同步表单、待确认身份键、快照组合键和 unsupported 表单。（原因：不同表单身份模型不同）
- 增加分批 dry-run 能力，输出 summary/detail/blockers 报告。（原因：全表单一次执行不利于排障）
- 明确所有 discovery 和 dry-run 路径只读，不调用 SQL Server 写入方法。（原因：本 change 不允许写生产数据）

## 非目标

- 不执行回灌、补写、删除或任何 SQL Server 写操作。
- 不修改数据库 schema、主键、唯一键、字段顺序或报表表结构。
- 不把科目余额表纳入第一批字段级真实性审计。（原因：报表接口与行身份模型不同）
- 不把描述、规格、条码、自定义文本等弱字段作为第一版阻断项。（原因：先控制噪声）

## 架构

新增一个 discovery 层，与现有审计层保持分离：

```text
form-queries.json ─┐
tables.json        ├─ discovery report ── authenticity_mapping_draft.csv
SQL Server columns ┤
AUDIT_SPECS        ┘

authenticity_mapping_draft.csv + reviewed specs
        │
        ▼
AUDIT_SPECS / FORM_BATCHES ── audit script ── summary/detail/blockers
```

Discovery 只负责发现和报告，不参与行级差异判定。行级差异仍由 `src/core/sync_data_authenticity.py` 的比较器和分类模型承担。（原因：报告生成与真实性判定边界清晰）

## 数据模型调整

在现有 `AuthenticitySpec` 基础上补充可选元数据：

- `identity_confirmed: bool`：身份键是否已确认；未确认时可报告但不得自动回灌。（原因：防止错身份写入）
- `unsupported_reason: str | None`：暂不支持审计的表单原因，例如科目余额表。（原因：让跳过项可审计）
- `batch: str`：所属 dry-run 批次，例如 `business_documents`、`production_documents`、`snapshot_master_data`。（原因：分批执行）
- `identity_kind: str`：`entry`、`master`、`snapshot`、`report`。（原因：单据分录、主数据和快照的身份模型不同）

不引入数据库表保存这些元数据，全部保留在代码配置和 CSV 报告中。（原因：当前不需要持久化 schema）

## 字段分组规则

阻断字段：
- 身份键、单号、分录序号、物料、客户/供应商、组织、核心数量/金额。（原因：这些字段错配会造成业务事实错误）

Warning 字段：
- 单据日期、创建日期、修改日期、审核日期、状态、关闭状态。（原因：这些字段可能随业务流程变化）

Unsupported/待确认：
- 科目余额表、缺少明确身份键的表单、DB 列缺失或 API 字段缺失的候选字段。（原因：避免不可靠字段进入阻断项）

## 表单批次

第一批 `business_documents`：
- 销售订单、销售出库单、销售退货单、发货通知单、采购订单、采购入库单、委外订单、应付单、应收单。

第二批 `production_documents`：
- 生产入库单、生产订单主表、生产订单明细、生产用料清单主表、生产用料清单明细表、预测订单。

第三批 `snapshot_master_data`：
- 即时库存、客户资料、物料、仓库、物料清单、物料清单子项。

暂缓：
- 科目余额表。（原因：报表类接口需要单独身份模型和参数校验）

## Discovery 报告

输出路径：

```text
logs/sync_data_authenticity/authenticity_mapping_draft.csv
```

字段：

- `form`
- `table`
- `form_id`
- `batch`
- `identity_kind`
- `identity_confirmed`
- `db_identity`
- `api_identity`
- `blocker_fields`
- `warning_fields`
- `api_field_keys`
- `db_columns`
- `missing_db_fields`
- `missing_api_fields`
- `unsupported_reason`

如果数据库连接不可用，discovery 可以使用空 DB 列集合输出 `missing_db_fields`，但必须在报告里标记 `db_columns_available=false`。（原因：本地测试和生产 discovery 都需要可运行）

## Dry-run 报告

现有 detail/summary 保留，新增 blockers-only 报告：

- `sync_data_authenticity_summary.csv`
- `sync_data_authenticity_detail.csv`
- `sync_data_authenticity_blockers.csv`

`blockers.csv` 仅包含 `missing_db`、`missing_api`、`identity_mismatch`、`dimension_mismatch`、`value_mismatch`。（原因：人工优先处理阻断项）

## 测试策略

- 单元测试 discovery：使用 fixture configs 和 fake DB columns，覆盖 supported、unconfirmed、unsupported、missing fields。（原因：报告格式和字段判定必须稳定）
- 单元测试 spec 元数据：覆盖 `identity_confirmed=false` 时不可自动回灌，`identity_kind=snapshot` 的即时库存组合键。（原因：防止未确认身份进入回灌候选）
- 脚本测试：覆盖 `--discover`、`--batch`、blockers CSV 输出，不连接真实 DB/API。（原因：测试必须可重复）
- 回归测试：保留采购订单/采购入库单 1589 行通过的现有用法，不改变命令兼容性。（原因：已有能力不能回退）

## 执行边界

实现阶段允许执行：

```bash
python scripts/maintenance/audit_sync_data_authenticity.py --discover --out-dir logs/sync_data_authenticity
python -m pytest tests/test_sync_data_authenticity.py tests/test_audit_sync_data_authenticity_script.py -q
python -m compileall -q src tests scripts
```

实现阶段不允许执行任何回灌写库命令。（原因：本 change 只交付映射报告和 dry-run 计划）
