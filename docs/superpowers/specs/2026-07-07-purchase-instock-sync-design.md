---
comet_change: add-purchase-instock-sync
role: technical-design
canonical_spec: openspec
archived-with: 2026-07-08-add-purchase-instock-sync
status: final
---

# 采购入库单同步技术设计

## 结论

本次实现采用“配置注册 + 现有 writer registry + SQL Server staging/upsert”的最小扩展方案新增“采购入库单”同步能力（原因：项目已有表单同步、分页拉取、写入分发、重试、日志和 staging/upsert 能力，复用现有链路风险最低）。采购入库单先限定为基础明细同步，字段以后续 dry-run 响应校准（原因：不同金蝶环境可能存在字段路径、大小写和自定义字段差异）。

## 架构方案

采购入库单进入现有同步链路：

1. `src/config/form-queries.json` 新增“采购入库单”，`FormId` 初始使用 `STK_InStock`，`FieldKeys` 先覆盖基础明细字段（原因：让同步入口通过统一配置发现该表单）。
2. `src/config/tables.json` 新增“采购入库单”到 SQL Server 目标表与 writer 方法的映射（原因：现有 `FormSyncRunner` 依赖该映射选择写入方法）。
3. `src/core/writers_registry.py` 注册 `insert_purchase_instock`（原因：统一 writer 分发，避免在 runner 中增加表单特判）。
4. writer 复用 `MySQLManager._batch_insert` 与 `_prepare_purchase_instock_data` 做批量写入和字段转换（原因：保持与采购订单、生产入库单、应付单一致的写入行为）。
5. SQL Server upsert/staging 主键映射补充采购入库单分录级幂等键（原因：采购入库单一单多行，单据头 `FID` 不能唯一表示明细）。

## 数据流

```text
form-queries.json
  -> ConfigManager
  -> FormSyncRunner
  -> KingdeeAPI.query_data(FormId=STK_InStock)
  -> writers_registry.insert_purchase_instock
  -> MySQLManager._prepare_purchase_instock_data
  -> _batch_insert / staging / upsert
  -> SQL Server 采购入库单目标表
```

## 字段与表设计

基础明细字段至少包含：

- `FID`：单据内码（原因：用于追溯单据头）。
- 分录主键：优先使用 dry-run 返回的采购入库单分录内码字段，例如 `FInStockEntry_FENTRYID` 或等价字段（原因：用于分录级幂等）。
- 分录序号：用于人工核对和兜底定位（原因：同一单据多行时便于排查）。
- `FBillNo`、`FDate`、`FDocumentStatus`、供应商、采购组织、物料编码、物料名称、实收数量、源单号、源单行、`FModifyDate`（原因：覆盖采购入库基础业务追踪所需字段）。

目标表建议先按业务单据独立建表，不与采购订单或生产入库单混表（原因：不同单据语义、字段和生命周期不同，混表会增加查询和维护成本）。若实施时采用 `STK_InStock` 作为表名，应与现有大小写表名兼容；若采用小写表名，应同步更新配置、staging 表名和索引映射（原因：项目内同时存在金蝶原始表名和小写业务表名）。

## 错误处理

- 缺少 `FID`、分录主键或单号时跳过该行并记录 warning，日志包含可定位字段（原因：避免无效数据破坏唯一键或造成重复写入）。
- 金蝶字段缺失时优先通过 dry-run 校准配置，不在代码中硬编码未经验证的字段假设（原因：防止字段路径幻觉）。
- SQL Server 写入失败沿用现有 writer/upsert 异常处理和日志体系（原因：保持错误表现与其他表单一致）。

## 测试策略

- 配置测试：确认“采购入库单”可从内置查询和表映射中加载（原因：表单必须先能被同步入口发现）。
- writer registry 测试：确认 `insert_purchase_instock` 已注册（原因：避免运行时找不到 writer）。
- 字段准备测试：覆盖正常记录、大小写兼容、空分录主键、空单号、空 `FID`（原因：这些是最容易导致脏数据或重复写入的边界）。
- upsert/staging 测试：确认采购入库单使用分录级幂等键（原因：重复同步必须更新而不是重复插入）。
- dry-run：输出请求字段、样例响应、预计写入量、跳过量和 SQL Server 写入日志预期（原因：字段以真实金蝶响应为准）。

## 数据库影响

本次允许新增非报表业务表和必要索引，不修改报表相关表结构（原因：采购入库单是业务单据，不属于报表表结构禁改范围）。如果实施中涉及主键、唯一键或字段顺序调整，必须先保留数据并校验行数（原因：项目数据库规则要求结构调整不得破坏既有数据）。

## 既有未提交改动处理

用户已确认将当前工作区既有未提交改动并入本 change。实施阶段必须复核 `assets/styles.css`、`src/core/mysql_manager.py`、诊断脚本和日志中心截图的影响范围，并避免覆盖其中与本次采购入库单无关但用户希望保留的内容（原因：dirty worktree 已被明确纳入当前 change，验证报告需要说明其影响）。

## 待确认事项

- 采购入库单目标环境真实字段路径需通过 dry-run 校准（原因：当前设计不能假定所有字段在目标账套中完全一致）。
- 目标表最终命名需在实施时结合现有表名风格确定（原因：命名会影响 staging 配置、索引映射和 SQL Server 查询习惯）。
