# CONTEXT — kingdee-sync 领域上下文

本文件是项目的统一语言（ubiquitous language）词汇表与模块地图。
所有 issue 标题、重构提案、测试命名、假设描述应使用此处定义的术语，
不得漂移到「应避免的说法」中列出的同义词。架构决策见 `docs/adr/`。

## 项目定位

将金蝶云星空（K/3 Cloud）的**业务表单**数据定时同步至 SQL Server，
提供 Web 管理界面进行**同步运行**调度、监控与配置管理。
生产链路唯一：`apps/web → /api → apps/server → Kingdee API / SQL Server`
（见 `docs/architecture/current-runtime.md`）。

## 术语表（Glossary）

### 同步对象

| 术语 | 定义 | 代码锚点 |
|---|---|---|
| **表单（Form）** | 金蝶侧的一个业务实体（如销售订单、应收单），对应目标库的一张主表。当前共 22 张。 | `form-queries.json` 的键 |
| **表单查询配置（FormQuery）** | 一个表单的同步配置：`form_id` / `field_keys` / `filter_string` / `field_map`（金蝶字段 → 目标列映射）。权威存储于状态库 `go_form_queries` 表。 | `config.GetFormQuery()`、`gormdb` |
| **种子配置（Seed Config）** | `packages/sync-config/form-queries.json`。仅在全新部署（`go_form_queries` 表为空）时一次性灌库，之后仅作兜底，**不是**运行时权威源。 | `gormdb.MigrateFormQueriesFromJSON` |
| **目标表（Target Table）** | SQL Server（`10.10.10.191/Kingdee`，schema dbo）中承接表单数据的主表。 | `sqlserver_writer.go` |

### 同步运行

| 术语 | 定义 | 代码锚点 |
|---|---|---|
| **同步运行（Run）** | 一次同步执行，有唯一 `run_id`，包含若干表单的**表单统计（FormStats）**与**运行事件（RunEvent）**。 | `sync_runs` / `sync_form_stats` / events API |
| **同步类型（SyncType）** | 对外仅两种：`incremental`（增量，按时间窗口）与 `full`（全量）。`reset` 是引擎内部兼容标签，API 不接受。 | `api/routes/v1/schedules.go:72` |
| **运行状态（SyncStatus）** | 公共状态机：`running / stopping / success / partial / failed / stopped / failed_abnormal_exit`。终态不可被正常执行改变；`failed_abnormal_exit` 只能由恢复流程产生。 | `api/contract` |
| **调度（Schedule）** | 按 cron 表达式周期性触发同步运行的配置项，经 Web 界面管理。默认：工作日每 2 小时增量、周日 02:00 全量。 | `internal/schedule`、`/api/v1/schedules` |
| **单表单重跑（Retry-Failed）** | 针对某次运行中失败表单的手动重试，生成新 run。 | `POST runs/retry-failed` |

### 同步策略（按表单二选一）

| 术语 | 定义 | 代码锚点 |
|---|---|---|
| **游标表单（Cursor Form）** | 有稳定主键、走游标分页拉取的表单；全量同步后可反查并清理孤儿数据。 | `cursor_pagination.go`、`cursor_orphan.go` |
| **快照表单（Snapshot Form）** | 无稳定游标、按快照整体重写的表单；快照生命周期 `writing → validated → reconciled / aborted`，TRUNCATE 重写后无孤儿。 | `snapshot.go`（`SnapshotManager`） |

### 写入与对账

