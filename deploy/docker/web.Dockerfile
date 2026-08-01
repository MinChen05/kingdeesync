FROM docker.m.daocloud.io/library/node:22-alpine AS build

# 国内 npm 镜像源：覆盖 package-lock.json 中写死的 resolved 地址，
# 下载内容与原官方源逐字节一致，依赖版本与构建结果保持不变。
ENV NPM_CONFIG_REGISTRY=https://registry.npmmirror.com

WORKDIR /src/apps/web
COPY apps/web/package.json apps/web/package-lock.json apps/web/.npmrc ./
RUN npm ci --ignore-scripts --legacy-peer-deps --registry=https://registry.npmmirror.com
COPY apps/web ./
RUN npm run build

FROM docker.m.daocloud.io/library/nginx:1.27-alpine
COPY deploy/docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/apps/web/dist /usr/share/nginx/html
EXPOSE 80
