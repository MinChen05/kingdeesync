#!/usr/bin/env bash
set -euo pipefail
test -d apps/server/cmd/server
test -d apps/server/cmd/check_org
test ! -e apps/server/cmd/cutover-sync
test ! -e apps/server/cmd/window-sync
test ! -e apps/server/cmd/snapshot-approve
test ! -e apps/server/cmd/snapshot-replay
test ! -e apps/server/cmd/cleanup-shadow
