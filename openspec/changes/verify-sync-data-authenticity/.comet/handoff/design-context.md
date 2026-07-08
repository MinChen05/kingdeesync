# Comet Design Handoff

- Change: verify-sync-data-authenticity
- Phase: design
- Mode: compact
- Context hash: 51812c578b8ce4f94dcf8a7e8e79fb4f77203d51c756fdf6ea024473103b96b0

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/verify-sync-data-authenticity/proposal.md

- Source: openspec/changes/verify-sync-data-authenticity/proposal.md
- Lines: 1-30
- SHA256: d59f8542b1ea8e58198cc6a754ae718f0b86d56d7e2e3647b12266b7a727c0d9

```md
## Why

现有历史差异处理主要围绕“数据库为 0、金蝶非 0”的数量字段校验，能够发现 decimal 写 0 问题，但不能证明回灌后的数据整体真实。（原因：数量一致必须建立在同一单据、同一分录、同一物料、同一往来方和同一日期等业务维度一致的前提上）

需要新增同步数据真实性校验能力，在执行批量回灌或确认同步结果前，系统应能按表单定义对数据库记录与金蝶源记录进行字段级、行级和业务维度级比对，并输出可追溯报告。（原因：避免只修正数量字段，却掩盖主键错配、分录错配或物料/供应商/客户错配）

## What Changes

- 新增数据真实性审计能力：按配置定义每个同步表单的身份键、业务维度字段、数值字段、日期字段和允许误差。（原因：不同单据的真实性字段不同，必须配置化而不是硬编码）
- 第一阶段优先覆盖 `采购入库单` 与 `采购订单`，后续扩展到发货通知单、销售订单、应收/应付、生产相关单据和即时库存。（原因：先校验刚回灌过的采购链路，降低一次性覆盖风险）
- 审计报告必须区分 `missing_db`、`missing_api`、`identity_mismatch`、`dimension_mismatch`、`value_mismatch`、`date_mismatch` 和 `passed`。（原因：不同差异类型对应不同处理方式）
- 回灌前 dry-run 必须输出真实性校验摘要和明细，不得只输出待更新数量。（原因：批量修复前必须确认目标行身份真实）
- 回灌后 verify 必须重新比对真实性字段，只有所有必检字段通过才标记为已修复。（原因：写入成功不等于业务真实）
- 不改变数据库结构，不引入新的外部依赖，不自动清空或删除生产数据。（原因：本次目标是审计与安全回灌门禁）

## Capabilities

### New Capabilities

- `sync-data-authenticity`: 同步数据真实性审计与回灌门禁，覆盖数据库记录与金蝶源记录的身份、维度、数值和日期一致性校验。

### Modified Capabilities

- 无。（原因：现有规格中尚无通用同步真实性审计能力）

## Impact

- 影响范围：同步审计脚本/工具、采购入库单和采购订单的回灌前后校验流程、相关测试与文档。
- 数据库影响：不涉及结构变更；执行审计时只读，执行回灌时仍使用现有 upsert 写入路径。（原因：保留现有安全写入边界）
- 运维影响：会新增 CSV/日志报告，报告用于人工确认和后续批量回灌决策。（原因：真实性校验需要可审计证据）
```

## openspec/changes/verify-sync-data-authenticity/design.md

- Source: openspec/changes/verify-sync-data-authenticity/design.md
- Lines: 1-57
- SHA256: e8680815ef775bcbb199afe693c3adc8a29ea0129a561d057fa37abc95f36766

