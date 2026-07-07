# Comet Design Handoff

- Change: add-purchase-instock-sync
- Phase: design
- Mode: compact
- Context hash: 036eec0cf0faf7c21e38ab7a42f5198d5cd53d17cfcf4af988912df71ee92f0c

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/add-purchase-instock-sync/proposal.md

- Source: openspec/changes/add-purchase-instock-sync/proposal.md
- Lines: 1-29
- SHA256: 10bea4b6d800633216ff0b77877948cb0b8c91f051c35c4c5bf108c0318c08ab

```md
## Why

当前工具已支持采购订单、应付单、生产入库单等同步，但缺少采购入库单同步，导致采购到货入库后的库存与供应链闭环无法在 SQL Server 侧完整追踪。新增采购入库单基础明细同步，可以补齐采购订单到入库的业务链路，并为后续应付核对、库存分析和异常追溯提供数据基础。

## What Changes

- 新增“采购入库单”表单同步能力，优先覆盖单据头和分录基础字段，包括单号、日期、状态、供应商、采购组织、物料、实收数量、源单号、源单行、修改时间等（原因：先完成可验证的基础明细闭环，降低字段不确定性风险）。
- 新增金蝶查询配置，目标 FormId 采用采购入库单常用标识 `STK_InStock`，字段清单以后续 dry-run 响应校准（原因：不同金蝶环境可能存在字段别名或自定义字段差异）。
- 新增 SQL Server 目标表与 writer 注册，复用现有 `form-queries.json`、`tables.json`、writer registry、批量写入、staging/upsert 和增量过滤链路（原因：框架能力和项目既有同步能力优先复用，避免重复造轮子）。
- 新增采购入库单数据准备与写入校验，空主键、空单号等无效行必须跳过并记录日志（原因：保证写入幂等性和数据可追溯性）。
- 新增相关单元测试和 dry-run 验证脚本/说明，覆盖配置注册、字段映射、writer 注册、主键过滤和 SQL Server 写入预期日志（原因：数据库写入变更必须有可回归证据）。
- 将当前工作区既有未提交改动纳入本 change 的核验范围，包括 `assets/styles.css`、`src/core/mysql_manager.py`、诊断脚本和日志中心截图（原因：用户明确要求并入当前 change，后续验证需避免遗漏）。

## Capabilities

### New Capabilities

- `purchase-instock-sync`: 定义采购入库单基础明细从金蝶 API 拉取、字段映射、SQL Server 写入、幂等更新和验证要求。

### Modified Capabilities

- 无。

## Impact

- 影响配置：`src/config/form-queries.json`、`src/config/tables.json`、`config.example.ini` 中的表单与 staging 配置可能需要新增采购入库单条目（原因：让 GUI、调度和同步服务能够发现并执行该表单）。
- 影响写入链路：`src/core/sales_writer.py` 或更合适的 writer 模块、`src/core/writers_registry.py`、`src/core/mysql_manager.py` 需要新增/复用采购入库单写入方法（原因：当前架构通过 writer registry 分发具体表单写入）。
- 影响 SQL Server：允许新增非报表业务表 `STK_InStock` 或约定后的采购入库单目标表，并允许新增必要索引；不修改报表相关表结构（原因：采购入库单是业务单据表，不属于报表表结构禁改范围）。
- 影响测试：新增或扩展配置、writer、upsert、字段映射和 dry-run 相关测试（原因：同步表单新增会影响配置加载、数据转换和数据库写入三层行为）。
```

## openspec/changes/add-purchase-instock-sync/design.md

- Source: openspec/changes/add-purchase-instock-sync/design.md
- Lines: 1-70
- SHA256: cfb8476e21dba9fe8e8f67f5f6cdd5decd11b8bc2bac94f21dba70336c0bc374

