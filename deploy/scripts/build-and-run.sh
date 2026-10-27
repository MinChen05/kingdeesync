#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

command -v podman >/dev/null || { echo "Podman is required" >&2; exit 1; }
test -f "$PROJECT_ROOT/config.local.ini" || { echo "config.local.ini is required" >&2; exit 1; }

# Load deploy-time secrets (DingTalk webhook etc.), gitignored
# （原因：告警凭据不得进 git/镜像，仅在宿主机运行时注入容器环境）
if [ -f "$PROJECT_ROOT/deploy/deploy.env" ]; then
  set -a
  . "$PROJECT_ROOT/deploy/deploy.env"
  set +a
fi

mkdir -p "$PROJECT_ROOT/.run/logs" "$PROJECT_ROOT/.run/state"

POD_NAME="kingdee-sync"
API_CONTAINER="kingdee-sync-api"
WEB_CONTAINER="kingdee-sync-web"
RELEASE_TAG="$(date +%Y%m%d-%H%M%S)"
API_IMAGE="kingdee-sync-api:release-$RELEASE_TAG"
WEB_IMAGE="kingdee-sync-web:release-$RELEASE_TAG"

# Build both images before touching the running pod
# （原因：任一镜像构建失败时线上服务必须保持运行）
podman build -f "$PROJECT_ROOT/deploy/docker/Dockerfile" -t "$API_IMAGE" "$PROJECT_ROOT"
podman build -f "$PROJECT_ROOT/deploy/docker/web.Dockerfile" -t "$WEB_IMAGE" "$PROJECT_ROOT"

# Remove existing pod and containers only after both images are ready
podman pod rm -f "$POD_NAME" 2>/dev/null || true

# Create pod with shared network namespace
podman pod create --name "$POD_NAME" -p 8000:8000 -p 8001:80

# Run API container
podman run -d --pod "$POD_NAME" --name "$API_CONTAINER" \
  -v "$PROJECT_ROOT/config.local.ini":/app/config.local.ini:ro,Z \
  -v "$PROJECT_ROOT/packages/sync-config":/app/packages/sync-config:ro,Z \
  -v "$PROJECT_ROOT/.run/logs":/app/logs:Z \
  -v "$PROJECT_ROOT/.run/state":/app/state:Z \
  -e LISTEN_ADDR=0.0.0.0 \
  -e LISTEN_PORT=8000 \
  -e GORM_DB_PATH=/app/state/go_state.db \
  -e DINGTALK_WEBHOOK_URL="${DINGTALK_WEBHOOK_URL:-}" \
  -e DINGTALK_WEBHOOK_SECRET="${DINGTALK_WEBHOOK_SECRET:-}" \
  "$API_IMAGE"

# Run Web container
podman run -d --pod "$POD_NAME" --name "$WEB_CONTAINER" \
  "$WEB_IMAGE"

# --retry-connrefused covers the gap between container start and port listening
# （原因：仅 --retry 不会重试连接拒绝，会在服务已启动但尚未监听时误报失败）
curl -fsS --retry 30 --retry-delay 1 --retry-connrefused http://127.0.0.1:8000/health
curl -fsS --retry 30 --retry-delay 1 --retry-connrefused http://127.0.0.1:8001/health

# Publish latest only after the new containers pass health checks
# （原因：失败发布不得覆盖当前可运行版本标签）
podman tag "$API_IMAGE" kingdee-sync-api:latest
podman tag "$WEB_IMAGE" kingdee-sync-web:latest