```md
## Overview

本变更引入“同步数据真实性审计”作为回灌前后的门禁。真实性不再只看目标数量是否从 0 变为非 0，而是按表单定义比对数据库记录与金蝶源记录是否代表同一业务事实。（原因：错误数量、错分录、错物料都可能让报表看似修复但业务仍失真）

## Validation Model

每个表单定义一组校验字段：

- 身份键：定位同一行，例如 `FID + FENTRYID`。（原因：防止跨单据或跨分录错配）
- 业务维度：单号、分录序号、物料编码、供应商/客户、组织等。（原因：确认主键匹配之外的业务身份一致）
- 数值字段：数量、金额、价格等，支持 decimal 精度容忍。（原因：避免浮点格式差异导致误报）
- 日期字段：单据日期、修改日期等，支持统一格式化到秒或日期，第一版作为 warning 字段。（原因：API 与 SQL Server 日期精度可能不同，且日期可能被后续业务动作更新）
- 可选字段：部分历史表缺列或字段业务上不稳定时可标为 warning。（原因：先覆盖关键真实性，不因弱字段阻断核心修复）
- 严重级别：`blocker` 字段阻断自动回灌，`warning` 字段只进入报告不阻断。（原因：第一版需要控制误报和误阻断）

## Initial Scope

第一阶段覆盖：

### 采购入库单

- 身份键：`FID + FENTRYID` 对 `FID + FInStockEntry_FENTRYID`
- 阻断字段：`FBILLNO`、`FSEQ`、`FMATERIALNUMBER`、`FSUPPLIERNAME`、`FREALQTY`
- warning 字段：`FDATE`、`FDOCUMENTSTATUS`、`FModifyDate`

### 采购订单

- 身份键：`FID + FENTRYID` 对 `FID + FPOOrderEntry_FENTRYID`
- 阻断字段：`FBillNo`、`FNUMBER`、`FSupplier`、`FQTY`
- warning 字段：`FDocumentStatus`、`FCreateDate`、`FModifyDate`、`FApproveDate`

## Workflow

1. 从待审计来源读取目标行：可以是历史差异 CSV，也可以是按表单/时间范围从数据库抽样。（原因：既支持当前回灌，也支持后续主动巡检）
2. 按身份键批量查询数据库当前值。（原因：避免使用旧报告里的过期数据）
3. 按金蝶 FormId 和身份键批量回查 API 当前值。（原因：所有判断以金蝶源数据为准）
4. 对每行生成字段级校验结果，输出明细 CSV 和汇总 CSV。（原因：差异需要可追溯到字段）
5. dry-run 阶段只生成报告，不写库。（原因：审计和修复职责分离）
6. 回灌阶段只允许处理 `passed_blockers` 且目标修复字段存在差异的行。（原因：禁止在身份或关键业务维度不真实时写入）
7. verify 阶段重新执行真实性审计，要求阻断字段全部通过；warning 字段保留在报告中供人工判断。（原因：写入成功必须有二次证据，同时避免日期/状态误阻断）

## Error Handling

- API 查不到：标记 `missing_api`，不得回灌。（原因：没有源数据不能证明真实）
- DB 查不到：标记 `missing_db`，不得回灌，除非后续设计明确支持补插。（原因：当前目标是修复已有同步行）
- 身份字段不一致：标记 `identity_mismatch`，阻断回灌。（原因：错身份写入风险最高）
- 业务维度不一致：标记 `dimension_mismatch`，阻断回灌或人工复核。（原因：可能是映射错误或源数据变更）
- 阻断字段不一致：标记具体字段差异，阻断自动回灌。（原因：关键身份和数量不真实时不能自动写入）
- warning 字段不一致：标记具体字段差异，但不阻断自动回灌。（原因：日期和状态可能随业务流程变化）
- 数值字段不一致且其他阻断字段通过：可进入回灌候选。（原因：这是当前历史数据修复的主要目标）

## Testing

- 单元测试覆盖字段比较器：decimal、日期、字符串、空值。
- 单元测试覆盖采购入库单和采购订单真实性配置。
- 集成式 dry-run 测试使用伪造 DB/API 行，验证报告分类。
- 真实环境验证以 dry-run CSV 和 verify CSV 为准，不把生产数据写入测试 fixture。（原因：避免泄露业务数据）
```

## openspec/changes/verify-sync-data-authenticity/tasks.md

- Source: openspec/changes/verify-sync-data-authenticity/tasks.md
- Lines: 1-7
- SHA256: 4ba576e8ddfd2ed9d3f43a0d653005702dc63f108ea3c2fa5e153d9ed4b9b0a6

