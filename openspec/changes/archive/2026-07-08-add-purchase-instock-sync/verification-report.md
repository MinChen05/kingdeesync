# 采购入库单同步验证报告

## 验证结论

本轮验证覆盖采购入库单配置注册、writer 注册、字段准备、SQL Server upsert/staging、SQL Server 业务列顺序、相邻表单回归、OpenSpec 严格校验，以及 2026-07-08 的真实金蝶 dry-run 与 SQL Server 小批量写入验证。真实写入仅限 10 行采购入库单样例；未清空、未删除任何生产数据（原因：本轮目标是字段校准和最小写入闭环验证）。

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
- `python -m pytest tests/test_config_manager.py tests/test_purchase_instock_write_validation.py tests/test_writers_registry.py tests/test_upsert_engine_sqlserver.py::UpsertEngineSqlServerTests::test_stk_instock_filters_missing_entryid tests/test_sqlserver_business_layout.py::SqlServerBusinessLayoutTests::test_stk_instock_places_material_and_source_fields_before_modifydate -q`
  - 结果：`19 passed in 0.25s`

## SQL Server 写入验证结果

采购入库单 dry-run 和小批量同步已验证以下日志与指标（原因：字段以真实金蝶响应为准，写入以 SQL Server 实际行数为准）：

- 金蝶查询配置应显示表单名“采购入库单”、`FormId=STK_InStock` 和基础明细 `FieldKeys`。
- 校准后的 `FieldKeys` 使用 `FInStockEntry_fseq` 填充目标列 `FSRCENTRYSEQ`（原因：原 `FSrcEntrySeq` 在当前金蝶账套不存在）。
- writer 已路由到 `insert_purchase_instock`，目标表为 `STK_InStock`。
- 字段准备阶段应跳过缺少 `FID`、`FENTRYID` 或 `FBILLNO` 的记录，并输出包含单据内码、分录内码和单号的 warning。
- SQL Server upsert 阶段已按 `FENTRYID` 幂等合并，并过滤空 `FID/FENTRYID` 记录。
- 目标表已具备 `UX_STK_InStock_fentryid` 唯一索引，`FModifyDate` 可用于增量/排查。

## 既有改动归因

用户已确认将开始本 change 前的既有未提交改动并入当前 change。`src/core/mysql_manager.py` 中既有生产订单相关改动已随 Task 4 提交 `c964af74` 并入；其不属于采购入库单新增逻辑，但属于本 change 的并入范围（原因：遵守用户对 dirty worktree 的明确选择）。当前仍保留的 `assets/styles.css`、`.mimocode/plans/1782280635509-silent-nebula.md`、`check_latest*.py` 和 `docs/screenshots/log_center_*.png` 不参与采购入库单 writer 运行路径。
