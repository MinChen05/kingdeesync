#!/bin/sh
# 启动时从 /etc/resolv.conf 动态读取容器 DNS，替换 nginx.conf 中的占位符。
# （原因：Podman 与 Docker 的 DNS 网关地址不同（10.89.0.1 vs 127.0.0.11），
#  写死任一地址在另一运行时下都会导致后端容器名解析失败、返回 502）
set -e

DNS_SERVER=$(awk '/^nameserver/{print $2; exit}' /etc/resolv.conf)
if [ -n "$DNS_SERVER" ]; then
    sed -i "s/__DNS_SERVER__/$DNS_SERVER/" /etc/nginx/conf.d/default.conf
fi

exec /docker-entrypoint.sh nginx -g "daemon off;"
