# ADR-0004: 收敛为单一 Go 同步链路，移除影子表与 Python 运行时

- **状态**：Accepted
- **日期**：2026-08-01（提交 `7d37854`，`docs/architecture/current-runtime.md` 加入）
- **相关**：`docs/DESIGN.md`（历史）、`docs/adr/0001`

## 背景

项目早期存在并行的两套形态：Python 同步运行时（FastAPI 封装，见历史文档
`docs/DESIGN.md`）与 Go 服务；写入侧曾有影子表、切换、快照审批机制，
链路分叉导致行为不一致、部署入口不唯一。

## 决策

唯一生产链路收敛为：

```
apps/web → /api → apps/server → Kingdee API / SQL Server
```

- 影子表、切换、快照审批机制整体移除；写入语义改由 Staging + MERGE 承担
  （见 ADR-0001）。
- Python 同步运行时移除，Go `apps/server` 是唯一同步引擎。
- 运行与部署入口唯一：`deploy/scripts/` 与 `deploy/docker/`。
- 运维表（`sync_runs` / `sync_form_stats` / `sync_errors`）迁至目标库体系。

## 后果

- 正面：单一事实链路与部署入口，排障只需盯 Go 服务；文档可断言"当前架构"。
- 负面：`docs/DESIGN.md` 整体过期但保留（UI 设计语言仍参考），读者必须先看
  `docs/architecture/current-runtime.md` 与 `CONTEXT.md` 的历史文档阅读指引。
