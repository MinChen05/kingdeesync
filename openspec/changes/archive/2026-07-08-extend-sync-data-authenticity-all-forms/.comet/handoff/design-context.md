# Comet Design Handoff

- Change: extend-sync-data-authenticity-all-forms
- Phase: design
- Mode: compact
- Context hash: b042c4cf2160b67868a52541644fbb80d8d1f69d3fad0f406c5583cc011c04a2

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/extend-sync-data-authenticity-all-forms/proposal.md

- Source: openspec/changes/extend-sync-data-authenticity-all-forms/proposal.md
- Lines: 1-27
- SHA256: d7406d63e392f67384b6c8a2e92f812f0494bd05163e100ae801308859158968

```md
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
```

## openspec/changes/extend-sync-data-authenticity-all-forms/design.md

- Source: openspec/changes/extend-sync-data-authenticity-all-forms/design.md
- Lines: 1-55
- SHA256: 8e043f91173d32975c0fe2c01889bc2aac3f50edae60c46a6a8c807accc5eea2

```md
## Context

项目已有 `sync-data-authenticity` 能力，核心模块通过声明式 `AuthenticitySpec` 比对数据库行和金蝶 API 行；维护脚本已经能对采购订单、采购入库单执行 dry-run/verify，并处理 SQL Server 大批量参数拆批。（原因：扩展全表单应复用现有比较器、分类和报告模型）

当前同步表单定义分散在 `src/config/form-queries.json`、`src/config/tables.json` 和 writer 准备函数中。仅靠人工维护全表单映射容易出现 DB 列名、API 字段名、身份键不一致。（原因：字段映射需要先被发现和报告，再进入阻断规则）

## Goals / Non-Goals

**Goals:**

- 生成全同步表单真实性映射草案报告，包含表单、目标表、API FormId、身份键候选、阻断字段候选、warning 字段候选、字段覆盖状态。（原因：实现前先形成可审阅证据）
- 将除科目余额表外的已同步表单纳入 dry-run 规划，分批执行并输出 summary/detail/blockers。（原因：覆盖所有同步单据但控制执行风险）
- 对无法可靠确认身份键的表单标记 `[待确认]`，不默认进入自动回灌门禁。（原因：身份键不确定时不能自动写入）
- 保持所有脚本只读，禁止写 SQL Server。（原因：本 change 是真实性校验扩展，不是数据修复）

**Non-Goals:**

- 不执行生产数据回灌或补写。
- 不修改数据库 schema、主键、索引或报表表结构。
- 不把科目余额表纳入第一批字段级真实性审计。（原因：报表接口参数和行身份模型不同，需要单独设计）
- 不把弱字段如描述、规格、条码、自定义文本作为第一版阻断项。（原因：先降低噪声，聚焦业务真实性核心）

## Decisions

### Decision 1: 先做 schema discovery，再扩展阻断规则

实现一个 discovery 报告，读取 `form-queries.json`、`tables.json`、当前 DB 列和已有 `AUDIT_SPECS`，输出 `authenticity_mapping_draft.csv`。（原因：全表字段多且命名不统一，先做发现能减少硬编码误判）

备选方案是直接手写所有 `AuthenticitySpec`。该方案速度快，但容易遗漏 DB 字段和 writer 实际落库列，暂不采用。（原因：真实性校验最怕错字段造成假通过）

### Decision 2: 表单分三批 dry-run

第一批覆盖业务单据：销售、采购、应收应付、委外、发货通知单。第二批覆盖生产与预测。第三批覆盖即时库存、基础资料、BOM。（原因：按业务域分批能隔离 API 超时、字段口径差异和数据量风险）

### Decision 3: 身份键不确定时进入报告，不进入自动回灌候选

没有明确 `FID` 或分录 ID 的表单先输出 `[待确认]`，dry-run 可报告缺口，但不得把这些表单标记为可自动回灌。（原因：身份键不可靠时写库风险最高）

### Decision 4: 即时库存采用快照组合键

即时库存不依赖增量时间；真实性身份使用库存组织、仓库、仓位、库存状态、物料、基本单位组成快照键，`FBASEQTY` 作为阻断数量，`FUPDATETIME` 作为 warning。（原因：即时库存是当前状态快照，不适合按单据分录身份校验）

## Risks / Trade-offs

- [Risk] 部分 DB 表列名与 API 字段名不一致 → 通过 discovery 报告标记 `missing_db_field` / `missing_api_field`，先人工确认再阻断。（原因：避免把字段命名问题误判为业务差异）
- [Risk] 大表 dry-run 查询耗时或 API 超时 → 按批次、拆批参数、分页查询，并记录每批耗时。（原因：降低一次性全量扫描风险）
- [Risk] warning 字段过多导致报告噪声大 → 第一版 summary 单独统计 warning，不阻断 dry-run 通过。（原因：日期和状态常随业务流程变化）
- [Risk] 基础资料没有分录结构 → 使用主数据 ID/编码作为身份键，并只比较核心编码、名称、组织、状态。（原因：基础资料真实性口径不同于单据）

## Migration Plan

1. 新增 discovery 报告，不影响现有采购 dry-run 命令。
2. 增量补充 `AuthenticitySpec`，每批有单元测试覆盖身份键、阻断项、warning 项。
3. 先执行 discovery，再执行第一批 dry-run；确认报告后再推进第二、第三批。
4. 如任一表单出现身份键缺失或大量 blocker，暂停该表单，保留报告供人工确认。（原因：真实性校验不能在身份不明时继续自动化）
```

