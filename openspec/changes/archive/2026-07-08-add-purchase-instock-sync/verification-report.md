# 采购入库单同步验证报告

## 验证结论

本轮验证覆盖采购入库单配置注册、writer 注册、字段准备、SQL Server upsert/staging、SQL Server 业务列顺序、相邻表单回归、OpenSpec 严格校验，以及 2026-07-08 的真实金蝶 dry-run、SQL Server 10 行小批量写入验证、1000 行增量放大验证和正式增量同步入口验证。真实写入仅新增或更新采购入库单样例行；未清空、未删除任何生产数据（原因：本轮目标是字段校准、最小写入闭环、幂等性和正式入口可观测性验证）。

## 已执行命令

- `python -m pytest tests/test_config_manager.py::ConfigManagerTests::test_builtin_tables_json_registers_purchase_instock_sync tests/test_writers_registry.py::WriterRegistryTests::test_purchase_instock_writer_is_registered tests/test_purchase_instock_write_validation.py -q`
  - 结果：`6 passed in 31.68s`
- `python -m pytest tests/test_upsert_engine_sqlserver.py tests/test_sqlserver_business_layout.py -q`
  - 结果：`20 passed in 31.75s`
- `python -m pytest tests/test_prd_instock_write_validation.py tests/test_ap_payable_field_mapping.py tests/test_writers_registry.py -q`
  - 结果：`10 passed in 31.71s`
- `openspec validate add-purchase-instock-sync --strict`
  - 结果：`Change 'add-purchase-instock-sync' is valid`
- 2026-07-08 真实 dry-run 与小批量写入验证
  - 金蝶 `STK_InStock` 查询 `Limit=10`，返回 10 行。
  - `FSrcEntrySeq` 被金蝶元数据拒绝；`FInStockEntry_fseq` 可查询，并与样例中的 `FInStockEntry_FSEQ` 完全一致。
  - 写入前 SQL Server 当前库为 `Kingdee`，目标表 `dbo.STK_InStock` 不存在；已新增非报表业务表 `dbo.STK_InStock` 和唯一索引 `UX_STK_InStock_fentryid`（原因：没有目标表会触发 SQL Server 208“对象名无效”，无法执行 MERGE）。
  - 写入前匹配行数：0；writer 返回写入数：10；写入后匹配行数：10；目标表总行数：10。
  - SQL Server 日志：`成功插入/更新 10 条记录 (SQL Server)`。
- 2026-07-08 1000 行增量放大与幂等验证
  - 金蝶 `STK_InStock` 查询 `Limit=1000`，返回 1000 行。
  - 字段准备结果：有效 1000 行，无效/跳过 0 行，源端重复 `FENTRYID` 0 个。
  - 写入前目标表总行数：10；本批匹配行数：10。
  - 首次写入：writer 返回 1000；目标表总行数变为 1000；本批匹配行数变为 1000；总行数变化 +990。
  - 重复写入：writer 返回 1000；目标表总行数保持 1000；本批匹配行数保持 1000；总行数变化 0（原因：`FENTRYID` 幂等合并生效）。
  - 只读核对：关键字段异常行数 0；重复 `FENTRYID` 组数 0；`FSRCENTRYSEQ` 已由 `FInStockEntry_fseq` 正常写入。
  - 命令 stdout 出现两次 `成功插入/更新 1000 条记录 (SQL Server)`；`logs/app.log` 未捕获本次记录（原因：验证 harness 的 logging 输出到 stdout，未接入应用文件日志 handler）。
- 2026-07-08 正式增量同步入口验证
  - 通过 `run_sync` / `DataSyncManager.sync_data` 正式路径运行“采购入库单”增量同步，并启用应用文件日志。
  - `run_id=453d49a964dd476ba5ab49c5dc11d263`，同步状态为 `success`。
  - 增量字段使用 `FModifyDate`；金蝶返回 0 条新数据，目标表 `dbo.STK_InStock` 保持 1000 行。
  - SQL Server `sync_runs` 记录：`total_records=0`、`success_count=1`、`failure_count=0`。
  - SQL Server `sync_logs` 记录：`table_name=STK_InStock`、`record_count=0`、`status=success`。
  - 本地 `logs/sync_stats.db` 已记录 `run_stats` 与 `form_stats`；其中 `form_stats.table_name` 当前为空（原因：现有统计落库未填充该字段，不影响 SQL Server 同步日志）。
  - `logs/app.log` 命中 19 条本次采购入库单/run 日志，`logs/app.jsonl` 命中 5 条审计/完成日志。
  - 成功同步后未留下 pending checkpoint 文件。