```md
## Context

项目当前同步链路是配置驱动：`src/config/form-queries.json` 定义金蝶查询参数，`src/config/tables.json` 将中文表单名映射到 SQL Server 表和 writer，`src/core/form_sync_runner.py` 执行拉取与写入，`src/core/writers_registry.py` 分发 writer，具体 writer 通过 `MySQLManager` 的批量写入、staging/upsert 和字段准备方法落库。采购入库单应沿用这条链路（原因：复用现有框架能力可以减少新增分支逻辑和运行风险）。

当前已有相邻能力包括“采购订单”“应付单”“生产入库单”。其中生产入库单提供了入库类单据的分录主键、单号校验和 staging/upsert 参考；采购订单和应付单提供了供应商、采购组织、物料等采购域字段参考。采购入库单目标先限定为基础明细同步，不覆盖批号、仓位、库存状态、金额税率等扩展字段（原因：用户已选择 A 方案，字段以后续 dry-run 响应校准）。

本 change 会涉及 SQL Server 写入：允许新增非报表业务表和必要索引，不涉及报表相关表结构；如后续实施涉及主键、唯一键或字段顺序调整，必须保留数据并校验行数（原因：遵守项目数据库规则，避免破坏生产数据）。

## Goals / Non-Goals

**Goals:**

- 新增“采购入库单”作为可配置、可调度、可手动执行的同步表单（原因：让现有 GUI、调度和同步服务自然识别新表单）。
- 拉取采购入库单基础明细字段，并写入 SQL Server 非报表业务表（原因：补齐采购到货入库数据闭环）。
- 通过分录级主键实现幂等写入，重复同步同一分录时更新而不是重复插入（原因：同步任务可能重试或增量回放）。
- 对空 `FID`、空分录主键、空单号等无效数据执行跳过并记录日志（原因：避免脏数据破坏唯一键或影响后续追溯）。
- 提供配置、writer、字段映射、upsert 和 dry-run 级别验证（原因：新增 SQL Server 写入能力需要可回归证据）。

**Non-Goals:**

- 不在本次实现批号、仓位、库存状态、保质期等库存扩展字段（原因：这些字段依赖具体业务启用情况，容易扩大范围）。
- 不在本次实现金额、税率、价税合计、成本价等财务字段（原因：财务口径应与应付或成本模块单独确认）。
- 不修改报表相关表结构（原因：项目明确禁止修改报表相关表结构）。
- 不新建独立同步框架或绕过 writer registry（原因：现有同步框架已覆盖配置、重试、staging 和日志能力）。

## Decisions

### Decision 1: 复用现有配置驱动同步链路

采购入库单新增到 `form-queries.json` 和 `tables.json`，通过现有 `FormSyncRunner`、`ConfigManager`、writer registry 进入统一同步流程（原因：这能让手动同步、定时同步、增量过滤和 GUI 展示保持一致）。

备选方案是为采购入库单单独写脚本或独立入口。该方案短期更快，但会绕过现有任务、日志、重试和配置校验体系，后续维护成本更高（原因：项目已有通用同步能力，不应重复造轮子）。

### Decision 2: 采用分录级幂等键

目标表以采购入库单分录主键作为优先幂等键，字段可参考 `FInStockEntry_FENTRYID` 或 dry-run 返回的实际分录字段；若 SQL Server upsert 配置需要统一，需在 `upsert_engine_sqlserver` 的主键映射中补充目标表主键（原因：采购入库单是一单多行结构，单据头 `FID` 不能唯一表示明细行）。

备选方案是使用 `FID + FSEQ`。该方案可作为兼容兜底，但对字段变更和行号调整更敏感，应优先使用金蝶分录内码（原因：分录内码更适合做稳定幂等键）。

### Decision 3: 字段先按基础明细建模，dry-run 校准字段名

初始字段集覆盖 `FID`、分录主键、分录序号、`FBillNo`、`FDate`、单据状态、供应商、采购组织、物料编码、物料名称、实收数量、源单号、源单行、修改时间。`FormId` 采用 `STK_InStock`，字段路径以后续接口 dry-run 响应为准进行校准（原因：金蝶环境可能存在字段别名、大小写和自定义字段差异）。

备选方案是一次性加入库存和财务扩展字段。该方案信息更完整，但字段启用差异和目标表设计复杂度更高，当前不符合 A 方案边界（原因：先小步闭环更易验证）。

### Decision 4: 目标表命名保持业务语义并纳入 staging 配置

目标表建议使用 `STK_InStock` 或项目约定后的等价业务表名，并加入 `force_staging_tables`（原因：采购入库单属于业务单据写入，staging 能降低直接 upsert 的类型转换和批量合并风险）。

备选方案是复用采购订单或生产入库单表。该方案会混淆业务实体和字段语义，不利于后续查询和维护（原因：不同单据应保持独立表结构）。

## Risks / Trade-offs

- [Risk] 金蝶字段名在目标环境与默认配置不一致 → 通过 dry-run 输出响应样例校准 `FieldKeys` 和 `_prepare_purchase_instock_data` 字段读取顺序（原因：避免凭空假定字段存在）。
- [Risk] 目标表新增后历史数据量较大，首次同步耗时较长 → 复用分页、增量过滤、staging 和必要索引，并在日志中观察页数、写入量和跳过量（原因：性能问题需要先有证据）。
- [Risk] 分录主键字段缺失导致幂等失效 → 单元测试覆盖空主键跳过，并在 dry-run 日志中确认分录主键非空比例（原因：唯一键设计依赖稳定主键）。
- [Risk] 既有未提交改动被并入后扩大验证范围 → 在 tasks 中显式增加 dirty worktree 归因与验证任务（原因：用户要求并入当前 change，必须保证这些改动不会被无意忽略）。

## Migration Plan

1. 新增配置和 writer 注册，不先执行生产数据写入（原因：先让代码路径可测试）。
2. 新增/确认 SQL Server 非报表业务表及索引；如需要调整主键或唯一键，先备份并校验行数（原因：数据库结构变更必须保留数据）。
3. 运行单元测试和采购入库单 dry-run，确认金蝶响应字段、跳过记录、目标 SQL 和预期日志（原因：字段以后续 dry-run 响应校准）。
4. 小批量执行同步并检查写入行数、重复同步幂等性和错误日志（原因：验证真实数据库写入行为）。
5. 如上线异常，禁用“采购入库单”任务或从配置中移除表单映射，保留已写入业务表待人工核对（原因：避免破坏其他表单同步）。

## Open Questions

- 目标环境采购入库单基础字段的真实 `FieldKeys` 路径需通过 dry-run 响应确认（原因：当前只能依据相邻表单和金蝶常用 FormId 做设计）。
- SQL Server 目标表最终命名采用 `STK_InStock` 还是小写业务表名需在实施时结合现有命名风格决定（原因：项目同时存在金蝶原名表和小写业务表）。
```

