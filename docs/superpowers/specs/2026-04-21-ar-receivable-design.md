# AR_receivable 设计文档

## 目标

为金蝶应收单新增一条最小可用的同步链路，使项目可以：

- 从金蝶 `AR_receivable` 表单拉取应收单数据
- 将数据写入 SQL Server 业务表 `AR_receivable`
- 支持后续按 `FModifyDate` 做增量同步
- 复用现有 GUI、同步编排、日志和 SQL Server upsert 能力

本次目标只覆盖“单表新增同步能力”和“目标表创建”，不做无关重构。

## 范围

本设计只包含以下内容：

- 新增“应收单”表单查询配置
- 新增“应收单”表映射与 writer 映射
- 新增 `AR_receivable` 目标表建表脚本
- 新增应收单字段映射、写入逻辑和 SQL Server upsert 主键配置
- 新增与 `AR_receivable` 相关的索引定义
- 新增相关单元测试和建表脚本 dry-run 验证

本设计不包含：

- 报表相关表结构调整
- 现有同步框架重构
- “应收/应付单”通用化抽象
- 默认同步表单集合的自动变更
- 生产数据清理或任何破坏性删除

## 当前状态

现有仓库已经具备完整的业务单据同步骨架，关键路径如下：

- `src/config/form-queries.json` 负责表单查询参数
- `src/config/tables.json` 负责表单到目标表、writer 的映射
- `src/core/sales_writer.py` 负责业务写入 SQL 模板
- `src/core/mysql_manager.py` 负责数据准备、主键匹配、写入委派
- `src/core/upsert_engine_sqlserver.py` 负责 SQL Server `MERGE`
- `src/core/index_manager.py` 负责业务表索引维护
- `src/services/sync_service.py` 与 GUI 页面从配置自动读取可用表单

现有最接近的参考对象是“应付单”：

- 表单：`AP_Payable`
- 目标表：`AP_Payable`
- 已有字段补齐、writer、prepare、SQL Server upsert 支持

因此，本次最稳妥的方案是按“应付单”的接入方式，为“应收单”新增一条独立链路，而不是改造公共抽象。

## 方案比较

### 方案 1：独立新增 `AR_receivable` 链路

做法：

- 新增“应收单”配置
- 新增 `AR_receivable` 表
- 新增独立 writer、prepare、主键映射和测试

优点：

- 改动最小
- 风险最低
- 与现有“应付单”模式一致，便于维护
- GUI 不需要专门改代码，配置生效后会自动出现

缺点：

- 需要新增一套应收单字段映射代码

### 方案 2：抽象为“财务往来单据通用写入器”

做法：

- 重构现有应付单写入逻辑
- 让应收/应付共用一套财务单据 writer

优点：

- 后续再加类似单据时复用度更高

缺点：

- 需要修改公共写入路径
- 测试面扩大
- 不符合当前“优先最小改动”的要求

### 方案 3：只创建数据库表，不接程序同步

做法：

- 只新增 `AR_receivable` 表，不修改同步代码

优点：

- 实施最快

缺点：

- 程序仍无法同步应收单
- 后续仍需再做一轮代码接入
- 不满足“新增同步单据”的实际目标

## 推荐方案

采用方案 1。

原因：

- 与当前仓库结构最匹配
- 可以完整交付“可同步 + 可建表 + 可验证”
- 改动集中在配置、writer、prepare、建表脚本和测试，边界清晰

## 数据设计

本次新增 SQL Server 业务表：

- 表名：`AR_receivable`

建议字段如下：

1. `FID BIGINT NULL`
2. `FENTRYID BIGINT NOT NULL`
3. `FSEQ INT NULL`
4. `FBILLNAME NVARCHAR(255) NULL`
5. `FBILLNO NVARCHAR(80) NULL`
6. `FDATE DATE NULL`
7. `FCUSTOMERNAME NVARCHAR(255) NULL`
8. `FSETACCOUNTTYPE NVARCHAR(50) NULL`
9. `FBASEPROPERTY1 NVARCHAR(255) NULL`
10. `FMODIFYDATE DATETIME2 NULL`
11. `SYNC_TIME DATETIME2 NOT NULL DEFAULT GETDATE()`

