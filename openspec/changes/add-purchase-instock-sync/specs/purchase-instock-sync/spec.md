## ADDED Requirements

### Requirement: 采购入库单可配置同步
系统 SHALL 将“采购入库单”作为可配置同步表单注册到现有表单查询和目标表映射中，并通过现有同步入口执行拉取与写入。

#### Scenario: 配置加载采购入库单
- **WHEN** 配置管理器加载内置表单查询和表映射
- **THEN** 系统返回“采购入库单”的金蝶查询配置、SQL Server 目标表和 writer 方法

#### Scenario: 同步入口执行采购入库单
- **WHEN** 用户或调度任务选择同步“采购入库单”
- **THEN** 系统通过现有金蝶 API 查询、表单同步 runner 和 writer registry 执行该表单同步

### Requirement: 采购入库单基础明细字段
系统 SHALL 拉取并写入采购入库单基础明细字段，至少覆盖单据内码、分录内码、分录序号、单号、日期、单据状态、供应商、采购组织、物料编码、物料名称、实收数量、源单号、源单行和修改时间。

#### Scenario: 基础字段写入目标表
- **WHEN** 金蝶 API 返回采购入库单基础明细记录
- **THEN** 系统将基础字段转换为目标表字段并批量写入 SQL Server

#### Scenario: dry-run 校准字段
- **WHEN** dry-run 响应显示字段路径与默认配置不一致
- **THEN** 系统 SHALL 以 dry-run 响应为准调整 `FieldKeys` 和字段读取逻辑

### Requirement: 分录级幂等写入
系统 SHALL 使用采购入库单分录级主键执行幂等写入，重复同步同一分录时更新既有记录而不是重复插入。

#### Scenario: 重复同步同一分录
- **WHEN** 同一采购入库单分录被同步两次
- **THEN** SQL Server 目标表中该分录只有一条最新记录

#### Scenario: 单据多分录同步
- **WHEN** 同一采购入库单包含多个分录
- **THEN** 系统按分录分别写入多条记录，并保留同一单号下的不同分录

### Requirement: 无效采购入库单记录处理
系统 SHALL 跳过缺少单据内码、分录主键或单号的采购入库单记录，并记录可定位的警告日志。

#### Scenario: 分录主键为空
- **WHEN** 采购入库单记录缺少分录主键
- **THEN** 系统跳过该记录，并在日志中记录单据内码、单号和跳过原因

#### Scenario: 单号为空
- **WHEN** 采购入库单记录缺少单号
- **THEN** 系统跳过该记录，并在日志中记录单据内码、分录主键和跳过原因

### Requirement: SQL Server 写入验证
系统 SHALL 为采购入库单同步提供单元测试和 dry-run 验证，覆盖配置注册、字段转换、writer 注册、无效记录跳过、幂等写入和预期日志。

#### Scenario: 单元测试验证写入链路
- **WHEN** 运行相关单元测试
- **THEN** 测试覆盖采购入库单配置、writer 注册、字段准备和空主键跳过行为

#### Scenario: dry-run 验证 SQL Server 写入预期
- **WHEN** 执行采购入库单 dry-run
- **THEN** 输出 SHALL 显示查询字段、样例记录、预计写入量、跳过量和 SQL Server 写入日志预期
