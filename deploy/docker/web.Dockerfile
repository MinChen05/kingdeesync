FROM docker.m.daocloud.io/library/node:22-alpine AS build

# 国内 npm 镜像源：下载内容与原官方源逐字节一致，依赖版本与构建结果保持不变。
# NODE_OPTIONS 强制 IPv4 优先：本机 IPv6 不通，Node 默认先试 IPv6 超时再回退，会拖慢每次请求。
# /pnpm-store 由构建时 --volume 挂载持久化：构建失败/重跑时复用已下载包，只补缺失部分。
ENV NPM_CONFIG_REGISTRY=https://registry.npmmirror.com \
    COREPACK_NPM_REGISTRY=https://registry.npmmirror.com \
    NODE_OPTIONS=--dns-result-order=ipv4first \
    COREPACK_HOME=/pnpm-store/corepack

WORKDIR /src/apps/web
# pnpm 钉到已知可用版本：pnpm@latest 漂移后删除 --fetch-retries 等 CLI 标志，
# 使 pnpm install 步骤失败。（原因：构建可重现性与标志兼容性锁定）
RUN corepack enable && corepack prepare pnpm@11.17.0 --activate
# 先复制全部源码再安装：prepare 脚本（husky + max setup）需要完整源码
COPY apps/web ./
RUN pnpm install --frozen-lockfile --store-dir /pnpm-store --fetch-retries=10 --fetch-timeout=300000 --network-concurrency=6
RUN pnpm build

FROM docker.m.daocloud.io/library/nginx:1.27-alpine
COPY deploy/docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/apps/web/dist /usr/share/nginx/html
COPY deploy/docker/web-entrypoint.sh /usr/local/bin/web-entrypoint.sh
RUN chmod +x /usr/local/bin/web-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/web-entrypoint.sh"]
EXPOSE 80