字段来源映射如下：

- `FID -> FID`
- `FEntityDetail_FENTRYID -> FENTRYID`
- `FEntityDetail_FSEQ -> FSEQ`
- `FBillTypeID.FNAME -> FBILLNAME`
- `FBillNo -> FBILLNO`
- `FDATE -> FDATE`
- `FCUSTOMERID.FNAME -> FCUSTOMERNAME`
- `FSetAccountType -> FSETACCOUNTTYPE`
- `F_ora_BaseProperty1 -> FBASEPROPERTY1`
- `FModifyDate -> FMODIFYDATE`

类型选择依据：

- `FENTRYID` 作为 SQL Server `MERGE` 匹配键，需要唯一且非空
- 文本类字段长度按现有业务表常用口径设置，优先保证首版稳定写入
- 本次不引入金额类字段，避免扩大类型判断和补列范围

## 索引设计

建议索引如下：

- 唯一聚集索引：`UX_AR_receivable_fentryid` on `FENTRYID`
- 普通索引：`IX_AR_receivable_modify_date` on `FMODIFYDATE`
- 普通索引：`IX_AR_receivable_billno` on `FBILLNO`

设计原因：

- `FENTRYID` 用于 SQL Server upsert 匹配，必须稳定唯一
- `FMODIFYDATE` 用于增量同步取最近修改时间
- `FBILLNO` 便于按单号核查

## 配置设计

### 表单查询配置

在 `src/config/form-queries.json` 中新增：

- 表单名称：`应收单`
- `FormId`: `AR_receivable`
- `FieldKeys`: `FID,FEntityDetail_FENTRYID,FEntityDetail_FSEQ,FBillTypeID.FNAME,FBillNo,FDATE,FCUSTOMERID.FNAME,FSetAccountType,F_ora_BaseProperty1,FModifyDate`
- `FilterString`: `FDocumentStatus = 'C' AND FSALEORGID.FNAME = '台州市金宇机电有限公司'`

### 表单映射配置

在 `src/config/tables.json` 中新增：

- `应收单 -> AR_receivable`
- `insert_method -> insert_ar_receivable`

配置完成后，GUI 可用表单列表会自动读到“应收单”，无需单独修改页面代码。

## 实现设计

### 1. 配置接入

修改：

- `src/config/form-queries.json`
- `src/config/tables.json`

结果：

- 同步编排能识别“应收单”
- GUI 表单列表自动出现“应收单”

### 2. 写入器接入

修改 `src/core/sales_writer.py`：

- 新增 `insert_ar_receivable(manager, data)`

职责：

- 生成 `INSERT INTO AR_receivable (...) VALUES (...)`
- 复用现有 `_batch_insert` 进入 SQL Server upsert 路径

### 3. 数据准备接入

修改 `src/core/mysql_manager.py`：

- 新增 `insert_ar_receivable`
- 新增 `_prepare_ar_receivable_data`
- 在 `_get_primary_key()` 中新增 `"ar_receivable": "FENTRYID"`

`_prepare_ar_receivable_data` 需要同时兼容：

- 字典格式响应
- 列表格式响应

并把字段顺序严格对齐 `insert_ar_receivable` 的 SQL 列顺序。

### 4. Writer 注册

修改 `src/core/writers_registry.py`：

- 注册 `insert_ar_receivable`

确保 `tables.json` 中的 `insert_method` 能成功解析。

### 5. SQL Server upsert 约束

修改 `src/core/upsert_engine_sqlserver.py`：

- 将 `AR_receivable` 纳入必填键过滤逻辑
- 建议按 `FID` 与 `FENTRYID` 至少校验 `FENTRYID` 非空

目标是：

- 避免空主键进入 `MERGE`
- 避免因脏数据导致整批失败

### 6. 索引维护

修改 `src/core/index_manager.py`：

