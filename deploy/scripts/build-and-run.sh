#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

command -v podman >/dev/null || { echo "Podman is required" >&2; exit 1; }
test -f "$PROJECT_ROOT/config.local.ini" || { echo "config.local.ini is required" >&2; exit 1; }

mkdir -p "$PROJECT_ROOT/.run/logs" "$PROJECT_ROOT/.run/state"

POD_NAME="kingdee-sync"
API_CONTAINER="kingdee-sync-api"
WEB_CONTAINER="kingdee-sync-web"

# Remove existing pod and containers
podman pod rm -f "$POD_NAME" 2>/dev/null || true

# Create pod with shared network namespace
podman pod create --name "$POD_NAME" -p 8000:8000 -p 8001:80

# Build images
podman build -f "$PROJECT_ROOT/deploy/docker/Dockerfile" -t kingdee-sync-api "$PROJECT_ROOT"
podman build -f "$PROJECT_ROOT/deploy/docker/web.Dockerfile" -t kingdee-sync-web "$PROJECT_ROOT"

# Run API container
podman run -d --pod "$POD_NAME" --name "$API_CONTAINER" \
  -v "$PROJECT_ROOT/config.local.ini":/app/config.local.ini:ro,Z \
  -v "$PROJECT_ROOT/packages/sync-config":/app/packages/sync-config:ro,Z \
  -v "$PROJECT_ROOT/.run/logs":/app/logs:Z \
  -v "$PROJECT_ROOT/.run/state":/app/state:Z \
  -e LISTEN_ADDR=0.0.0.0 \
  -e LISTEN_PORT=8000 \
  -e GORM_DB_PATH=/app/state/go_state.db \
  kingdee-sync-api

# Run Web container
podman run -d --pod "$POD_NAME" --name "$WEB_CONTAINER" \
  kingdee-sync-web

# Health checks
curl -fsS --retry 10 --retry-delay 1 http://127.0.0.1:8000/health
curl -fsS --retry 10 --retry-delay 1 http://127.0.0.1:8001/health