# Podman 前后端双服务部署设计

## 目标

将金蝶数据同步项目部署为两个由 Podman 管理的容器：前端对外提供 `8001` 端口，后端对外提供 `8000` 端口。

## 架构

`kingdee-sync-web` 使用 Nginx 提供 `apps/web/dist` 中的静态资源，并把 `/api`、`/health` 和 `/ready` 转发给同一私有网络中的 `kingdee-sync-api`。

`kingdee-sync-api` 运行 Go 服务，监听容器内的 `8000` 端口。它只读挂载根目录 `config.local.ini` 和 `packages/sync-config`，并把日志及 SQLite 状态持久化到项目根目录下的运行目录。

两个容器连接到独立的 `kingdee-sync-net` bridge 网络。前端访问同源的相对 API 路径，因此不依赖浏览器跨域访问；后端的 `8000` 映射仍保留给运维健康检查和 API 调试。

## 容器资产

- 后端镜像：使用 Go 构建阶段生成 Linux 静态二进制，再以精简运行时镜像启动服务。
- 前端镜像：使用 Node 构建 Umi 静态站点，再由 Nginx 运行时镜像提供服务和代理。
- Compose：定义两个服务、端口映射、只读配置挂载、可写状态与日志挂载、健康检查和专用网络。
- Nginx：前端路由回退到 `index.html`；`/api/`、`/health` 和 `/ready` 代理到 `http://kingdee-sync-api:8000`。

## 配置与安全

- `config.local.ini` 不复制进镜像，也不提交版本库。
- 容器以只读方式使用业务配置，运行时生成的数据仅落在挂载目录。
- 后端 CORS 允许前端源 `http://localhost:8001`，以支持直接请求后端端口的运维场景。

## 验收

1. `podman compose -f deploy/docker/compose.yaml up -d --build` 成功创建两个容器。
2. `http://127.0.0.1:8000/health` 返回 HTTP 200 和 `status: ok`。
3. `http://127.0.0.1:8000/ready` 返回服务实际就绪状态；若外部 Doris 不可达，可返回 HTTP 503 并提供原因。
4. `http://127.0.0.1:8001/` 返回前端 HTML，且前端的 `/api` 请求经 Nginx 到达后端。
5. 重启容器后，挂载目录中的日志和 SQLite 状态仍存在。

## 非目标

- 不创建或修改 Doris、金蝶或 MSSQL 容器。
- 不删除其他无关 Podman 镜像、卷或网络。
- 不改变应用同步逻辑或 API 契约。