- 2026-07-08 `sync_stats.form_stats.table_name` 修复验证
  - 提交 `c073c3b0` 已将本地统计写入改为：当表单结果缺少 `table_name` 时，从 `DataSyncManager.table_mapping` 兜底获取目标表名（原因：正式同步结果当前不直接返回表名）。
  - 新增回归测试先复现 `form_stats.table_name=''`，修复后通过。
  - 相关回归命令结果：`27 passed in 0.39s`。
  - 正式入口复验 `run_id=da2a2b6a0c5f40b5a86cd39a8174f026` 成功，金蝶返回 0 条新数据，`logs/sync_stats.db.form_stats.table_name` 已记录 `STK_InStock`。
  - 复验后 `dbo.STK_InStock` 仍为 1000 行。
- `python -m pytest tests/test_config_manager.py tests/test_purchase_instock_write_validation.py tests/test_writers_registry.py tests/test_upsert_engine_sqlserver.py::UpsertEngineSqlServerTests::test_stk_instock_filters_missing_entryid tests/test_sqlserver_business_layout.py::SqlServerBusinessLayoutTests::test_stk_instock_places_material_and_source_fields_before_modifydate -q`
  - 结果：`19 passed in 0.25s`
- `python -m pytest tests/test_config_manager.py tests/test_purchase_instock_write_validation.py tests/test_writers_registry.py tests/test_upsert_engine_sqlserver.py::UpsertEngineSqlServerTests::test_stk_instock_filters_missing_entryid tests/test_sqlserver_business_layout.py::SqlServerBusinessLayoutTests::test_stk_instock_places_material_and_source_fields_before_modifydate -q`
  - 1000 行增量放大后复跑结果：`19 passed in 0.24s`

## SQL Server 写入验证结果

采购入库单 dry-run 和小批量同步已验证以下日志与指标（原因：字段以真实金蝶响应为准，写入以 SQL Server 实际行数为准）：

- 金蝶查询配置应显示表单名“采购入库单”、`FormId=STK_InStock` 和基础明细 `FieldKeys`。
- 校准后的 `FieldKeys` 使用 `FInStockEntry_fseq` 填充目标列 `FSRCENTRYSEQ`（原因：原 `FSrcEntrySeq` 在当前金蝶账套不存在）。
- writer 已路由到 `insert_purchase_instock`，目标表为 `STK_InStock`。
- 字段准备阶段应跳过缺少 `FID`、`FENTRYID` 或 `FBILLNO` 的记录，并输出包含单据内码、分录内码和单号的 warning。
- SQL Server upsert 阶段已按 `FENTRYID` 幂等合并，并过滤空 `FID/FENTRYID` 记录。
- 目标表已具备 `UX_STK_InStock_fentryid` 唯一索引，`FModifyDate` 可用于增量/排查。
- 1000 行重复写入验证显示目标表总行数不再增长，重复 `FENTRYID` 组数为 0（原因：证明分录级幂等键在当前目标库生效）。
- 正式入口验证显示 `sync_runs`、`sync_logs`、`sync_stats.db`、`app.log` 和 `app.jsonl` 均可观测到本次增量同步；checkpoint 成功清理或未生成 pending 文件。
- `sync_stats.db.form_stats.table_name` 已在修复后记录 `STK_InStock`，与 SQL Server `sync_logs.table_name` 保持一致。

## 既有改动归因

用户已确认将开始本 change 前的既有未提交改动并入当前 change。`src/core/mysql_manager.py` 中既有生产订单相关改动已随 Task 4 提交 `c964af74` 并入；其不属于采购入库单新增逻辑，但属于本 change 的并入范围（原因：遵守用户对 dirty worktree 的明确选择）。当前仍保留的 `assets/styles.css`、`.mimocode/plans/1782280635509-silent-nebula.md`、`check_latest*.py` 和 `docs/screenshots/log_center_*.png` 不参与采购入库单 writer 运行路径。
