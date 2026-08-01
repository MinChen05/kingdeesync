# Kingdee Sync

Kingdee Sync 是一个以 Go 服务和 React 前端构成的数据同步系统。同步链路为：React 前端 → Go API → Kingdee API / Doris。

## 目录

- `apps/server`：Go 服务、同步引擎与 API。
- `apps/web`：React/Umi 前端。
- `packages/sync-config`：表单配置和脱敏配置样例。
- `deploy`：容器与本地运维脚本。
- `docs`：架构、运行和验收资料。

## 本地验证

```bash
cd apps/server && go test ./...
cd ../web && npm run lint && npm test
```

## 启动

创建本地 `config.local.ini` 后：

```bash
deploy/scripts/start-server.sh --port 8080
```

服务读取 `packages/sync-config/form-queries.json`，可通过 `SYNC_CONFIG_DIR` 覆盖配置目录。
