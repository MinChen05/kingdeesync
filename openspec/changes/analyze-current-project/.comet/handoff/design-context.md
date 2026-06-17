# Comet Design Handoff

- Change: analyze-current-project
- Phase: design
- Mode: compact
- Context hash: 3edddf6844637af907af8d19aeb4333d99df5d7dc39222559861bafd9dc21f21

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/analyze-current-project/proposal.md

- Source: openspec/changes/analyze-current-project/proposal.md
- Lines: 1-23
- SHA256: 16c794a3c0c04c5068efdacc3d2a79733e46b93800cdb390de527f6217a87b13

```md
## Why

当前项目已经形成金蝶 API 拉取、SQL Server 写入、桌面 GUI、同步历史与性能优化的完整链路，但关键架构知识分散在代码、配置、测试和历史计划中。需要建立一份可追踪的项目现状基线，便于后续排查同步失败、评估数据库变更影响、规划性能优化和交接维护。

## What Changes

- 新增当前项目分析产物，覆盖模块边界、同步主流程、配置驱动模型、数据库写入路径、GUI 调用路径、测试与运维入口。
- 明确数据库结构相关风险点：当前分析不修改任何业务表、报表表或索引，只记录现有代码中可能执行 DDL 的位置。
- 输出后续任务清单，用于后续分阶段验证连接、dry-run、单元测试和结构治理。

## Capabilities

### New Capabilities
- `project-analysis-baseline`: 记录项目现状、数据流、数据库写入边界、验证口径和后续风险清单。

### Modified Capabilities
- 无。

## Impact

- 影响范围仅限 OpenSpec/Comet 分析文档。
- 不修改 `src/`、`tests/`、配置 JSON、数据库结构或同步运行逻辑。
- 为后续涉及 SQL Server 写入、报表表保护、性能优化和 GUI 运维体验的 change 提供事实基线。
```

## openspec/changes/analyze-current-project/design.md

- Source: openspec/changes/analyze-current-project/design.md
- Lines: 1-130
- SHA256: 09d72c8a76ffb28058ff987754a22c7a3e9cc0d2d5288b01daafc6f92a1fda30

[TRUNCATED]

```md
## Context

这是一个 Python 3.11 金蝶数据同步工具，当前主路径是 SQL Server，MySQL 作为兼容路径保留。项目包含三条主要使用入口：

- `main.py`: CLI/GUI 统一入口，支持 `gui`、`sync`、`maintenance archive_logs`、`check`。
- `src/utils/kingdee_sync_tool.py`: GUI 启动封装，负责桌面应用生命周期和启动恢复。
- `src/gui/workers.py`: GUI 后台线程边界，将页面操作委托给 `src/services/sync_service.py`。

核心代码按层次大致分为：

- 配置层：`src/config/config_manager.py`、`config_accessors.py`、`config_reader.py`，结合 `tables.json`、`form-queries.json`、`field_mappings.json` 驱动同步表单、查询字段和字段容错映射。
- API 层：`src/core/kingdee_api.py` 负责登录、会话保活、分页查询、报表接口适配、限流、重试和会话失效重登。
- 编排层：`src/core/data_sync.py` 负责同步批次、并发分组、心跳、熔断、任务级结果和本地 SQLite 统计。
- 单表执行层：`src/core/form_sync_runner.py` 负责构建过滤条件、查询分页回调、异步或批量写入、断点、写入失败遥测和表单级日志。
- 写入层：`src/core/writers_registry.py` 将 `tables.json` 的 `insert_method` 解析为 `sales_writer.py`、`production_writer.py`、`masterdata_writer.py` 中的具体 writer。
- 数据库层：`src/core/mysql_manager.py` 管理 SQL Server/MySQL 连接、元数据、writer 执行、历史记录代理；`upsert_engine_sqlserver.py` 与 `upsert_engine_mysql.py` 承担批量 upsert。
- 历史与报表层：`sync_run_repository.py`、`sync_log_repository.py`、`history_manager.py`、`services/reporting.py` 为 GUI 仪表盘、历史页和维护任务提供数据。

主同步数据流：

```text
GUI/CLI
  -> SyncService
    -> DataSyncManager.sync_data
      -> KingdeeAPIClient.ensure_session + MySQLManager.test_connection
      -> grouped forms by priority/concurrency
        -> FormSyncRunner.sync_single_form
          -> FilterBuilder.build_filter_string
          -> KingdeeAPIClient.query_data(page_callback)
          -> WriterRegistry / domain writer
          -> UpsertEngineSqlServer MERGE or staging MERGE
          -> sync_logs + sync_runs + local sync_stats.db
