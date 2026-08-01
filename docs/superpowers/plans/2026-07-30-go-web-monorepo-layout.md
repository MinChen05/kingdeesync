# Go + Web 单仓目录重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Go 服务和 React 前端迁移至 `apps/` 单仓结构，移除旧前端、废弃迁移命令和派生产物，并保持同步 API 可用。

**Architecture:** `apps/server` 是唯一后端模块，`apps/web` 是唯一前端模块，`packages/sync-config` 存放运行期表单配置。`deploy/` 存放 Docker 和运维脚本，Go 通过 `SYNC_CONFIG_DIR` 定位配置。

**Tech Stack:** Go、Gin、Doris、SQLite/GORM、React、Umi Max、Ant Design、Docker、Bash。

---

### Task 1: 创建配置包并解耦工作目录

**Files:** Move `src/config/form-queries.json` to `packages/sync-config/form-queries.json`; create `packages/sync-config/config.example.ini`; modify `go/internal/config/config.go` and `go/internal/config/config_test.go`.

- [ ] 添加 `TestFormQueryCandidatesPreferConfiguredDirectory`：设置 `SYNC_CONFIG_DIR` 后，断言候选首项为 `$SYNC_CONFIG_DIR/form-queries.json`。
- [ ] 运行 `cd go && go test ./internal/config -run TestFormQueryCandidatesPreferConfiguredDirectory -count=1`，预期因候选函数不存在而失败。
- [ ] 实现 `formQueryCandidates(configPath string) []string`：优先读取 `SYNC_CONFIG_DIR/form-queries.json`，随后读取 `<configDir>/packages/sync-config/form-queries.json` 与 `<configDir>/form-queries.json`。
- [ ] 让 `loadFormQueries` 遍历上述候选；移动 JSON；新增不含真实凭据的 `config.example.ini`。
- [ ] 运行 `cd go && go test ./internal/config -count=1`，预期通过；提交 `refactor: move runtime config into package`。

### Task 2: 迁移 Go 服务至 apps/server

**Files:** Move `go/` to `apps/server/`; move `scripts/start-go-server.sh` and `scripts/stop-go-server.sh` to `deploy/scripts/`; modify `apps/server/cmd/server/main.go` and its tests.

- [ ] 添加 `TestDefaultConfigDirectory`，断言可执行文件 `/opt/kingdee/server` 的默认配置目录为 `/opt/kingdee/packages/sync-config`。
- [ ] 运行 `cd apps/server && go test ./cmd/server -run TestDefaultConfigDirectory -count=1`，预期因函数不存在而失败。
- [ ] 执行 `mkdir -p apps && mv go apps/server`，在服务启动前设置缺省 `SYNC_CONFIG_DIR` 为可执行文件同级 `packages/sync-config`。
- [ ] 更新启动脚本：从 `apps/server` 构建 `.run/server`，并用 `SYNC_CONFIG_DIR="$PROJECT_ROOT/packages/sync-config"` 启动。
- [ ] 运行 `cd apps/server && go test ./... && go build ./cmd/server`，预期通过；提交 `refactor: move go service into apps server`。

### Task 3: 迁移 React 前端至 apps/web

**Files:** Move `frontend/` to `apps/web/`; delete `frontend-legacy/`; modify `apps/server/cmd/server/main.go`; test `apps/web/src/services/api.test.ts`.

- [ ] 添加 `TestFrontendDistCandidatesUseAppsWeb`，断言静态资源候选包含 `/opt/kingdee/apps/web/dist`。
- [ ] 运行 `cd apps/server && go test ./cmd/server -run TestFrontendDistCandidatesUseAppsWeb -count=1`，预期失败。
- [ ] 执行 `rm -rf frontend/.git && mv frontend apps/web && rm -rf frontend-legacy`；保留但不提交 `apps/web/node_modules/`，将静态资源候选改为 `apps/web/dist`、`../apps/web/dist` 和可执行文件相邻 `apps/web/dist`，保持 API 路由优先注册。
- [ ] 运行 `cd apps/web && npm test -- --run src/services/api.test.ts && npm run build`，预期通过且产物在 `apps/web/dist/`；提交 `refactor: move web client into apps web`。

### Task 4: 迁移部署资产

**Files:** Move `Dockerfile` to `deploy/docker/Dockerfile`; move `docker-compose.yml` to `deploy/docker/compose.yaml`; move `scripts/build-and-run.sh` to `deploy/scripts/build-and-run.sh`; create `deploy/scripts/verify-layout.sh`.

- [ ] 创建布局检查脚本，断言存在 `apps/server/go.mod`、`apps/web/package.json`、`packages/sync-config/form-queries.json`、`deploy/docker/Dockerfile`。
- [ ] 执行 `mkdir -p deploy/docker` 后移动 Docker、Compose 和构建脚本。
- [ ] Dockerfile 复制 `.run/server`、`apps/web/dist`、`packages/sync-config` 并设置 `SYNC_CONFIG_DIR=/app/packages/sync-config`；Compose 挂载本地配置与 `packages/sync-config`。
- [ ] 构建脚本改为在 `apps/web` 和 `apps/server` 执行，并复制配置至 `.run/packages/sync-config/`。
- [ ] 运行 `bash deploy/scripts/verify-layout.sh && docker build -f deploy/docker/Dockerfile -t kingdee-sync:layout-check .`，预期通过；提交 `refactor: centralize deployment assets`。

### Task 5: 删除失效运行资产并更新文档

**Files:** Delete `apps/server/cmd/cutover-sync/`, `window-sync/`, `snapshot-approve/`, `snapshot-replay/`, `cleanup-shadow/`, `dist/`, `.pytest_cache/`, `.ruff_cache/`, `checkpoints/`; modify `README.md`; create `docs/architecture/current-runtime.md`.

- [ ] 创建 `deploy/scripts/verify-runtime-commands.sh`，断言保留 `apps/server/cmd/server` 与 `apps/server/cmd/check_org`，所有影子表/切换 CLI 均不存在。
- [ ] 运行该脚本，预期在删除前失败。
- [ ] 删除上述命令和派生产物；不得删除 `.worktrees/` 或 `docs/superpowers/reports/`。
- [ ] 将 README 改为 Go + React 启动、测试和部署说明；新架构文档声明唯一同步链路为 React → Go → Kingdee API/Doris，正式 MSSQL 仅作只读核对。
- [ ] 运行 `bash deploy/scripts/verify-runtime-commands.sh` 及 `find . -type f -name '*.py' -not -path './.worktrees/*' -not -path './apps/web/node_modules/*' -print`，预期检查通过且后者无输出；提交 `chore: remove obsolete migration runtime`。

### Task 6: 端到端验收

**Files:** Modify `apps/server/internal/syncengine/engine_test.go` and `deploy/scripts/verify-layout.sh`.

- [ ] 新增 `TestConfiguredFormsContainAllProductionForms`，加载 `packages/sync-config/form-queries.json` 并断言 22 张表单包含“物料”“科目余额表”“生产用料清单明细表”。
- [ ] 运行 `cd apps/server && go test ./...`、`cd ../web && npm run lint && npm test`、`cd ../.. && git diff --check`，预期通过。
- [ ] 运行 `SYNC_CONFIG_DIR="$PWD/packages/sync-config" deploy/scripts/start-server.sh --port 18000`，并访问 `/health`、`/ready`、`/api/forms`；预期前两个端点成功，表单端点返回 22 项。
- [ ] 提交 `test: verify monorepo runtime layout`。