- 增加 `AR_receivable` 的索引定义
- 增加 `AR_receivable` 到分析表名单

### 7. 建表工具

新增：

- `src/tools/create_ar_receivable_table.py`

脚本能力：

- 支持 `--dry-run`
- dry-run 时只输出 SQL，不执行
- 非 dry-run 时创建表和索引

本次不把整表创建逻辑塞入日常同步运行时，原因是：

- 运行期 DDL 风险更高
- 不利于定位同步异常
- 当前项目对业务表默认假设是“表已存在”

## 验证设计

按项目要求，完成后至少执行以下验证：

### 单元测试

至少补充以下测试：

- 配置接入测试
  - 验证“应收单”能从配置中被读取
  - 验证表映射和 writer 映射正确
- 字段映射测试
  - 验证 `_prepare_ar_receivable_data` 对字典和列表格式的解析结果
- SQL Server upsert 测试
  - 验证 `AR_receivable` 使用 `FENTRYID` 作为匹配键
  - 验证空主键行会被过滤

### Dry-run

执行建表脚本 dry-run：

```bash
python src/tools/create_ar_receivable_table.py --dry-run
```

预期：

- 打印完整 `CREATE TABLE`
- 打印 `CREATE INDEX`
- 不真正执行数据库写入

### SQL Server 写入验证

只选择“应收单”执行一次单表同步，检查：

- 目标表是否有新增或更新记录
- `FMODIFYDATE` 最大值是否合理
- 日志是否出现预期的批次写入信息

## 预期日志变化

### 建表阶段

预期日志包括：

- `正在创建表 AR_receivable...`
- `表 AR_receivable 创建成功。`
- `索引创建成功: UX_AR_receivable_fentryid`
- `索引创建成功: IX_AR_receivable_modify_date`

### 同步阶段

预期日志包括：

- `[应收单] 开始同步数据`
- `[应收单] 增量时间字段推断: FModifyDate`
- `处理批次 1/N，记录数: xxx`
- `批次 1 执行成功，写入 xxx 条记录`
- `成功插入/更新 xxx 条记录 (SQL Server)`
- `[应收单] 获取 xxx 条，插入 xxx 条数据`

如果没有新数据，预期日志为：

- `[应收单] 没有新数据需要同步`

如果字段类型或长度异常，现有 SQL Server 写入器仍会输出：

- 类型转换诊断日志
- 截断诊断日志

## 风险与控制

### 风险 1：金蝶返回字段类型与预期不一致

控制方式：

- 首版仅落地当前已确认字段
- 文本列长度适度放宽
- 复用现有 SQL Server 类型诊断日志

### 风险 2：`FENTRYID` 为空或重复

控制方式：

- upsert 前过滤空主键
- 目标表建立唯一索引

### 风险 3：增量同步时间字段判断错误

控制方式：

- 使用现有 `FilterBuilder` 自动识别 `FModifyDate`
- 为 `FMODIFYDATE` 建索引

### 风险 4：范围扩张

控制方式：

- 不做应收/应付通用化
- 不改默认同步范围
- 不修改报表表结构

## 非目标

以下内容明确不在本次范围内：

- 抽象新的公共财务单据框架
- 改造 GUI 页面布局
- 批量改动其他单据表结构
- 自动迁移历史应收单数据

## 交付物

本次设计对应的最终交付应包括：

- 配置变更
  - `src/config/form-queries.json`
  - `src/config/tables.json`
- 写入链路变更
  - `src/core/sales_writer.py`
  - `src/core/mysql_manager.py`
  - `src/core/writers_registry.py`
  - `src/core/upsert_engine_sqlserver.py`
  - `src/core/index_manager.py`
- 建表脚本
  - `src/tools/create_ar_receivable_table.py`
- 测试
  - 字段映射测试
  - 配置接入测试
  - SQL Server upsert 测试

## 自检

- 无 TBD/TODO 占位
- 范围仅覆盖“应收单”新增同步能力与目标表创建
- 表结构、字段映射、索引、验证、日志口径前后一致
- 不涉及报表表结构调整
