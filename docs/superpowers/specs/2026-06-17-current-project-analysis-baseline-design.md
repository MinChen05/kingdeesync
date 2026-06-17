---
comet_change: analyze-current-project
role: technical-design
canonical_spec: openspec
---

# 当前项目分析基线技术设计

## 1. 背景

当前项目是一个 Python 3.11 金蝶数据同步工具，主链路覆盖金蝶 API 拉取、SQL Server 写入、桌面 GUI、同步历史、指标统计和部署脚本。SQL Server 是默认数据库路径，MySQL 保留为兼容路径。

本次 change 的目标不是实现新功能，而是建立可追踪的项目现状基线。这个基线后续用于判断改动是否触碰数据库结构、是否影响报表表、是否需要补充 SQL Server 写入日志预期，以及应该跑哪些验证。

## 2. 确认方向

后续优先方向确认如下：

1. 先建立 SQL Server 写入安全与报表表保护基线。
2. 再基于该基线考虑性能观测和项目清理。
3. 暂不进入业务代码实现，不改同步逻辑，不运行生产数据库操作。

这意味着当前阶段只产出设计文档和约束，不对 `src/`、配置 JSON、测试或数据库做行为变更。

## 3. 当前架构地图

主同步链路如下：

```text
GUI / CLI
  -> src/services/sync_service.py
    -> src/core/data_sync.py
      -> src/core/form_sync_runner.py
        -> src/core/filter_builder.py
        -> src/core/kingdee_api.py
        -> src/core/writers_registry.py
          -> src/core/sales_writer.py
          -> src/core/production_writer.py
          -> src/core/masterdata_writer.py
        -> src/core/upsert_engine_sqlserver.py
        -> src/core/sync_log_repository.py
        -> src/core/sync_run_repository.py
```

配置驱动链路如下：

```text
config.ini / config.local.ini
  -> src/config/config_manager.py
  -> src/config/config_accessors.py
  -> src/config/tables.json
  -> src/config/form-queries.json
  -> src/config/field_mappings.json
```

GUI 边界如下：

```text
src/gui/pages/*
  -> src/gui/workers.py
    -> src/services/sync_service.py
```

## 4. 数据库影响边界

本 change 不修改数据库结构，不执行 SQL，不清空数据，不调整报表表。

但当前代码中已有以下数据库影响点，后续任何相关实现必须提前说明影响：

1. `src/core/form_sync_runner.py`
   - complete 同步会对普通目标表执行 `TRUNCATE TABLE`。

2. `src/core/account_balance_sync.py`
   - 科目余额表 `GL_RPT_AccountBalance` 默认清空后按月插入。
   - 这是报表相关表，后续不得随意改结构。

3. `src/core/sync_run_repository.py`
   - 会创建或补齐 `sync_runs`，并创建任务级索引。

4. `src/services/reporting.py`
   - 会为 `sync_logs` 建索引。
   - 日志归档会写入 archive 表并删除旧 `sync_logs`。

5. `src/core/mysql_manager.py` 与各 writer
   - 存在按需补列、改列类型、补 `SYNC_TIME`、补业务字段的逻辑。

6. `src/core/upsert_engine_sqlserver.py`
   - 大批量 SQL Server 写入可能创建 `dbo.__stage_*` 阶段表，完成或失败后清理。

7. `src/tools/create_account_balance_table.py`
   - 包含 drop/create 科目余额表逻辑，只能作为单独审查的高风险工具。

## 5. 后续改动规则

后续如果涉及 SQL Server 写入，应在实现前记录：

1. 目标表名和表单名。
2. 是否涉及报表表。
3. 是否会触发 `TRUNCATE TABLE`、`ALTER TABLE`、`CREATE INDEX`、`DROP TABLE` 或 staging 表。
4. 预期 `sync_runs` 日志变化，包括 `status`、`message`、`heartbeat_at`、`details_json`。
5. 预期 `sync_logs` 日志变化，包括 `status`、`record_count`、`error_type`、`duration_seconds`。
6. 预期表单级指标变化，包括 `fetched`、`inserted`、`invalid`、`deduped`、`failed`。
7. 失败时应观察的日志关键词，例如 MERGE、STAGE、write_failure_detail、query_error、circuit_open。

后续如果涉及数据库结构，应在实现前记录：

1. 表是否为报表相关表。
2. 是否涉及主键、唯一键或字段顺序。
3. 数据保留方案。
4. 变更前后行数校验方案。
5. 回滚或恢复方式。

## 6. 推荐后续切入点

推荐先做一个单独 change：`sqlserver-write-safety-baseline`。

建议目标：

1. 汇总现有自动 DDL 入口，给出集中清单或 dry-run 视图。
2. 给报表相关表增加更醒目的保护说明和测试覆盖。
3. 为 SQL Server 写入路径整理统一日志预期，不先重构 `mysql_manager.py`。

暂不推荐直接重构 `mysql_manager.py`。该文件责任确实偏重，但它承载大量历史兼容逻辑，直接拆分风险高。更稳的路径是先补证据和保护，再逐步拆分。

## 7. 测试策略

当前文档基线已验证：

1. `openspec status --change analyze-current-project`
2. `openspec validate analyze-current-project`
3. `python scripts/dry_run_cleanup.py --root .`
4. `python -m unittest tests.test_dry_run_cleanup -v`

后续实现型 change 至少应补：

1. 目标模块单元测试。
2. 对应 dry-run 或只读检查脚本。
3. 如涉及 SQL Server 写入，说明预期日志变化。
4. 如涉及数据库结构，说明数据保留和行数校验。

## 8. 风险与约束

1. 当前工作区已有大量未提交改动，本基线反映的是当前 `D:\Kingdee` 工作区现状。
2. `config.local.ini` 可能包含本地连接信息，后续不得提交密钥或密码。
3. 报表相关表需要单独保护，尤其是 `GL_RPT_AccountBalance`。
4. 项目已存在自动 DDL 行为，后续优化应先增强可见性，再考虑治理。

## 9. 验收标准

本设计阶段完成后应满足：

1. OpenSpec change 有 proposal、design、tasks、delta spec。
2. Comet `.comet.yaml` 记录 `design_doc`。
3. Comet design guard 通过并进入 build 阶段。
4. 未修改业务代码或数据库结构。
5. 后续实现方向已明确为 SQL Server 写入安全与报表表保护基线。
