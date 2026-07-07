## Why

当前工具已支持采购订单、应付单、生产入库单等同步，但缺少采购入库单同步，导致采购到货入库后的库存与供应链闭环无法在 SQL Server 侧完整追踪。新增采购入库单基础明细同步，可以补齐采购订单到入库的业务链路，并为后续应付核对、库存分析和异常追溯提供数据基础。

## What Changes

- 新增“采购入库单”表单同步能力，优先覆盖单据头和分录基础字段，包括单号、日期、状态、供应商、采购组织、物料、实收数量、源单号、源单行、修改时间等（原因：先完成可验证的基础明细闭环，降低字段不确定性风险）。
- 新增金蝶查询配置，目标 FormId 采用采购入库单常用标识 `STK_InStock`，字段清单以后续 dry-run 响应校准（原因：不同金蝶环境可能存在字段别名或自定义字段差异）。
- 新增 SQL Server 目标表与 writer 注册，复用现有 `form-queries.json`、`tables.json`、writer registry、批量写入、staging/upsert 和增量过滤链路（原因：框架能力和项目既有同步能力优先复用，避免重复造轮子）。
- 新增采购入库单数据准备与写入校验，空主键、空单号等无效行必须跳过并记录日志（原因：保证写入幂等性和数据可追溯性）。
- 新增相关单元测试和 dry-run 验证脚本/说明，覆盖配置注册、字段映射、writer 注册、主键过滤和 SQL Server 写入预期日志（原因：数据库写入变更必须有可回归证据）。
- 将当前工作区既有未提交改动纳入本 change 的核验范围，包括 `assets/styles.css`、`src/core/mysql_manager.py`、诊断脚本和日志中心截图（原因：用户明确要求并入当前 change，后续验证需避免遗漏）。

## Capabilities

### New Capabilities

- `purchase-instock-sync`: 定义采购入库单基础明细从金蝶 API 拉取、字段映射、SQL Server 写入、幂等更新和验证要求。

### Modified Capabilities

- 无。

## Impact

- 影响配置：`src/config/form-queries.json`、`src/config/tables.json`、`config.example.ini` 中的表单与 staging 配置可能需要新增采购入库单条目（原因：让 GUI、调度和同步服务能够发现并执行该表单）。
- 影响写入链路：`src/core/sales_writer.py` 或更合适的 writer 模块、`src/core/writers_registry.py`、`src/core/mysql_manager.py` 需要新增/复用采购入库单写入方法（原因：当前架构通过 writer registry 分发具体表单写入）。
- 影响 SQL Server：允许新增非报表业务表 `STK_InStock` 或约定后的采购入库单目标表，并允许新增必要索引；不修改报表相关表结构（原因：采购入库单是业务单据表，不属于报表表结构禁改范围）。
- 影响测试：新增或扩展配置、writer、upsert、字段映射和 dry-run 相关测试（原因：同步表单新增会影响配置加载、数据转换和数据库写入三层行为）。
