# 当前运行架构

唯一生产同步链路为：

```text
apps/web -> /api -> apps/server -> Kingdee API / SQL Server
```

`packages/sync-config/form-queries.json` 定义 22 张业务表单的查询与映射配置。Go 服务通过 `SYNC_CONFIG_DIR` 定位该目录；未设置时从部署二进制相邻的 `packages/sync-config` 或项目根目录的配置包读取。

同步数据直接写入 SQL Server 主表（10.10.10.191/Kingdee，schema dbo）。

影子表、切换、快照审批和 Python 同步运行时均已移除。运行与部署入口位于 `deploy/scripts/` 和 `deploy/docker/`。
