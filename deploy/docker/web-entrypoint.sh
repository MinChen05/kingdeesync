#!/bin/sh
# 直接启动 nginx，无需 DNS 解析（Pod 内 127.0.0.1 直连后端）。
set -e
exec /docker-entrypoint.sh nginx -g "daemon off;"