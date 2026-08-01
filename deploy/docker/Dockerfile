FROM docker.1ms.run/library/golang:1.25-alpine AS build

# 国内 Go 模块代理：goproxy.cn 是官方 proxy.golang.org 的透明镜像，
# 配合 go.sum 校验，模块版本与构建结果与原官方源一致。
ENV GOPROXY=https://goproxy.cn,direct \
    GOSUMDB=sum.golang.google.cn

WORKDIR /src/apps/server
COPY apps/server/go.mod apps/server/go.sum ./
RUN go mod download
COPY apps/server ./
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags='-s -w' -o /out/server ./cmd/server

FROM docker.1ms.run/library/alpine:3.20
RUN apk add --no-cache ca-certificates tzdata
WORKDIR /app
COPY --from=build /out/server ./server
COPY packages/sync-config ./packages/sync-config

ENV LISTEN_ADDR=0.0.0.0 \
    LISTEN_PORT=8000 \
    TZ=Asia/Shanghai \
    SYNC_CONFIG_DIR=/app/packages/sync-config

EXPOSE 8000
ENTRYPOINT ["/app/server"]
