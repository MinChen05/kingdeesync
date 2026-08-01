# 国内镜像源配置（加速依赖安装与镜像构建）

> 适用项目：kingdee-sync（前端 `apps/web` 用 npm，后端 `apps/server` 用 Go modules）
> 所有镜像源均为官方源的**透明镜像**，内容逐字节一致，配合 lockfile / `go.sum` 校验，
> **依赖版本与构建结果与使用官方源完全一致**。

## 一、npm（前端 apps/web）

镜像源：`https://registry.npmmirror.com`（阿里 npmmirror，npm 官方注册表的透明镜像）

### 永久生效（项目级，已配置）
项目已写入 `apps/web/.npmrc`：
```ini
legacy-peer-deps=true
registry=https://registry.npmmirror.com
disturl=https://npmmirror.com/dist
fetch-timeout=120000
```

### 永久生效（全局）
```bash
npm config set registry https://registry.npmmirror.com
```

### 临时使用（单次命令）
```bash
# 安装/构建时显式指定；注意 npm ci 必须带 --registry 才能覆盖 lockfile 中写死的 resolved 地址
npm ci --ignore-scripts --legacy-peer-deps --registry=https://registry.npmmirror.com
npm install --registry=https://registry.npmmirror.com
```
> 重要：项目使用 `package-lock.json`，`npm ci` 默认会按 lockfile 里的 `resolved` 地址（官方源）下载。
> 无论用 `.npmrc` 还是 `--registry`，都要确保最终生效的是镜像源（Dockerfile 中已显式加 `--registry` 兜底）。

## 二、Go modules（后端 apps/server）

镜像代理：`https://goproxy.cn`（官方 `proxy.golang.org` 的透明镜像）+ 校验库 `sum.golang.google.cn`

### 永久生效
```bash
go env -w GOPROXY=https://goproxy.cn,direct
go env -w GOSUMDB=sum.golang.google.cn
```

### 临时使用（单次命令）
```bash
GOPROXY=https://goproxy.cn,direct GOSUMDB=sum.golang.google.cn go mod download
```
> Docker 构建已在 `deploy/docker/Dockerfile` 内设置 `ENV GOPROXY=... GOSUMDB=...`，`go mod download` 自动走镜像。

## 三、pip（备用，本项目当前未使用）

镜像源：清华 `https://pypi.tuna.tsinghua.edu.cn/simple` 或阿里 `https://mirrors.aliyun.com/pypi/simple/`

### 永久生效
```bash
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

### 临时使用
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 四、Docker / Podman 镜像加速器（基础镜像拉取加速）

### Podman（本机使用，已配置）
已修改 `/etc/containers/registries.conf`，为 `docker.io` 增加镜像：
```
[[registry]]
prefix = "docker.io"
location = "docker.io"
[[registry.mirror]]
location = "docker.m.daocloud.io"
[[registry.mirror]]
location = "hub-mirror.c.163.com"
```
备份文件：`/etc/containers/registries.conf.bak.*`。Dockerfile 基础镜像已直接写 `docker.m.daocloud.io/library/...`。

### Docker（若改用 Docker 守护进程）
编辑 `/etc/docker/daemon.json`：
```json
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://hub-mirror.c.163.com",
    "https://registry.docker-cn.com"
  ]
}
```
重启：`sudo systemctl restart docker`

## 五、验证与版本一致性

- npm：`npm ci --registry=...` 时所有 tarball 均从 `registry.npmmirror.com` 下载，`package-lock.json` 锁定的版本号不变。
- Go：`goproxy.cn` 提供与官方一致的模块，`go.sum` 校验哈希，版本不变。
- 基础镜像：`docker.m.daocloud.io` 是 Docker Hub library 镜像的同步源，镜像内容一致。

重新构建（已验证可用）：
```bash
cd <项目根目录>
podman build -f deploy/docker/web.Dockerfile -t kingdee-sync-web:latest .
podman build -f deploy/docker/Dockerfile      -t kingdee-sync-api:latest  .
# 或一键：podman compose -f deploy/docker/compose.yaml build
```
