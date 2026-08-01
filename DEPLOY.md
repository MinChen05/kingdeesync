# 部署指南

## 运行资产

- Go 服务：`apps/server`
- React 前端：`apps/web`
- 表单配置：`packages/sync-config/form-queries.json`
- 本地敏感配置：`config.local.ini`，不得提交
- 本地同步历史：`go_state.db`，按部署需要备份

## 本地启动

```bash
deploy/scripts/start-server.sh --port 8080
```

脚本会构建 `apps/server/cmd/server`，设置 `SYNC_CONFIG_DIR=packages/sync-config`，并在 `.run/` 中保存二进制、PID 与日志。

## 容器构建

```bash
docker build -f deploy/docker/Dockerfile -t kingdee-sync:latest .
docker compose -f deploy/docker/compose.yaml up -d
```

容器运行时挂载根目录的 `config.local.ini` 和 `packages/sync-config/`。生产环境应通过受控渠道保存金蝶与 Doris 凭据，禁止将凭据写入镜像或版本库。

## 验证

```bash
curl -fsS http://127.0.0.1:8080/health
curl -fsS http://127.0.0.1:8080/ready
```

前端通过 `/api/sync/start` 启动同步；Go 服务直接写入 Doris 主表。
