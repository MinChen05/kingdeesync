## 1. 配置与表单注册

- [ ] 1.1 在 `src/config/form-queries.json` 新增“采购入库单”查询配置，初始 FormId 使用 `STK_InStock`，字段先覆盖基础明细并保留 dry-run 校准记录。
- [ ] 1.2 在 `src/config/tables.json` 新增“采购入库单”目标表和 writer 映射。
- [ ] 1.3 在 `config.example.ini` 的 staging 配置中加入采购入库单目标表。
- [ ] 1.4 扩展配置加载或配置校验测试，确认“采购入库单”可被发现。

## 2. Writer 与数据准备

- [ ] 2.1 新增 `insert_purchase_instock` writer，并注册到 `src/core/writers_registry.py`。
- [ ] 2.2 新增 `_prepare_purchase_instock_data` 数据准备方法，覆盖基础明细字段转换。
- [ ] 2.3 为缺少 `FID`、分录主键或单号的记录增加跳过逻辑和警告日志。
- [ ] 2.4 在 SQL Server upsert/staging 主键映射中补充采购入库单分录级幂等键。

## 3. SQL Server 表结构与索引

- [ ] 3.1 定义采购入库单非报表业务目标表字段，保留数据类型与现有写入引擎兼容。
- [ ] 3.2 如目标表不存在，新增建表或自动补列路径；如涉及主键、唯一键或字段顺序调整，先保留数据并校验行数。
- [ ] 3.3 为分录主键和修改时间新增必要索引。
- [ ] 3.4 明确本次不修改报表相关表结构。

## 4. 测试与 Dry-run

- [ ] 4.1 新增 writer registry 测试，确认 `insert_purchase_instock` 已注册。
- [ ] 4.2 新增采购入库单字段准备测试，覆盖正常记录、空分录主键、空单号和大小写字段兼容。
- [ ] 4.3 新增 upsert/staging 测试，确认采购入库单使用分录级幂等键。
- [ ] 4.4 新增或更新 dry-run 脚本说明，输出金蝶响应样例、字段校准结果、预计写入量和跳过量。

## 5. 既有未提交改动核验

- [x] 5.1 复核并归因 `assets/styles.css`、`src/core/mysql_manager.py`、诊断脚本和日志中心截图，确认是否与本 change 一起保留。归因结论：用户已明确要求将这些既有未提交改动并入当前 change；`src/core/mysql_manager.py` 中既有生产订单相关改动已随 Task 4 提交 `c964af74` 并入，后续验证报告需单独说明其非采购入库单新增逻辑。
- [x] 5.2 对 `src/core/mysql_manager.py` 的既有改动运行相关测试，避免采购入库单实现覆盖用户改动。已运行采购入库单字段准备、writer registry、SQL Server upsert 和业务列顺序相关测试，结果通过；生产订单既有改动属于并入范围，未在本任务中回滚。
- [x] 5.3 如截图或诊断脚本不参与运行时逻辑，在验证报告中说明其影响范围。当前剩余未提交文件包括 `assets/styles.css`、`.mimocode/plans/1782280635509-silent-nebula.md`、`check_latest*.py` 和 `docs/screenshots/log_center_*.png`；它们不参与采购入库单 writer 运行路径，后续验证报告需标注为并入范围内的非运行时/界面与诊断资产。

## 6. 验证收尾

- [ ] 6.1 运行 `pytest` 中采购入库单相关单元测试。
- [ ] 6.2 运行配置管理、writer registry、upsert/staging 相关回归测试。
- [ ] 6.3 执行采购入库单 dry-run，并记录预期 SQL Server 写入日志变化。
- [ ] 6.4 运行 `openspec validate add-purchase-instock-sync --strict`。
