#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

test -f apps/server/go.mod
test -f apps/web/package.json
test -f packages/sync-config/form-queries.json
test -f deploy/docker/Dockerfile
