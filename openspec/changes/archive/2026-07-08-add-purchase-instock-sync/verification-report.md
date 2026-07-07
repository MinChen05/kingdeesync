# 采购入库单同步验证报告

## 验证结论

本轮验证覆盖采购入库单配置注册、writer 注册、字段准备、SQL Server upsert/staging、SQL Server 业务列顺序、相邻表单回归和 OpenSpec 严格校验。未连接生产 SQL Server，未执行破坏性 SQL（原因：本阶段验证代码路径与 dry-run 预期，不清空或修改生产数据）。

## 已执行命令

- `python -m pytest tests/test_config_manager.py::ConfigManagerTests::test_builtin_tables_json_registers_purchase_instock_sync tests/test_writers_registry.py::WriterRegistryTests::test_purchase_instock_writer_is_registered tests/test_purchase_instock_write_validation.py -q`
  - 结果：`6 passed in 31.68s`
- `python -m pytest tests/test_upsert_engine_sqlserver.py tests/test_sqlserver_business_layout.py -q`
  - 结果：`20 passed in 31.75s`
- `python -m pytest tests/test_prd_instock_write_validation.py tests/test_ap_payable_field_mapping.py tests/test_writers_registry.py -q`
  - 结果：`10 passed in 31.71s`
- `openspec validate add-purchase-instock-sync --strict`
  - 结果：`Change 'add-purchase-instock-sync' is valid`

## SQL Server 写入预期日志

采购入库单 dry-run 或小批量同步时应重点观察以下日志与指标（原因：字段需以后续真实金蝶响应校准）：

- 金蝶查询配置应显示表单名“采购入库单”、`FormId=STK_InStock` 和基础明细 `FieldKeys`。
- 分页日志应显示每页拉取数量、累计数量和结束条件。
- writer 应路由到 `insert_purchase_instock`，目标表为 `STK_InStock`。
- 字段准备阶段应跳过缺少 `FID`、`FENTRYID` 或 `FBILLNO` 的记录，并输出包含单据内码、分录内码和单号的 warning。
- SQL Server staging/upsert 阶段应按 `FENTRYID` 幂等合并，并过滤空 `FID/FENTRYID` 记录。
- 目标表应具备 `UX_STK_InStock_fentryid` 唯一索引计划和 `FModifyDate` 可用于增量/排查。

## 既有改动归因

用户已确认将开始本 change 前的既有未提交改动并入当前 change。`src/core/mysql_manager.py` 中既有生产订单相关改动已随 Task 4 提交 `c964af74` 并入；其不属于采购入库单新增逻辑，但属于本 change 的并入范围（原因：遵守用户对 dirty worktree 的明确选择）。当前仍保留的 `assets/styles.css`、`.mimocode/plans/1782280635509-silent-nebula.md`、`check_latest*.py` 和 `docs/screenshots/log_center_*.png` 不参与采购入库单 writer 运行路径。
