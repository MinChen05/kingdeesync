# Kingdee Sync

[![Go + React Baseline](https://github.com/MinChen05/kingdeesync/actions/workflows/go-react.yml/badge.svg?branch=master)](https://github.com/MinChen05/kingdeesync/actions/workflows/go-react.yml)

将金蝶云星空（K/3 Cloud）的业务表单数据定时同步至 SQL Server，并提供任务调度、手动同步、运行监控、表单配置和系统维护的 Web 管理台。

## 核心能力

- **增量与全量同步**：支持手动触发、Cron 调度、停止运行和失败表单重试。
- **两类同步策略**：有稳定主键的表单使用游标分页；快照表单按完整快照重写。
- **可靠写入**：SQL Server 使用 Staging + MERGE，写入完成后执行抽样校验和孤儿数据对账。
- **安全清理**：孤儿删除经过完整性门控、比例安全帽和审批状态评估，避免半量写入误删数据。
- **运行监控**：记录运行、表单统计和事件，提供趋势看板、异常日志、健康诊断和运行详情。
- **配置管理**：表单元数据、字段映射、查询过滤、调度任务和配置快照均可在管理台维护。
- **异常告警**：支持通用 Webhook 和钉钉通知，钉钉仅在异常运行时推送。

## 架构

```text
                         Podman Pod: kingdee-sync
┌───────────────────────────────────────────────────────────────┐
│                                                               │
│  Browser                                                      │
│     │                                                         │
│     ▼                                                         │
│  Nginx :8001 ── /api/* ──▶ Go API :8000 ──▶ 金蝶 K/3 API       │
│     │                         │                               │
│     │                         ├───────────▶ SQL Server         │
│     │                         │              （业务数据）      │
│     │                         │                               │
│     └── React 静态资源         └───────────▶ SQLite             │
│                                             （运行状态与配置）  │
└───────────────────────────────────────────────────────────────┘
```

生产链路唯一为：

```text
apps/web -> /api -> apps/server -> Kingdee API / SQL Server
```

Nginx 与 API 位于同一 Pod、共享网络命名空间，因此 Nginx 通过 `127.0.0.1:8000` 反向代理，不依赖容器 DNS。

## 技术栈

| 层级 | 技术 |
|---|---|
| 后端 | Go 1.25、Gin、GORM、sqlx、robfig/cron、gobreaker、x/time rate |
| 前端 | React 18、TypeScript、UmiJS 4、Ant Design 6、Pro Components、TanStack Query |
| 样式与图表 | Tailwind CSS 4、Less、Ant Design Charts |
| 业务数据库 | SQL Server |
| 状态数据库 | SQLite |
| 测试与质量 | Go testing、Vitest、Testing Library、Biome、GitHub Actions |
| 部署 | Podman Pod、Nginx、多阶段镜像构建 |

## 目录结构

```text
.
├── apps/
│   ├── server/                  Go API、同步引擎、调度器与恢复逻辑
│   └── web/                     React 管理台
├── packages/
│   └── sync-config/             表单查询种子配置与配置说明
├── deploy/
│   ├── docker/                  API/Web Dockerfile 与 Nginx 配置
│   └── scripts/                 构建、启停、验证与部署脚本
├── docs/
│   ├── architecture/            当前运行架构
│   └── adr/                     架构决策记录
├── scripts/                     SQL 辅助脚本与接口检查工具
├── CHANGELOG.md                 生产发布与回滚记录
└── CONTEXT.md                   领域词汇表与模块地图
```

## 快速开始

### 环境要求

- Go 1.25 及以上
- Node.js 22、pnpm 11
- 可访问的金蝶 K/3 Cloud 与 SQL Server
- 容器部署需要 Podman

### 1. 创建配置

在仓库根目录创建 `config.local.ini`。该文件包含真实凭据，已被 `.gitignore` 排除，禁止提交。

```ini
[KINGDEE]
login_url = https://your-kingdee-host/k3cloud/login
query_url = https://your-kingdee-host/k3cloud/query
acct_id = your_account_id
username = your_username
password = your_password
lcid = 2052
page_size = 10000
rate_limit_qps = 50

[DATABASE]
type = sqlserver

[SQLSERVER]
host = your-sqlserver-host
port = 1433
user = your_user
password = your_password
database = Kingdee

[SYNC]
sync_type = incremental
time_window_days = 30
table_concurrency = 8
```

可选字段与基础格式可参考 [config.example.ini](packages/sync-config/config.example.ini) 和 [config.go](apps/server/internal/config/config.go)。

### 2. 本地开发

```bash
# 启动后端，监听 8000
bash deploy/scripts/start-server.sh --port 8000

# 启动前端，监听 8001
cd apps/web
pnpm install --frozen-lockfile
pnpm dev
```

访问 `http://127.0.0.1:8001`。开发服务器会把 `/api/*` 代理到 `http://127.0.0.1:8000`。

停止本地后端：

```bash
bash deploy/scripts/stop-server.sh
```

### 3. 容器部署

```bash
bash deploy/scripts/build-and-run.sh
```

部署脚本会：

1. 构建 API 和 Web 镜像；构建全部成功后才替换现有 Pod。
2. 将状态库、日志和同步配置从宿主机挂载到容器。
3. 等待 API 与 Web 健康检查通过，再将新镜像标记为 `latest`。

部署后访问：

| 服务 | 地址 |
|---|---|
| 管理台 | `http://localhost:8001` |
| API | `http://localhost:8000` |
| 健康检查 | `http://localhost:8000/health` |
| 就绪检查 | `http://localhost:8000/ready` |

需要钉钉异常告警时，在 `deploy/deploy.env` 中提供：

```dotenv
DINGTALK_WEBHOOK_URL=
DINGTALK_WEBHOOK_SECRET=
```

该文件已被 `.gitignore` 排除，不要提交或写入镜像。

## 配置与状态

### 配置段

| 配置段 | 用途 |
|---|---|
| `[KINGDEE]` | 金蝶登录地址、查询地址、账套与凭证、分页和限流 |
| `[DATABASE]` | 目标库类型，当前生产使用 `sqlserver` |
| `[SQLSERVER]` | SQL Server 主机、端口、账号、密码和数据库名 |
| `[SYNC]` | 同步类型、时间窗口、并发、超时和目标库探活 |
| `[INCREMENTAL_FIELDS]` | 表单对应的增量时间字段 |

### 关键环境变量

| 变量 | 说明 |
|---|---|
| `LISTEN_ADDR` / `LISTEN_PORT` | API 监听地址与端口 |
| `GORM_DB_PATH` | SQLite 状态库路径 |
| `SYNC_CONFIG_DIR` | 表单查询种子配置目录 |
| `DINGTALK_WEBHOOK_URL` | 钉钉机器人地址 |
| `DINGTALK_WEBHOOK_SECRET` | 钉钉签名密钥 |

### 状态库与表单配置

- 状态库保存运行历史、表单统计、事件、调度任务、配置快照和表单查询配置。
- 容器路径为 `/app/state/go_state.db`，宿主机路径为 `.run/state/go_state.db`。
- `go_form_queries` 表是表单配置的**运行时权威源**。
- [form-queries.json](packages/sync-config/form-queries.json) 仅在全新状态库初始化时灌入，之后作为缺失记录的兜底。
- 修改已有表单配置应通过管理台或 API；直接编辑 JSON 不会覆盖已初始化的数据库。

详细规则见 [packages/sync-config/README.md](packages/sync-config/README.md)。

## 同步机制

| 机制 | 说明 |
|---|---|
| 增量同步 | 按时间窗口和表单的增量字段拉取变更数据 |
| 全量同步 | 拉取表单完整结果，用于初始化、修复或周期性校准 |
| 游标表单 | 使用稳定主键分页，可在完整同步后反查并清理孤儿记录 |
| 快照表单 | 以完整快照重写目标数据，避免无稳定游标带来的遗漏 |
| Staging + MERGE | 批次先写入 staging 表，再合并进目标表 |
| 完整性门控 | 写入量异常时不进入孤儿清理 |
| 安全帽与审批 | 孤儿删除超过阈值时阻断，要求人工评估 |
| 抽样校验 | 同步后回查目标库，生成数据差异 |
| 异常恢复 | 启动时识别异常中断的运行并执行恢复流程 |

默认调度：

| 任务 | Cron | 说明 |
|---|---|---|
| 增量同步 | `0 0 */2 * * 1-6` | 周一至周六每 2 小时 |
| 全量同步 | `0 0 2 * * 0` | 每周日 02:00 |

调度任务可在管理台按需启停、修改或批量操作。

## 管理台页面

| 路径 | 页面 | 主要用途 |
|---|---|---|
| `/overview` | 系统概览 | 实时状态、核心指标、趋势、异常与最近运行 |
| `/dashboard` | 数据看板 | 数据量、表单排名和同步趋势 |
| `/sync` | 同步管理 | 手动增量/全量同步、进度与日志 |
| `/schedule` | 任务调度 | 调度启停、任务筛选、编辑与批量操作 |
| `/data` | 数据配置 | 表单启停、查询条件与字段映射 |
| `/monitor` | 监控分析 | 运行历史、错误日志、详情抽屉与健康诊断 |
| `/system` | 系统管理 | 连接配置、维护归档、版本与系统信息 |

管理台统一支持桌面与移动布局，并适配 `prefers-reduced-motion`。

## API 概览

完整路由以 [apps/server/api/routes/v1](apps/server/api/routes/v1) 为准。

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/health`、`/ready` | 进程健康与依赖就绪 |
| `GET` | `/api/v1/overview` | 同步概览 |
| `GET` / `POST` | `/api/v1/runs` | 运行列表 / 手动启动同步 |
| `GET` | `/api/v1/runs/:runId` | 运行详情 |
| `GET` | `/api/v1/runs/:runId/events` | 运行事件 |
| `POST` | `/api/v1/runs/:runId/retry-failed` | 重试失败表单 |
| `GET` / `POST` | `/api/v1/sync/status`、`/api/v1/sync/stop` | 当前状态 / 停止同步 |
| `GET` / `POST` / `PUT` / `DELETE` | `/api/v1/schedules` | 调度任务管理 |
| `GET` / `PUT` | `/api/v1/forms` | 表单列表与配置更新 |
| `GET` | `/api/v1/datasources` | 数据源状态 |
| `GET` / `PUT` | `/api/v1/system/config` | 系统配置 |
| `GET` | `/api/v1/system/diagnostics` | 系统诊断 |
| `POST` | `/api/v1/system/test-connections` | 连接测试 |
| `POST` | `/api/v1/system/archive` | 运行历史归档 |

同一运行时刻只允许一个同步任务；重复启动返回冲突状态。

## 开发与测试

### 后端

```bash
cd apps/server

gofmt -l .
go vet ./...
go test -race ./...
```

真实 SQL Server 集成测试默认跳过，需要设置 `MSSQL_INTEGRATION=1` 并使用可访问的 `config.local.ini`。

### 前端

```bash
cd apps/web

pnpm install --frozen-lockfile
pnpm tsc
pnpm test
pnpm build
```

### CI

[.github/workflows/go-react.yml](.github/workflows/go-react.yml) 在每次推送和 PR 时执行：

- Go：`gofmt`、`go vet`、`go test -race`
- React：TypeScript、Vitest、生产构建

## 运维

```bash
# 查看容器状态
podman ps --filter name=kingdee-sync

# 查看日志
podman logs -f kingdee-sync-api
podman logs -f kingdee-sync-web

# 停止 / 启动整个 Pod
podman pod stop kingdee-sync
podman pod start kingdee-sync
```

发布前应备份 `.run/state/go_state.db`。发布记录、镜像标签和回滚信息见 [CHANGELOG.md](CHANGELOG.md)。

`deploy/docker/compose.yaml` 仅作参考，实际生产入口是 `deploy/scripts/build-and-run.sh`。

## 安全说明

- `config.local.ini`、`deploy/deploy.env`、`.run/`、数据库和运行日志均不得提交。
- 管理台当前未内置用户认证与权限体系，应部署在可信内网，或置于带认证的反向代理之后。
- 对外暴露前应限制网络访问范围，并妥善保护金蝶、SQL Server 和 Webhook 凭据。

## 文档

- [CONTEXT.md](CONTEXT.md)：领域词汇、模块边界与术语约束
- [当前运行架构](docs/architecture/current-runtime.md)：生产链路与运行组件
- [ADR](docs/adr/)：关键架构决策记录
- [表单配置说明](packages/sync-config/README.md)：配置优先级与防漂移规则
- [变更记录](CHANGELOG.md)：生产发布、验证与回滚信息

## 许可

内部业务项目，未声明开源许可证。
