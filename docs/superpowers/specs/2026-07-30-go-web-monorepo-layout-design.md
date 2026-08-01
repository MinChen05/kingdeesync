# Go + Web 单仓目录重构设计

## 背景

项目已完成从 Python 同步链路到 Go 服务和 React 前端的切换，但仓库根目录仍混有旧 Python 结构、历史前端、构建产物、缓存与过期文档。当前运行时实际依赖为 Go 服务、React 前端、表单配置 JSON、Doris 配置和部署文件。

本次重构将运行资产收敛为唯一单仓结构，不改变同步业务规则、Doris 主表或 API 契约。

## 目标

```text
apps/
  server/                 Go 服务模块
  web/                    React 前端模块
packages/
  sync-config/            运行期表单配置与配置样例
deploy/
  docker/                 容器构建和编排
  scripts/                构建、启动与运维脚本
docs/
  architecture/           当前架构与运维文档
  superpowers/            历史设计、计划和验收报告
```

运行链路固定为：

```text
apps/web -> /api -> apps/server -> Kingdee API / Doris
                     |
                     +-> packages/sync-config/form-queries.json
```

## 迁移边界

### 保留并迁移

- `go/` 迁移至 `apps/server/`，保留 Go module、`cmd/`、`internal/`、`api/` 和 `testdata/`。
- `frontend/` 迁移至 `apps/web/`，保留当前 Umi/React 前端源码、锁文件和前端测试。
- 删除 `frontend/.git/`，使前端源码成为主仓的一部分；保留但不提交 `apps/web/node_modules/`。
- `src/config/form-queries.json` 迁移至 `packages/sync-config/form-queries.json`。
- `Dockerfile`、`docker-compose.yml` 与 Go 启动脚本迁移至 `deploy/`，并改为引用新目录。
- `config.local.ini` 继续作为未跟踪本地运行配置；新增脱敏 `config.example.ini` 放入 `packages/sync-config/`。
- `apps/server/cmd/` 仅保留常驻服务入口与仍被运维调用的诊断命令。

### 删除

- `frontend-legacy/`。
- Python 已删除后遗留的 `dist/`、`.pytest_cache/`、`.ruff_cache/`、旧 Python 打包目录和无效启动器。
- 仍描述 Python 作为主链路的 README、部署和架构文档。
- 已失效的影子表迁移 CLI：`cutover-sync`、`window-sync`、`snapshot-approve`、`snapshot-replay`、`cleanup-shadow` 及其专用测试。
- 不再存在调用方的 Python 验收与旧切换脚本。

### 不处理

- `.worktrees/`：独立工作树，保持不变。
- `docs/superpowers/reports/`：保留为历史验收证据。
- Doris 主表、SQLite 同步运行记录和本地 `config.local.ini`：不由目录迁移修改。

## 服务配置定位

Go 配置加载器改为按以下优先级定位：

1. `SYNC_CONFIG_DIR` 指向的目录。
2. 可执行文件相邻的 `packages/sync-config/`。
3. 仓库开发模式的 `packages/sync-config/`。

表单配置不再依赖当前工作目录或 `src/config/`。Docker 与本地启动脚本均设置 `SYNC_CONFIG_DIR=/app/packages/sync-config`。

## 构建与部署

- 前端从 `apps/web/` 构建到 `apps/web/dist/`。
- Go 服务从 `apps/server/cmd/server` 构建为单一二进制。
- Docker 构建上下文仍是仓库根目录；镜像仅复制 Go 二进制、前端构建产物、`packages/sync-config/` 和运行配置挂载点。
- `deploy/scripts/` 提供唯一的本地构建、启动和停止入口，移除已失效的 Python/旧 GUI 启动入口。

## 验证

1. `go test ./...` 在 `apps/server/` 通过。
2. `npm run lint` 与 `npm test` 在 `apps/web/` 通过。
3. 容器构建能找到 Go 二进制、前端产物和表单配置。
4. 服务启动后 `/health`、`/ready`、`/api/forms` 可用。
5. `/api/sync/start` 的空表单请求仍选择 22 张配置表单。
6. 仓库根目录不再包含项目 Python 源码、Python 依赖或旧前端运行资产。

## 风险与回滚

目录迁移不改变数据库数据。若新启动路径失败，可通过 Git 还原目录映射；`config.local.ini` 与数据库均不受该操作影响。迁移期间不得删除 `.worktrees/` 或验收报告。
