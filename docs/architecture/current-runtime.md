# 当前运行架构

唯一生产同步链路为：

```text
apps/web -> /api -> apps/server -> Kingdee API / Doris
```

`packages/sync-config/form-queries.json` 定义 22 张业务表单的查询与映射配置。Go 服务通过 `SYNC_CONFIG_DIR` 定位该目录；未设置时从部署二进制相邻的 `packages/sync-config` 或项目根目录的配置包读取。

同步数据直接写入 Doris 主表。正式 MSSQL 不参与实时同步或切换，仅在明确的只读核对任务中作为历史证据使用。

影子表、切换、快照审批和 Python 同步运行时均已移除。运行与部署入口位于 `deploy/scripts/` 和 `deploy/docker/`。