## openspec/changes/extend-sync-data-authenticity-all-forms/tasks.md

- Source: openspec/changes/extend-sync-data-authenticity-all-forms/tasks.md
- Lines: 1-23
- SHA256: 758dcd16c38744afd48c8db7fd513f237641e300246a60f1f5c31135f237c645

```md
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
```

## openspec/changes/extend-sync-data-authenticity-all-forms/specs/sync-data-authenticity/spec.md

- Source: openspec/changes/extend-sync-data-authenticity-all-forms/specs/sync-data-authenticity/spec.md
- Lines: 1-46
- SHA256: 0b6415f1af191e8bd61a932c5b79e9ee1dc98552eb009ea48dd3a0c91ad44341

```md
## MODIFIED Requirements

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

#### Scenario: Non-purchase synchronized form is mapped
- **WHEN** a synchronized form other than `采购入库单` or `采购订单` is included in authenticity dry-run
- **THEN** the system MUST define or report candidate identity keys, blocker fields, warning fields, database fields, and Kingdee API fields for that form
- **AND** rows with unconfirmed identity keys MUST NOT be marked eligible for automated rehydration

#### Scenario: Inventory snapshot row is authentic
- **WHEN** an `即时库存` row is audited
- **THEN** the system MUST use stock organization, stock, stock location, stock status, material, and base unit as the snapshot identity
- **AND** base quantity MUST be treated as a blocker value field
- **AND** update time MUST be reported as a warning field when it differs

### Requirement: Rehydration requires authenticity gate
The system SHALL require authenticity audit evidence before and after any automated historical rehydration.

#### Scenario: Dry-run before rehydration
- **WHEN** a rehydration batch is prepared
- **THEN** the system MUST output a dry-run summary and detail report including target rows, rows that passed blockers, blocked rows, warning rows, and field-level differences

#### Scenario: Verify after rehydration
- **WHEN** a rehydration batch completes
- **THEN** the system MUST rerun authenticity audit for the same target identities and report whether all blocker fields now match Kingdee while preserving warning differences in the report

#### Scenario: All-form mapping discovery
- **WHEN** the operator prepares to extend authenticity dry-run to all synchronized forms
- **THEN** the system MUST output a mapping draft report that includes each synchronized form, SQL table, Kingdee FormId, configured API FieldKeys, candidate identity fields, blocker fields, warning fields, and unsupported or unconfirmed fields
- **AND** the mapping discovery MUST be read-only and MUST NOT write SQL Server data

#### Scenario: Batched all-form dry-run
- **WHEN** all-form authenticity dry-run is executed
- **THEN** the system MUST execute forms in documented business batches and output summary, detail, and blocker-only reports per batch
- **AND** the dry-run MUST NOT execute automatic rehydration or SQL Server writes
```

