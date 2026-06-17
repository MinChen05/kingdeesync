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
- `src/services/reporting.py`: 可为 `sync_logs` 建索引，并可归档后删除旧日志。
- `src/core/index_manager.py`: 维护一组预定义索引。
- `src/core/mysql_manager.py`、`sales_writer.py`、`production_writer.py`、`masterdata_writer.py`: 多个 writer 会按需补列或调整字段类型。
- `src/core/upsert_engine_sqlserver.py`: 大批量写入可能创建 `dbo.__stage_*` 阶段表，完成后清理。
- `src/tools/create_account_balance_table.py`: 工具脚本包含 drop/create 科目余额表逻辑，执行前必须单独审查。

后续任何涉及上述路径的改动，都需要按项目规则先说明数据库影响，报表相关表不要改结构，涉及主键/唯一键/字段顺序时保留数据并校验行数。

### Decision 4: 验证基线优先使用已有门禁与 dry-run

当前 README 和 `main.py check` 已定义基础门禁：

- `python main.py check`
- `python -m ruff check .`
- `python -m mypy`
- `python -m unittest discover tests -v`

针对只读分析，还应执行：

- `openspec validate analyze-current-project`
- `python scripts/dry_run_cleanup.py --root .`

涉及 SQL Server 写入的后续 change，需要额外说明预期日志变化，例如 `sync_runs.status/message/heartbeat_at`、`sync_logs.status/error_type`、表单级 `fetched/inserted/failed` 指标以及 staging/MERGE 批次日志。

## Risks / Trade-offs

- [Risk] 工作区已有大量未提交改动，分析可能反映当前脏工作区而非主线状态。→ Mitigation: 最终结论明确基于当前 `D:\Kingdee` 工作区，不回滚也不覆盖既有改动。
- [Risk] `mysql_manager.py` 同时承担连接、元数据、writer 兼容、DDL 补齐和历史代理，定位问题时容易范围扩散。→ Mitigation: 后续改动优先从 `FormSyncRunner`、writer、upsert engine、repository 的明确边界切入。
- [Risk] 报表表 `GL_RPT_AccountBalance` 在同步路径中会被清空后重建数据。→ Mitigation: 任何报表相关 change 都必须单独说明影响并避免结构变更。
- [Risk] 运行完整 `main.py check` 可能受本机依赖、SQL Server/ODBC 或既有脏改动影响。→ Mitigation: 先运行 OpenSpec 校验、目标单测和 dry-run；完整门禁失败时记录失败点。
- [Risk] 配置文件可能含本地连接信息。→ Mitigation: 不提交密钥或密码，分析仅引用配置结构和脱敏说明。

## Migration Plan

本 change 是文档/规范初始化，无运行时迁移。

后续如果进入实现阶段，应按以下顺序推进：

1. 先确认目标改动是否涉及数据库结构或 SQL Server 写入。
2. 若涉及数据库结构，先输出影响范围和数据保留/行数校验方案。
3. 用最小变更修改单一边界，优先保留现有配置驱动和 writer registry 模式。
4. 执行相关单元测试、相关脚本 dry-run。
5. 如涉及 SQL Server 写入，补充预期日志变化和失败回滚观察点。

## Open Questions

- 当前脏工作区中哪些改动属于用户已完成工作，哪些属于临时产物，后续是否需要单独分支整理。
- 是否要把现有自动 DDL 行为收敛为显式 migration/dry-run 机制。
- 科目余额表作为报表相关表，是否需要更强的结构保护和同步前行数快照。
- `mysql_manager.py` 是否需要在后续 change 中继续拆分连接、DDL、writer 兼容和历史代理职责。