## openspec/changes/add-purchase-instock-sync/tasks.md

- Source: openspec/changes/add-purchase-instock-sync/tasks.md
- Lines: 1-40
- SHA256: 96fb13936b346cf2cc252ac9516178892c175306bbce4acb1964a0012f313fa8

```md
## 1. 配置与表单注册

- [ ] 1.1 在 `src/config/form-queries.json` 新增“采购入库单”查询配置，初始 FormId 使用 `STK_InStock`，字段先覆盖基础明细并保留 dry-run 校准记录。
- [ ] 1.2 在 `src/config/tables.json` 新增“采购入库单”目标表和 writer 映射。
- [ ] 1.3 在 `config.example.ini` 的 staging 配置中加入采购入库单目标表。
- [ ] 1.4 扩展配置加载或配置校验测试，确认“采购入库单”可被发现。

## 2. Writer 与数据准备

- [ ] 2.1 新增 `insert_purchase_instock` writer，并注册到 `src/core/writers_registry.py`。
- [ ] 2.2 新增 `_prepare_purchase_instock_data` 数据准备方法，覆盖基础明细字段转换。
- [ ] 2.3 为缺少 `FID`、分录主键或单号的记录增加跳过逻辑和警告日志。
- [ ] 2.4 在 SQL Server upsert/staging 主键映射中补充采购入库单分录级幂等键。

## 3. SQL Server 表结构与索引

- [ ] 3.1 定义采购入库单非报表业务目标表字段，保留数据类型与现有写入引擎兼容。
- [ ] 3.2 如目标表不存在，新增建表或自动补列路径；如涉及主键、唯一键或字段顺序调整，先保留数据并校验行数。
- [ ] 3.3 为分录主键和修改时间新增必要索引。
- [ ] 3.4 明确本次不修改报表相关表结构。

## 4. 测试与 Dry-run

- [ ] 4.1 新增 writer registry 测试，确认 `insert_purchase_instock` 已注册。
- [ ] 4.2 新增采购入库单字段准备测试，覆盖正常记录、空分录主键、空单号和大小写字段兼容。
- [ ] 4.3 新增 upsert/staging 测试，确认采购入库单使用分录级幂等键。
- [ ] 4.4 新增或更新 dry-run 脚本说明，输出金蝶响应样例、字段校准结果、预计写入量和跳过量。

## 5. 既有未提交改动核验

- [ ] 5.1 复核并归因 `assets/styles.css`、`src/core/mysql_manager.py`、诊断脚本和日志中心截图，确认是否与本 change 一起保留。
- [ ] 5.2 对 `src/core/mysql_manager.py` 的既有改动运行相关测试，避免采购入库单实现覆盖用户改动。
- [ ] 5.3 如截图或诊断脚本不参与运行时逻辑，在验证报告中说明其影响范围。

## 6. 验证收尾

- [ ] 6.1 运行 `pytest` 中采购入库单相关单元测试。
- [ ] 6.2 运行配置管理、writer registry、upsert/staging 相关回归测试。
- [ ] 6.3 执行采购入库单 dry-run，并记录预期 SQL Server 写入日志变化。
- [ ] 6.4 运行 `openspec validate add-purchase-instock-sync --strict`。
```

