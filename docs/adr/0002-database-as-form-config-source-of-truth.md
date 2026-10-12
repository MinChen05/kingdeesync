# ADR-0002: 表单查询配置以状态库为权威源，JSON 仅作种子/兜底

- **状态**：Accepted
- **日期**：2026-08-27 成文（提交 `c9db3cd`；机制在此前已运行）
- **相关**：`packages/sync-config/README.md`、`CONTEXT.md`

## 背景

表单查询配置（`form_id` / `field_keys` / `filter_string` / `field_map`）同时存在于
多个 JSON 副本（根目录、`packages/sync-config/`、`apps/server/packages/`）和状态库
`go_form_queries` 表中。曾发生运维改了 SQL/数据库但被 JSON 快照误导、或改了 JSON
却对已初始化环境无效的漂移事故（如应收单过滤条件只改了库、种子文件长期落后）。

## 决策

读取优先级固定为（`config.GetFormQuery`）：

1. **状态库 `go_form_queries` 表**（权威源，实时、无缓存）——有记录即完全以库为准，
   改库后下次同步生效，无需重启。
2. **JSON**——仅在表完全为空时执行一次性种子化（`MigrateFormQueriesFromJSON`），
   之后仅作该表单无库记录时的内存快照兜底。

修改生产表单配置的唯一入口是 Web 控制台 / API（写库），**不改 JSON 文件**；
JSON 只在种子一致性维护时随库回填。

## 后果

- 正面：配置实时生效、可被 API/UI 管理、单一事实源。
- 负面：仓库中多份 JSON 副本仍存留，必须靠 `packages/sync-config/README.md`
  的防漂移表约束"哪个场景读哪份"；改库不会回流 JSON，需人工保持种子文件
  与库的语义一致（`c9db3cd` 即一次回填）。