| 术语 | 定义 | 代码锚点 |
|---|---|---|
| **Staging + MERGE** | 写入模式：批次先落 staging 表，再 MERGE 进目标表。已存在主键数须在 MERGE **前**统计，否则 `inserted` 恒为 0。 | `sqlserver_writer.go` |
| **孤儿数据（Orphan）** | 目标表中存在、但金蝶源侧快照中已不存在的记录。 | `orphan_reconcile.go` |
| **孤儿清理（Orphan Delete）** | 删除孤儿数据的动作，必须先过安全评估，决策三态：`blocked / auto_approved / approval_required`。输入含源计数、上次源计数、目标计数、重复键、部分写入标志等。 | `orphan_safety.go:EvaluateOrphanDelete` |
| **完整性门控（Write-Complete Gate）** | 只有写入完整（`inserted + updated` 达标）的运行才允许孤儿清理，防止半量写入误判出大量孤儿。 | `isWriteComplete`（`1631797`） |
| **安全帽（Safety Cap）** | 孤儿删除量超过比例上限（10%）时阻断，要求人工审批。 | `cursor_orphan.go` |
| **分区日期守卫（Partition Date Guard）** | 按日期分区写入时的防护校验，避免异常日期数据污染分区。 | `partition_date_guard.go` |
| **抽样校验（Verify Samples）** | 同步后回查目标库抽样记录，生成数据差异报告。 | `verifier.go:VerifySamples` |
| **脏运行恢复（Stale-Run Recovery）** | 启动时把超过 3 小时仍 `running` 的运行标记为 `failed`，清理 panic 遗留脏数据。 | `RecoverStaleRunningRuns`（`186b1ef`） |

### 基础设施

| 术语 | 定义 | 代码锚点 |
|---|---|---|
| **状态库（State DB）** | SQLite 文件（容器 `/app/state/go_state.db`，本地 `.run/state/go_state.db`），存运行历史、表单配置、调度、配置快照等。**表单配置的权威源**。 | `internal/gormdb`、`GORM_DB_PATH` |
| **运行态配置快照（ConfigSnapshot）** | 同步配置的版本化快照，支持回滚。 | `98e7493` P1 |
| **目标库（Target DB）** | SQL Server，业务数据唯一落库位置。 | `internal/db` |

## 应避免的说法

| 避免 | 改用 | 原因 |
|---|---|---|
| Doris | SQL Server / 目标库 | 写入引擎已于 2026-08 迁移，Doris 不再使用（ADR-0001） |
| 影子表 / 切换 / 快照审批（作为现有机制） | Staging + MERGE、孤儿清理 | 该机制已整体移除（ADR-0004） |
| Python 同步 / FastAPI 后端 | Go 同步引擎 | Python 运行时已移除，`docs/DESIGN.md` 是历史文档 |
| 任务（指 Run 时） | 同步运行 / Run | 「任务」在本项目仅指调度（Schedule），避免混淆 |
| 修改 JSON 生效表单配置 | 改状态库 `go_form_queries` | 数据库为权威源（ADR-0002），直接改 JSON 对已有环境无效 |

## 模块地图

```
apps/server/                     Go 后端（module: github.com/kingdee-sync/go）
├── cmd/server/                  服务入口
├── api/routes/v1/               路由层：仅参数绑定与响应封装
└── internal/
    ├── syncengine/              核心：运行编排、游标分页、孤儿对账与安全阀、
    │                            分区守卫、快照、归一化、SQL Server 写入、校验、恢复
    ├── kind/                    金蝶 K/3 API 客户端（登录会话、保活、限流、熔断、重试）
    ├── config/                  ini 配置 + GetFormQuery（DB 优先，JSON 兜底）
    ├── db/ gormdb/              sqlx（目标库轻量查询）/ GORM（状态库）
    ├── schedule/ task/ retry/   cron 调度、任务、重试队列
    ├── circuit/ ratelimit/      gobreaker 熔断、x/time rate 限流（金蝶默认 50 QPS）
    ├── api/contract/            前后端共享的运行状态契约（状态机唯一定义处）
    └── dashboard/ webhook/      看板统计、Webhook/钉钉告警
apps/web/                        React 18 + UmiJS 4 + AntD 5；页面：
                                 overview / dashboard / sync / schedule / data / monitor / system
packages/sync-config/            种子/兜底 form-queries.json（防漂移说明见其 README）
deploy/docker + deploy/scripts   Podman Pod 部署（ADR-0005）与启停脚本
docs/architecture/               当前运行架构（权威）
docs/adr/                        架构决策记录
```

## 历史文档阅读指引

- `docs/DESIGN.md`（2026-08-01 加入）：描述早期 Python + Tauri 桌面愿景，**已过期**，仅作 UI 设计语言参考。
- `docs/architecture/current-runtime.md`：当前唯一生产链路的权威描述。
- `packages/sync-config/README.md`：配置加载优先级与多副本防改错指南（必读）。