## openspec/changes/add-purchase-instock-sync/specs/purchase-instock-sync/spec.md

- Source: openspec/changes/add-purchase-instock-sync/specs/purchase-instock-sync/spec.md
- Lines: 1-56
- SHA256: 2641f9386ec3f57dc9d473e59a2ebca3c0f1ba499fb4bdf0dad85f1734cc3a07

```md
## ADDED Requirements

### Requirement: 采购入库单可配置同步
系统 SHALL 将“采购入库单”作为可配置同步表单注册到现有表单查询和目标表映射中，并通过现有同步入口执行拉取与写入。

#### Scenario: 配置加载采购入库单
- **WHEN** 配置管理器加载内置表单查询和表映射
- **THEN** 系统返回“采购入库单”的金蝶查询配置、SQL Server 目标表和 writer 方法

#### Scenario: 同步入口执行采购入库单
- **WHEN** 用户或调度任务选择同步“采购入库单”
- **THEN** 系统通过现有金蝶 API 查询、表单同步 runner 和 writer registry 执行该表单同步

### Requirement: 采购入库单基础明细字段
系统 SHALL 拉取并写入采购入库单基础明细字段，至少覆盖单据内码、分录内码、分录序号、单号、日期、单据状态、供应商、采购组织、物料编码、物料名称、实收数量、源单号、源单行和修改时间。

#### Scenario: 基础字段写入目标表
- **WHEN** 金蝶 API 返回采购入库单基础明细记录
- **THEN** 系统将基础字段转换为目标表字段并批量写入 SQL Server

#### Scenario: dry-run 校准字段
- **WHEN** dry-run 响应显示字段路径与默认配置不一致
- **THEN** 系统 SHALL 以 dry-run 响应为准调整 `FieldKeys` 和字段读取逻辑

### Requirement: 分录级幂等写入
系统 SHALL 使用采购入库单分录级主键执行幂等写入，重复同步同一分录时更新既有记录而不是重复插入。

#### Scenario: 重复同步同一分录
- **WHEN** 同一采购入库单分录被同步两次
- **THEN** SQL Server 目标表中该分录只有一条最新记录

#### Scenario: 单据多分录同步
- **WHEN** 同一采购入库单包含多个分录
- **THEN** 系统按分录分别写入多条记录，并保留同一单号下的不同分录

### Requirement: 无效采购入库单记录处理
系统 SHALL 跳过缺少单据内码、分录主键或单号的采购入库单记录，并记录可定位的警告日志。

#### Scenario: 分录主键为空
- **WHEN** 采购入库单记录缺少分录主键
- **THEN** 系统跳过该记录，并在日志中记录单据内码、单号和跳过原因

#### Scenario: 单号为空
- **WHEN** 采购入库单记录缺少单号
- **THEN** 系统跳过该记录，并在日志中记录单据内码、分录主键和跳过原因

### Requirement: SQL Server 写入验证
系统 SHALL 为采购入库单同步提供单元测试和 dry-run 验证，覆盖配置注册、字段转换、writer 注册、无效记录跳过、幂等写入和预期日志。

#### Scenario: 单元测试验证写入链路
- **WHEN** 运行相关单元测试
- **THEN** 测试覆盖采购入库单配置、writer 注册、字段准备和空主键跳过行为

#### Scenario: dry-run 验证 SQL Server 写入预期
- **WHEN** 执行采购入库单 dry-run
- **THEN** 输出 SHALL 显示查询字段、样例记录、预计写入量、跳过量和 SQL Server 写入日志预期
```

