#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

command -v podman >/dev/null || { echo "Podman is required" >&2; exit 1; }
command -v systemctl >/dev/null || { echo "systemctl is required（发布依赖 Quadlet 单元）" >&2; exit 1; }
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

# ---- Quadlet 发布模式（2026-11-11 切换）----
# 容器归属 systemd Quadlet 单元（Restart=always），发布 = 构建新镜像 → 更新 :latest →
# systemctl restart 让单元以新镜像重建容器。
# （原因：旧版 podman pod rm/create/run 与 Quadlet 单元抢占同名容器，
#  会与 Restart=always 反复拉扯，属于已废弃的手工管理模式）
API_UNIT="kingdee-sync-api.service"
WEB_UNIT="kingdee-sync-web.service"
RELEASE_TAG="$(date +%Y%m%d-%H%M%S)"
API_IMAGE="kingdee-sync-api:release-$RELEASE_TAG"
WEB_IMAGE="kingdee-sync-web:release-$RELEASE_TAG"

# Quadlet 单元必须存在，否则本机尚未完成 systemd 托管切换，禁止按旧方式操作
# （原因：在无双监护的机器上误跑本脚本只 restart 会失败得莫名其妙；在已托管机器上
#  跑旧流程会破坏监护，两个方向都要挡住）
systemctl cat "$API_UNIT" >/dev/null 2>&1 \
  || { echo "Quadlet 单元 $API_UNIT 不存在，宿主机未完成 systemd 切换，禁止继续发布" >&2; exit 1; }
systemctl cat "$WEB_UNIT" >/dev/null 2>&1 \
  || { echo "Quadlet 单元 $WEB_UNIT 不存在，宿主机未完成 systemd 切换，禁止继续发布" >&2; exit 1; }

# 记录当前 :latest 镜像 ID，供健康检查失败时回滚
# （原因：Quadlet 下 restart 直接以 :latest 重建容器，latest 必须先于 restart 更新；
#  为保留"失败发布不得覆盖当前可运行版本"的原语义，
#  健康检查失败时用记录的旧镜像 ID 回滚 latest 并再次 restart 恢复旧版本）
PREV_API_ID="$(podman image inspect --format '{{.Id}}' kingdee-sync-api:latest 2>/dev/null || true)"
PREV_WEB_ID="$(podman image inspect --format '{{.Id}}' kingdee-sync-web:latest 2>/dev/null || true)"

# Build both images before touching the running services
# （原因：任一镜像构建失败时线上服务必须保持运行，不得 restart）
podman build -f "$PROJECT_ROOT/deploy/docker/Dockerfile" -t "$API_IMAGE" "$PROJECT_ROOT"
podman build -f "$PROJECT_ROOT/deploy/docker/web.Dockerfile" -t "$WEB_IMAGE" "$PROJECT_ROOT"

podman tag "$API_IMAGE" kingdee-sync-api:latest
podman tag "$WEB_IMAGE" kingdee-sync-web:latest

systemctl restart "$API_UNIT" "$WEB_UNIT"

# --retry-connrefused covers the gap between container start and port listening
# （原因：仅 --retry 不会重试连接拒绝，会在服务已启动但尚未监听时误报失败）
if ! curl -fsS --retry 30 --retry-delay 1 --retry-connrefused http://127.0.0.1:8000/health \
   || ! curl -fsS --retry 30 --retry-delay 1 --retry-connrefused http://127.0.0.1:8001/health; then
  echo "健康检查失败：回滚 :latest 到旧镜像并重启恢复" >&2
  if [ -n "$PREV_API_ID" ]; then podman tag "$PREV_API_ID" kingdee-sync-api:latest; fi
  if [ -n "$PREV_WEB_ID" ]; then podman tag "$PREV_WEB_ID" kingdee-sync-web:latest; fi
  if ! systemctl restart "$API_UNIT" "$WEB_UNIT"; then
    echo "回滚重启失败，需人工介入：systemctl status $API_UNIT $WEB_UNIT" >&2
  fi
  exit 1
fi

echo "发布完成: release-$RELEASE_TAG"
