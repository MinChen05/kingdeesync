# Podman 双服务部署 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Podman 中部署可通过 `8001` 访问的前端和可通过 `8000` 访问的后端。

**Architecture:** Go 后端和 Nginx 前端分别构建为独立镜像，并加入同一个私有 bridge 网络。Nginx 提供静态资源，把同源的 API、健康检查请求转发到后端服务；Compose 负责端口、配置、状态和日志挂载。

**Tech Stack:** Podman Compose、Go、Umi、Node.js、Nginx、Dockerfile。

---

### Task 1: 固化后端运行镜像

**Files:**
- Modify: `deploy/docker/Dockerfile`
- Test: `deploy/scripts/verify-runtime-commands.sh`

- [ ] **Step 1: 运行现有运行时布局检查**

Run: `deploy/scripts/verify-runtime-commands.sh`
Expected: exit code 0。

- [ ] **Step 2: 将 Dockerfile 改为可独立构建的 Go 多阶段镜像**

使用 `golang:1.25-alpine` 构建 `apps/server/cmd/server`，将生成的 `/out/server`、`packages/sync-config` 和必要 CA 证书复制到运行镜像；运行镜像设置：

```dockerfile
ENV LISTEN_ADDR=0.0.0.0 LISTEN_PORT=8000 TZ=Asia/Shanghai \
    SYNC_CONFIG_DIR=/app/packages/sync-config
EXPOSE 8000
ENTRYPOINT ["/app/server"]
```

不得将 `config.local.ini`、日志或 SQLite 状态复制到镜像。

- [ ] **Step 3: 构建后端镜像**

Run: `podman build -f deploy/docker/Dockerfile -t kingdee-sync-api:local .`
Expected: exit code 0，镜像标签为 `kingdee-sync-api:local`。

- [ ] **Step 4: 再次运行运行时布局检查**

Run: `deploy/scripts/verify-runtime-commands.sh`
Expected: exit code 0。

### Task 2: 增加前端 Nginx 镜像与同源代理

**Files:**
- Create: `deploy/docker/web.Dockerfile`
- Create: `deploy/docker/nginx.conf`

- [ ] **Step 1: 写入 Nginx 配置**

在 `server` 块中提供静态站点和 SPA 回退，并声明以下代理：

```nginx
location /api/ { proxy_pass http://kingdee-sync-api:8000; }
location = /health { proxy_pass http://kingdee-sync-api:8000/health; }
location = /ready { proxy_pass http://kingdee-sync-api:8000/ready; }
location / { try_files $uri $uri/ /index.html; }
```

代理请求设置 `Host`、`X-Real-IP` 与 `X-Forwarded-For` 头。

- [ ] **Step 2: 写入前端多阶段 Dockerfile**

第一阶段从 `node:22-alpine` 在 `/app/apps/web` 运行 `npm ci --ignore-scripts` 与 `npm run build`；第二阶段从 `nginx:1.27-alpine` 复制 `dist` 和 Nginx 配置，并公开 `80` 端口。

- [ ] **Step 3: 构建前端镜像**

Run: `podman build -f deploy/docker/web.Dockerfile -t kingdee-sync-web:local .`
Expected: exit code 0，镜像标签为 `kingdee-sync-web:local`。

### Task 3: 定义 Podman Compose 运行拓扑

**Files:**
- Modify: `deploy/docker/compose.yaml`
- Modify: `DEPLOY.md`

- [ ] **Step 1: 用双服务定义替换现有 Compose 文件**

定义 `kingdee-sync-api` 与 `kingdee-sync-web`：

```yaml
services:
  kingdee-sync-api:
    build: { context: ../.., dockerfile: deploy/docker/Dockerfile }
    ports: ["8000:8000"]
  kingdee-sync-web:
    build: { context: ../.., dockerfile: deploy/docker/web.Dockerfile }
    ports: ["8001:80"]
    depends_on: [kingdee-sync-api]
```

后端使用 `restart: unless-stopped`、`config.local.ini` 与表单配置的只读挂载，以及 `.run/logs`、`.run/state` 的可写挂载；两个服务使用 `kingdee-sync-net`，并为后端配置 `/health` 健康检查。

- [ ] **Step 2: 更新部署说明**

将部署命令统一为：

```bash
podman compose -f deploy/docker/compose.yaml up -d --build
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8001/health
```

说明前端入口为 `http://127.0.0.1:8001`、后端入口为 `http://127.0.0.1:8000`，并保留停止与查看日志命令。

- [ ] **Step 3: 校验 Compose 展开结果**

Run: `podman compose -f deploy/docker/compose.yaml config`
Expected: exit code 0，且包含两个服务、两个端口映射和 `kingdee-sync-net`。

### Task 4: 运行部署并验证

**Files:**
- Modify: `deploy/scripts/build-and-run.sh`
- Test: `deploy/scripts/verify-runtime-commands.sh`

- [ ] **Step 1: 让部署脚本调用 Compose**

将脚本的运行阶段替换为：

```bash
mkdir -p "$PROJECT_ROOT/.run/logs" "$PROJECT_ROOT/.run/state"
podman compose -f "$PROJECT_ROOT/deploy/docker/compose.yaml" up -d --build
curl -fsS --retry 10 --retry-delay 1 http://127.0.0.1:8000/health
curl -fsS --retry 10 --retry-delay 1 http://127.0.0.1:8001/health
```

删除与旧单容器 `8080` 运行方式相关的构建、挂载和输出。

- [ ] **Step 2: 运行部署脚本**

Run: `deploy/scripts/build-and-run.sh`
Expected: 两个容器均为 running，且脚本以 exit code 0 结束。

- [ ] **Step 3: 验证后端、前端和代理路径**

Run: `curl -fsS http://127.0.0.1:8000/health && curl -fsS http://127.0.0.1:8001/health && curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8001/`
Expected: 两个健康检查返回 JSON 中的 `status: ok`，主页状态码为 `200`。

- [ ] **Step 4: 检查容器状态与日志**

Run: `podman compose -f deploy/docker/compose.yaml ps && podman logs --tail 100 kingdee-sync-api`
Expected: 两个服务为 running；后端日志中无启动失败或配置加载失败。

- [ ] **Step 5: 提交部署配置**

Run: `git add deploy/docker/Dockerfile deploy/docker/web.Dockerfile deploy/docker/nginx.conf deploy/docker/compose.yaml deploy/scripts/build-and-run.sh DEPLOY.md && git commit -m "feat: deploy web and api with podman"`
Expected: 只提交上述部署相关文件。
