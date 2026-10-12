# ADR-0005: 部署采用 Podman Pod 模式，nginx 经 127.0.0.1 直连后端

- **状态**：Accepted
- **日期**：2026-08-06（提交 `a6212b5`，前奏 `16a4a98`、`e375e42`）
- **相关**：`deploy/scripts/build-and-run.sh`、`deploy/docker/nginx.conf`

## 背景

前后端分容器部署时，nginx 需解析后端容器名。Podman 内置 DNS（10.89.0.1）
在部分网络环境不可达，导致 nginx 无法解析 `kingdee-sync-api`，前端稳定 502。
此前的两次缓解（`e375e42` resolver 动态解析、`16a4a98` entrypoint 优先 IP 直连）
都依赖 DNS 或启动时序，未根治。

## 决策

放弃容器名 DNS 依赖，改用 **Podman Pod**：

- `build-and-run.sh` 以 `podman pod` + `podman run --pod` 组织前后端容器，
  两容器共享网络命名空间。
- nginx 直接反代 `127.0.0.1:8000`，不再做任何服务发现。
- `web-entrypoint.sh` 简化为直接启动 nginx。
- `compose.yaml` 降级为参考文档，不再是执行入口。
- 状态库经 bind mount 持久化（`GORM_DB_PATH` → `/app/state/`，`137190e`），
  容器重建不丢同步历史。

## 后果

- 正面：彻底消除 DNS 故障面；后端重启不影响前端（同 Pod 内回环直达）。
- 负面：部署入口从 compose 变为自研脚本，可移植性下降（仅适配 Podman）；
  换 compose 编排需重新解决服务发现问题。
