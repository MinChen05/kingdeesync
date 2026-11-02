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

# 构建临时目录固定在磁盘上，不继承调用环境的 TMPDIR
# （原因：2026-11-02 部署从 CLI 会话发起时继承了 TMPDIR=/run/user/<uid>/…（tmpfs，上限 6.3G），
#  web 镜像单层就要 1.2G+，buildah 提交层时报 no space left on device（exit 125）；
#  失败发生在构建阶段，虽未影响线上，但部署被迫中断）
# 需要自定义目录时用 BUILD_TMPDIR 显式指定，避免再次被会话环境里的小 tmpfs 影响
BUILD_TMPDIR="${BUILD_TMPDIR:-/var/tmp}"
BUILD_TMPDIR_MIN_MB="${BUILD_TMPDIR_MIN_MB:-4096}"

mkdir -p "$BUILD_TMPDIR" || { echo "无法创建构建临时目录: $BUILD_TMPDIR" >&2; exit 1; }
BUILD_TMPDIR="$(cd "$BUILD_TMPDIR" && pwd -P)"
TMPDIR_FREE_MB="$(df -Pm "$BUILD_TMPDIR" 2>/dev/null | awk 'NR==2 {print $4}')"
[[ "${TMPDIR_FREE_MB:-}" =~ ^[0-9]+$ ]] || TMPDIR_FREE_MB=0

if (( TMPDIR_FREE_MB < BUILD_TMPDIR_MIN_MB )); then
  echo "构建临时目录 $BUILD_TMPDIR 仅 ${TMPDIR_FREE_MB}MB 可用，低于所需 ${BUILD_TMPDIR_MIN_MB}MB" >&2
  echo "请用 BUILD_TMPDIR 指向磁盘上的目录后重试（尚未执行任何 podman 操作，线上服务不受影响）" >&2
  exit 1
fi

# buildah 依据 TMPDIR 决定镜像层临时存储位置
export TMPDIR="$BUILD_TMPDIR"
echo "构建临时目录: $TMPDIR（可用 ${TMPDIR_FREE_MB}MB）"

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
