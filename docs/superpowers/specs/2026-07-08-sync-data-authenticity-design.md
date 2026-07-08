---
comet_change: verify-sync-data-authenticity
role: technical-design
canonical_spec: openspec
archived-with: 2026-07-08-verify-sync-data-authenticity
status: final
---

# 同步数据真实性校验技术设计

## 目标

建立一个可复用的真实性审计门禁：在历史差异回灌前后，用同一批业务身份从数据库和金蝶 API 取当前值，按配置比对身份键、阻断字段、warning 字段和修复目标字段。（原因：只证明数量不为 0 不足以证明数据真实）

第一版覆盖 `采购入库单` 和 `采购订单`，日期与状态差异只作为 warning，不阻断自动回灌。（原因：日期和状态可能随业务流程变化，第一版直接阻断会误报）

## 技术方案

新增一个独立核心模块 `src/core/sync_data_authenticity.py`，不要把审计逻辑塞进 `mysql_manager.py` 或 writer。（原因：审计是读源和比较职责，写入器只负责落库）

模块包含四类对象：

- `AuthenticityField`：描述一个字段如何比较，包括 DB 字段、API 字段、类型、严重级别和容忍度。
- `AuthenticitySpec`：描述一个表单的身份键、阻断字段、warning 字段、修复目标字段、表名和 Form 查询配置。
- `AuthenticityAuditor`：接收 DB 行和 API 行，输出字段级 `AuditDifference` 与行级状态。
- `AuditReportWriter`：写出 summary/detail CSV，供 dry-run、execute 前门禁和 verify 复核复用。

比较器使用标准库 `Decimal`、`datetime` 和字符串归一化，不新增第三方依赖。（原因：项目已有依赖足够，避免部署复杂度）

## 字段分级

阻断字段：

- 身份键：`FID + FENTRYID`
- 采购入库单：`FBILLNO`、`FSEQ`、`FMATERIALNUMBER`、`FSUPPLIERNAME`、`FREALQTY`
- 采购订单：`FBillNo`、`FNUMBER`、`FSupplier`、`FQTY`

warning 字段：

- 采购入库单：`FDATE`、`FDOCUMENTSTATUS`、`FModifyDate`
- 采购订单：`FDocumentStatus`、`FCreateDate`、`FModifyDate`、`FApproveDate`

行级状态优先级：

1. `missing_db`
2. `missing_api`
3. `identity_mismatch`
4. `dimension_mismatch`
5. `value_mismatch`
6. `warning_only`
7. `passed`

自动回灌只允许处理没有 `missing_*`、`identity_mismatch`、`dimension_mismatch` 的行。（原因：错身份或错维度写入会污染业务数据）

## 数据流

```text
历史差异 CSV / 指定表单范围
        |
        v
目标身份集合 FID+FENTRYID
        |
        +--> SQL Server 当前 DB 行
        |
        +--> Kingdee ExecuteBillQuery 当前 API 行
        |
        v
AuthenticityAuditor 字段级比较
        |
        +--> dry-run summary/detail CSV
        |
        +--> execute 门禁候选 key 列表
        |
        +--> verify summary/detail CSV
```

## 接口边界

第一版以脚本入口提供能力：

```text
scripts/maintenance/audit_sync_data_authenticity.py --forms 采购入库单,采购订单 --source logs/all_sync_document_zero_vs_kingdee_detail.csv --mode dry-run
scripts/maintenance/audit_sync_data_authenticity.py --forms 采购入库单,采购订单 --source logs/all_sync_document_zero_vs_kingdee_detail.csv --mode verify
```

脚本只负责读取目标、调用 auditor、写报告；不直接执行回灌。（原因：回灌应继续走现有 writer/upsert 路径，真实性审计只提供门禁证据）

## 测试策略

- `tests/test_sync_data_authenticity.py` 覆盖字段比较器：decimal、日期、字符串、空值、容忍度。
- 覆盖行级分类：缺 DB、缺 API、阻断字段不一致、warning-only、passed。
- 覆盖采购入库单和采购订单配置字段，确保阻断和 warning 分层正确。
- `tests/test_audit_sync_data_authenticity_script.py` 用伪造 DB/API 行测试 dry-run 报告结构。

真实生产数据只用于人工执行脚本生成 CSV，不写入测试 fixture。（原因：避免业务数据泄露）

## 风险与取舍

- 第一版不做 GUI 集成，只提供脚本和 CSV。（原因：先把真实性口径跑通）
- 第一版不自动补插 `missing_db` 行。（原因：补插是更高风险的数据修复动作）
- 第一版只覆盖采购链路两张表。（原因：字段真实性配置需要逐表校准）
