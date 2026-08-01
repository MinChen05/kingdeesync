# Kingdee Sync — 金蝶数据同步平台

将金蝶云星空（K/3 Cloud）业务数据定时同步至 Doris/MySQL/SQL Server，提供 Web 管理界面进行任务调度、运行监控和系统配置。

## 架构概览

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Web 前端    │────▶│  Go 后端 API  │────▶│  金蝶 K/3 API │
│  React+Umi  │◀────│  Gin+GORM    │────▶│  (K3 Cloud)  │
└─────────────┘     └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ Doris/MySQL/ │
                    │ SQL Server   │
                    └──────────────┘
```

## 技术栈

| 层级 | 技术 |
|------|------|
| **后端** | Go 1.25+、Gin、GORM、sqlx、robfig/cron、gobreaker |
| **前端** | TypeScript、React 18、UmiJS 4、Ant Design 5、Tailwind CSS |
| **数据库** | Doris（生产 OLAP）、MySQL（生产）、SQLite（开发/内部状态） |
| **部署** | Podman/Docker + compose |

## 目录结构

```
├── apps/
│   ├── server/          # Go 后端（API、同步引擎、调度器）
│   └── web/             # React 前端（任务管理、运行监控、系统配置）
├── packages/
│   └── sync-config/     # 表单配置与脱敏配置样例
├── deploy/
│   ├── docker/          # Dockerfile、compose.yaml、nginx
│   └── scripts/         # 启动/停止/验证脚本
└── docs/                # 架构决策与文档
```

## 快速开始

### 方式一：容器部署（推荐）

```bash
# 构建并启动
cd deploy/docker
podman-compose up -d --build

# 服务地址
# 前端: http://localhost:8001
# 后端: http://localhost:8000
# 健康检查: http://localhost:8000/health
```

### 方式二：本地开发

```bash
# 1. 准备配置文件
cp config.local.ini.example config.local.ini  # 按需修改

# 2. 启动后端
deploy/scripts/start-server.sh --port 8000

# 3. 启动前端
cd apps/web
pnpm dev
```

## 配置说明

编辑 `config.local.ini`，主要配置段如下：

### 金蝶连接 (`[KINGDEE]`)

| 配置项 | 说明 |
|--------|------|
| `login_url` | 金蝶认证接口地址 |
| `query_url` | 金蝶数据查询接口地址 |
| `acct_id` | 账套 ID |
| `username` / `password` | 登录凭证 |
| `rate_limit_qps` | API 限流（默认 50 QPS） |

### 目标数据库 (`[MYSQL]` / `[SQLSERVER]`)

根据 `[DATABASE] type` 选择使用的数据库段。支持 Doris（MySQL 协议）、MySQL、SQL Server。

### 同步策略 (`[SYNC]`)

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `sync_type` | `incremental`（增量）/ `full`（全量） | `incremental` |
| `default_forms` | 默认同步的表单列表 | 16 个核心表单 |
| `fetch_concurrency` | 金蝶拉取并发数 | 4 |
| `table_concurrency` | 表写入并发数 | 8 |
| `time_window_days` | 增量时间窗口（天） | 30 |

### 同步任务调度

系统默认创建 2 个调度任务（通过 Web 界面管理）：

| 任务 | 频率 | 说明 |
|------|------|------|
| 增量同步 | 周一~周六，每 2 小时 | `0 0 */2 * * 1-6` |
| 全量同步 | 每周日 2:00 | `0 0 2 * * 0` |

### 支持的业务表单

发货通知单、生产入库单、销售订单、销售出库单、销售退货单、预测订单、生产订单主表、生产订单明细、客户资料、生产用料清单主表、生产用料清单明细表、科目余额表、即时库存、物料、仓库、物料清单、物料清单子项、采购订单、采购入库单、委外订单、应付单、应收单。

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `GET` | `/api/v1/overview` | 同步概览 |
| `GET` | `/api/v1/runs` | 运行记录列表 |
| `GET` | `/api/v1/runs/:runId` | 运行详情 |
| `GET` | `/api/v1/runs/:runId/events` | 运行事件流 |
| `POST` | `/api/v1/runs` | 手动触发同步 |
| `GET` | `/api/v1/schedules` | 调度任务列表 |
| `POST` | `/api/v1/schedules` | 创建调度任务 |
| `PUT` | `/api/v1/schedules/:id` | 更新调度任务 |
| `DELETE` | `/api/v1/schedules/:id` | 删除调度任务 |
| `GET` | `/api/v1/forms` | 表单列表 |
| `GET` | `/api/v1/system/config` | 系统配置 |
| `PUT` | `/api/v1/system/config` | 更新系统配置 |

## 本地验证

```bash
# 后端测试
cd apps/server && go test ./...

# 前端测试
cd apps/web && pnpm test
```

## 部署

```bash
# 启动
cd deploy/docker && podman-compose up -d --build

# 停止
deploy/scripts/stop-server.sh

# 查看日志
podman logs -f kingdee-sync-api
```

## 许可证

私有项目，内部使用。
