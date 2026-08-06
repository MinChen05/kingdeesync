#!/bin/sh
# 启动时尝试解析 kingdee-sync-api 容器名，优先使用 IP 直连。
# 如果 DNS 解析成功则用容器名（resolver 动态解析），否则用 IP 兜底。
# （原因：Podman DNS 服务器在某些网络环境下不可达，导致 502 Bad Gateway）
set -e

# Try to resolve via DNS first
BACKEND_IP=""
for attempt in 1 2 3; do
    BACKEND_IP=$(getent hosts kingdee-sync-api 2>/dev/null | awk '{print $1; exit}')
    if [ -n "$BACKEND_IP" ]; then
        break
    fi
    sleep 1
done

if [ -n "$BACKEND_IP" ]; then
    # Use IP directly to avoid DNS resolution issues
    sed -i "s|http://kingdee-sync-api:8000|http://${BACKEND_IP}:8000|g" /etc/nginx/conf.d/default.conf
    sed -i "s|resolver .* valid=10s ipv6=off;|# resolver disabled (using static IP)|" /etc/nginx/conf.d/default.conf
    echo "[web-entrypoint] Using backend IP: ${BACKEND_IP}"
else
    # Fallback: try DNS resolver from resolv.conf
    DNS_SERVER=$(awk '/^nameserver/{print $2; exit}' /etc/resolv.conf)
    if [ -n "$DNS_SERVER" ]; then
        sed -i "s/__DNS_SERVER__/$DNS_SERVER/" /etc/nginx/conf.d/default.conf
        echo "[web-entrypoint] Using DNS resolver: ${DNS_SERVER}"
    else
        echo "[web-entrypoint] Warning: no DNS resolver found"
    fi
fi

exec /docker-entrypoint.sh nginx -g "daemon off;"