```

## Goals / Non-Goals

**Goals:**

- 建立当前项目架构和运行链路的事实基线。
- 标出 SQL Server 写入、DDL、报表表、日志归档、staging 表和完整同步截断等数据库边界。
- 给后续 bugfix、性能优化、字段映射调整和 GUI 维护提供最小可验证入口。
- 保持分析文档与 OpenSpec/Comet 状态机可追踪。

**Non-Goals:**

- 不修改业务代码、配置 JSON、测试文件或 GUI。
- 不执行同步任务，不连接生产 SQL Server，不写入业务表。
- 不新增、删除或调整任何业务表、报表表、主键、唯一键、字段顺序或索引。
- 不清理工作区已有脏文件，不处理已存在的未提交改动。

## Decisions

### Decision 1: 将项目分析沉淀为 OpenSpec change

选择 `analyze-current-project` 作为独立 change，原因是这次工作不是单点修复，而是为后续同步链路维护建立基线。OpenSpec 产物能把“为什么分析、分析覆盖什么、后续怎么验证”固定下来。

替代方案是只在聊天中输出分析结论，但那样无法被后续 `/comet-design`、`/comet-build` 或代码审查流程复用。

### Decision 2: 以同步链路为主轴，而不是以文件树为主轴

项目文件数量不大，但同步行为横跨 GUI、服务、API、配置、数据库和历史仓储。按链路梳理更容易定位问题：

```text
配置 JSON
  -> 表单与字段
  -> 金蝶查询参数
  -> writer 方法
  -> SQL Server upsert
  -> 历史与指标
```

替代方案是按目录逐个描述，但会弱化“某张表失败时该看哪里”的定位价值。

### Decision 3: 数据库影响按“现有风险点”记录

本 change 不触发数据库结构变更，但项目运行路径里已经存在 DDL/DML 边界：

- `src/core/form_sync_runner.py`: complete 同步会 `TRUNCATE TABLE` 普通目标表；科目余额表走专用按月同步并清空 `GL_RPT_AccountBalance`。
- `src/core/account_balance_sync.py`: 科目余额表同步默认清空后按月插入，属于报表相关表高风险路径。
- `src/core/sync_run_repository.py`: 自动创建/补齐 `sync_runs`，并创建任务级索引。
```

Full source: openspec/changes/analyze-current-project/design.md

## openspec/changes/analyze-current-project/tasks.md

- Source: openspec/changes/analyze-current-project/tasks.md
- Lines: 1-17
- SHA256: e65b3ee352abc651effaeaa07abd63c9591d7d7e1245e9d3cfae2f2efa9a19fa

```md
## 1. Baseline Artifacts

- [x] 1.1 Review the current project entrypoints, configuration files, sync orchestration, API client, writer registry, database layer, GUI worker boundary, and tests.
- [x] 1.2 Record the current architecture baseline in `proposal.md`, `design.md`, and `specs/project-analysis-baseline/spec.md`.
- [x] 1.3 Identify existing database-impacting code paths, including automatic column additions, index creation, complete-sync truncation, report-table sync, log archiving, and SQL Server staging tables.

## 2. Verification

- [x] 2.1 Run `openspec status --change analyze-current-project` and confirm all required OpenSpec artifacts are present.
- [x] 2.2 Run `openspec validate analyze-current-project` and fix any spec formatting or artifact issues.
- [x] 2.3 Run `python scripts/dry_run_cleanup.py --root .` as the relevant dry-run script for this documentation-only analysis.

## 3. Follow-up Planning

- [x] 3.1 Decide whether future work should first target SQL Server write safety, report-table protection, performance observability, or project cleanup.
- [x] 3.2 For any future SQL Server write change, document expected `sync_runs`, `sync_logs`, metrics, MERGE/staging, and failure-telemetry log changes before implementation.
- [x] 3.3 For any future database schema change, document table impact, data preservation plan, and row-count validation plan before editing code or running SQL.
```

## openspec/changes/analyze-current-project/specs/project-analysis-baseline/spec.md

- Source: openspec/changes/analyze-current-project/specs/project-analysis-baseline/spec.md
- Lines: 1-26
- SHA256: a498b828f250d790170fb3aace9c0d0b4b22b3323139f702ea73545606322c99

```md
## ADDED Requirements

### Requirement: Architecture Baseline
The project analysis baseline SHALL document the current module boundaries, runtime entrypoints, and primary data flow for the Kingdee data sync tool.

#### Scenario: Reader needs the project map
- **WHEN** a maintainer opens the baseline
- **THEN** they can identify the CLI/GUI entrypoints, configuration layer, Kingdee API client, sync orchestration, form runner, writer registry, SQL Server upsert path, repositories, and GUI worker boundary

### Requirement: Database Impact Boundary
The project analysis baseline SHALL explicitly distinguish this documentation-only change from future changes that alter SQL Server tables, indexes, primary keys, unique keys, or report-related structures.

#### Scenario: Baseline is created
- **WHEN** the OpenSpec change artifacts are reviewed
- **THEN** they state that no database schema or production data is changed by this analysis

#### Scenario: Existing DDL risk is reviewed
- **WHEN** maintainers plan a future SQL Server write change
- **THEN** the baseline provides a list of existing code areas that may create indexes, add columns, truncate tables, archive logs, or use staging tables

### Requirement: Verification Baseline
The project analysis baseline SHALL record the relevant validation commands and dry-run expectations for future work on this repository.

#### Scenario: Future change starts from the baseline
- **WHEN** a maintainer uses the analysis before implementing changes
- **THEN** they can see the expected minimum checks for unit tests, OpenSpec validation, cleanup dry-run, and SQL Server write-log expectations when applicable
```

