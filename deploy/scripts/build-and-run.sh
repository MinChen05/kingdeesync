#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/deploy/docker/compose.yaml"

command -v podman >/dev/null || { echo "Podman is required" >&2; exit 1; }
test -f "$PROJECT_ROOT/config.local.ini" || { echo "config.local.ini is required" >&2; exit 1; }

mkdir -p "$PROJECT_ROOT/.run/logs" "$PROJECT_ROOT/.run/state"

# Remove only this project's resources so every deployment uses fresh layers.
podman rm -f kingdee-sync-api kingdee-sync-web 2>/dev/null || true
podman image rm -f docker_kingdee-sync-api docker_kingdee-sync-web 2>/dev/null || true

podman compose -f "$COMPOSE_FILE" build --no-cache
podman compose -f "$COMPOSE_FILE" up -d --force-recreate

curl -fsS --retry 10 --retry-delay 1 http://127.0.0.1:8000/health
curl -fsS --retry 10 --retry-delay 1 http://127.0.0.1:8001/health
