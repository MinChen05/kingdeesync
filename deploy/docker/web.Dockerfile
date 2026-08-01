FROM docker.m.daocloud.io/library/node:22-alpine AS build

# 国内 npm 镜像源：下载内容与原官方源逐字节一致，依赖版本与构建结果保持不变。
ENV NPM_CONFIG_REGISTRY=https://registry.npmmirror.com \
    COREPACK_NPM_REGISTRY=https://registry.npmmirror.com

WORKDIR /src/apps/web
RUN corepack enable && corepack prepare pnpm@latest --activate
# 先复制全部源码再安装：prepare 脚本（husky + max setup）需要完整源码
COPY apps/web ./
RUN pnpm install --frozen-lockfile
RUN pnpm build

FROM docker.m.daocloud.io/library/nginx:1.27-alpine
COPY deploy/docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/apps/web/dist /usr/share/nginx/html
EXPOSE 80