```md
- [ ] 定义真实性校验配置结构，覆盖身份键、业务维度、数值字段、日期字段和容忍规则。（原因：不同表单真实性字段不同，需要配置化）
- [ ] 实现字段比较器，支持 decimal、日期、字符串、空值和必填/可选字段分类。（原因：避免格式差异造成误报）
- [ ] 实现采购入库单和采购订单的真实性 dry-run 审计，输出汇总 CSV 与明细 CSV。（原因：先覆盖当前已回灌的采购链路）
- [ ] 增加回灌门禁：只有身份和业务维度通过的行才允许自动回灌。（原因：防止错行写入）
- [ ] 实现回灌后真实性 verify，要求同一批目标身份重新比对通过。（原因：写入成功必须有字段级证据）
- [ ] 增加单元测试和小型集成测试，覆盖通过、缺失、维度错配、数值差异、日期差异场景。（原因：锁定真实性分类逻辑）
- [ ] 编写操作说明，明确 dry-run、execute、verify 的使用顺序和报告含义。（原因：后续人工处理需要统一口径）
```

## openspec/changes/verify-sync-data-authenticity/specs/sync-data-authenticity/spec.md

- Source: openspec/changes/verify-sync-data-authenticity/specs/sync-data-authenticity/spec.md
- Lines: 1-48
- SHA256: cb81e1342a8f9dc97cc97513bdf62ef5bac5f3c79220c83b0cb8a9a801b148f0

```md
## ADDED Requirements

### Requirement: Authenticity audit compares identity and business fields
The system SHALL compare synchronized database rows with Kingdee source rows using configured identity keys, blocker fields, warning fields, value fields, and date fields before declaring data authentic.

#### Scenario: Purchase instock row is authentic
- **WHEN** a `采购入库单` row is audited
- **THEN** the system MUST match `FID` and `FENTRYID` against the Kingdee entry identity and compare bill number, entry sequence, material number, supplier, and real quantity as blocker fields
- **AND** bill date, document status, and modify date MUST be reported as warning fields when they differ

#### Scenario: Purchase order row is authentic
- **WHEN** a `采购订单` row is audited
- **THEN** the system MUST match `FID` and `FENTRYID` against the Kingdee entry identity and compare bill number, material number, supplier, and quantity as blocker fields
- **AND** document status and configured dates MUST be reported as warning fields when they differ

### Requirement: Authenticity audit classifies differences
The system SHALL classify each audited row and field into actionable statuses.

#### Scenario: Source row is missing
- **WHEN** a database row cannot be found in Kingdee by configured identity keys
- **THEN** the audit result MUST be `missing_api` and the row MUST NOT be eligible for automated rehydration

#### Scenario: Database row is missing
- **WHEN** a Kingdee target identity cannot be found in the database
- **THEN** the audit result MUST be `missing_db` and the row MUST NOT be updated as an existing-row repair

#### Scenario: Blocker dimension mismatch
- **WHEN** identity keys match but blocker fields such as material, bill number, supplier, customer, organization, entry sequence, or quantity do not match
- **THEN** the audit result MUST be `dimension_mismatch` or `identity_mismatch` and automated rehydration MUST be blocked for that row

#### Scenario: Warning field mismatch
- **WHEN** identity keys and blocker fields match but warning fields such as date or document status differ
- **THEN** the audit result MUST include field-level warnings and automated rehydration MUST NOT be blocked solely by those warnings

#### Scenario: Repairable value mismatch
- **WHEN** identity and blocker business dimensions match but a configured quantity, amount, price, or repair target field differs
- **THEN** the audit result MUST identify the field-level difference and MAY mark the row as eligible for rehydration

### Requirement: Rehydration requires authenticity gate
The system SHALL require authenticity audit evidence before and after any automated historical rehydration.

#### Scenario: Dry-run before rehydration
- **WHEN** a rehydration batch is prepared
- **THEN** the system MUST output a dry-run summary and detail report including target rows, rows that passed blockers, blocked rows, warning rows, and field-level differences

#### Scenario: Verify after rehydration
- **WHEN** a rehydration batch completes
- **THEN** the system MUST rerun authenticity audit for the same target identities and report whether all blocker fields now match Kingdee while preserving warning differences in the report
```

