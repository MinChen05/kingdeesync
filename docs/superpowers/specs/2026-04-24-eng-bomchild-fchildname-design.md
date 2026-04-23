# ENG_BOMCHILD FCHILDNAME Design

## Goal

为物料清单子项同步链路新增金蝶字段 `FMATERIALIDCHILD.FNAME`，并落库到 SQL Server 业务表 `eng_bomchild` 的新字段 `FCHILDNAME`。同时将 `eng_bomchild` 的推荐字段顺序与实际 SQL Server 物理列顺序调整到项目约定顺序，保证后续同步写入与数据库结构一致。

## Scope

本设计仅覆盖以下内容：

- 更新“物料清单子项”API `FieldKeys`
- 更新 Python 侧物料清单子项映射与写库 SQL
- 新增 `eng_bomchild.FCHILDNAME`
- 更新 `eng_bomchild` 推荐字段顺序并执行 SQL Server 重排
- 补充相关单元测试与 dry-run 验证

不包含：

- 报表相关表结构调整
- GUI 展示改动
- 无关同步链路重构

## Database Impact

本次数据库影响如下：

- 表：`eng_bomchild`
- 变更：新增可空文本字段 `FCHILDNAME`
- 主键：不变，仍为 `FID,FENTRYID`
- 唯一键：不变
- 旧数据：保留，历史行新字段默认 `NULL`
- 物理列顺序：会通过现有安全重排脚本调整

重排方式沿用现有脚本能力：

- 创建临时表
- 复制原表数据
- 校验复制前后行数一致
- 重建索引
- 交换正式表与备份表
- 再次校验换表前后行数一致

## Current State

当前仓库中的“物料清单子项”同步链路已具备以下基础：

- `src/config/form-queries.json` 与 `dotnet/form-queries.json` 已包含 `FMATERIALIDCHILD.FNUMBER`
- `src/core/mysql_manager.py::_prepare_eng_bom_child_data` 已支持 `FCHILDNUMBER`
- `src/core/masterdata_writer.py::insert_eng_bom_child` 已写入 `FCHILDNUMBER`
- `src/core/upsert_engine_sqlserver.py` 中 `eng_bomchild` staging 特判分支已支持 `FCHILDNUMBER`
- `src/tools/sqlserver_business_layout.py` 中 `eng_bomchild` 推荐顺序已包含 `FCHILDNUMBER`

当前尚未覆盖的点：

- “物料清单子项”`FieldKeys` 不包含 `FMATERIALIDCHILD.FNAME`
- `eng_bomchild` 当前无 `FCHILDNAME` 目标列
- `_prepare_eng_bom_child_data()` 尚未映射 `FCHILDNAME`
- `insert_eng_bom_child()` 尚未写入 `FCHILDNAME`
- `eng_bomchild` 的 SQL Server staging 手写列清单尚未包含 `FCHILDNAME`
- `eng_bomchild` 推荐顺序尚未给 `FCHILDNAME` 预留位置

## Options Considered

### Option 1: 只改数据库，不改同步代码

优点：

- 实施快

缺点：

- API 不会拉取 `FMATERIALIDCHILD.FNAME`
- Python 不会映射和写入 `FCHILDNAME`
- 不能满足“新增同步字段”目标

### Option 2: 只改代码，不显式建库字段

优点：

- 代码链路完整

缺点：

- SQL Server upsert 遇到缺列时会忽略该列
- 新字段可能在运行中被静默丢弃
- 不满足“创建数据库字段并排序”的目标

### Option 3: 同步修改代码、显式补字段并执行重排

优点：

- 一次完成 API 拉取、字段映射、写库、建字段和排序
- 复用项目现有补列模式和重排脚本
- 风险和改动面最小

缺点：

- 需要执行一次数据库结构变更和物理列重排

## Recommendation

采用 Option 3。

原因：

- 最符合当前需求：“新增一个字段 `FMATERIALIDCHILD.FNAME`”
- 与 `FCHILDNUMBER` 的实现路径保持一致，维护成本最低
- 避免 `FCHILDNAME` 被 SQL Server 缺列忽略逻辑静默跳过

## Data Design

- 来源字段：`FMATERIALIDCHILD.FNAME`
- 落库表：`eng_bomchild`
- 新列名：`FCHILDNAME`
- SQL Server 类型：`NVARCHAR(255) NULL`
- MySQL 兼容类型：`VARCHAR(255) NULL`

命名选择 `FCHILDNAME` 的原因：

- 与现有 `FCHILDNUMBER` 保持命名风格一致
- 避免与其他通用 `FNAME` 字段混淆
- 语义上明确表示“子项物料名称”

## Recommended Column Order

`eng_bomchild` 推荐字段顺序调整为：

1. `FID`
2. `FENTRYID`
3. `FSEQ`
4. `FMASTERID`
5. `FMATERIALID`
6. `FCHILDNUMBER`
7. `FCHILDNAME`
8. `FMATERIALTYPE`
9. `FNUMERATOR`
10. `FDENOMINATOR`
11. `FQTY`
12. `FACTUALQTY`
13. `FISSUETYPE`
14. `FBACKFLUSHTYPE`
15. `FSUPPLYORG`
16. `FSTOCKID`
17. `FENTRYROWID`
18. `FREPLACEGROUP`
19. `FMODIFYDATE`
20. `SYNC_TIME`

`FCHILDNAME` 放在 `FCHILDNUMBER` 后、`FMATERIALTYPE` 前，形成连续的“子项物料信息块”：

- `FMATERIALID`
- `FCHILDNUMBER`
- `FCHILDNAME`
- `FMATERIALTYPE`

## Implementation Design

### API Query Configuration

在以下配置中为“物料清单子项”新增 `FMATERIALIDCHILD.FNAME`：

- `src/config/form-queries.json`
- `dotnet/form-queries.json`

新增位置放在 `FMATERIALIDCHILD.FNUMBER` 之后，保证返回顺序与本地映射顺序一致。

### Write Path

更新 `src/core/masterdata_writer.py::insert_eng_bom_child`：

- `INSERT INTO eng_bomchild (...)` 新增 `FCHILDNAME`
- `VALUES (...)` 新增对应占位符
- `ON DUPLICATE KEY UPDATE` 新增 `FCHILDNAME = VALUES(FCHILDNAME)`

### Payload Mapping

更新 `src/core/mysql_manager.py::_prepare_eng_bom_child_data`：

- 字典模式支持：
  - `FMATERIALIDCHILD.FNAME`
  - `FMATERIALIDCHILD.FName`
  - `FCHILDNAME`
- 列表模式按新的 `FieldKeys` 顺序插入 `FCHILDNAME`
- 返回 tuple 顺序与写库 SQL 保持一致

### Schema Safety

扩展 `src/core/mysql_manager.py::_ensure_additional_columns_for_eng_bomchild()`：

- SQL Server：
  - `ALTER TABLE eng_bomchild ADD FCHILDNAME NVARCHAR(255) NULL`
- MySQL：
  - `ALTER TABLE eng_bomchild ADD COLUMN FCHILDNAME VARCHAR(255) NULL`

该函数继续在 `src/core/masterdata_writer.py::insert_eng_bom_child` 执行写库前调用。

这样可以确保：

- 首次同步时字段存在
- 不依赖 SQL Server upsert 对缺列的忽略逻辑
- 已有环境可平滑补列

### SQL Server Staging Compatibility

更新 `src/core/upsert_engine_sqlserver.py` 中 `eng_bomchild` 的 staging `INSERT ... SELECT TRY_CAST(...)` 分支：

- 在列清单中加入 `FCHILDNAME`
- 明确使用 `TRY_CAST(? AS NVARCHAR(255))`
- 保持参数顺序与 `insert_eng_bom_child` 和 `_prepare_eng_bom_child_data` 完全一致

建议 staging 物料信息块顺序为：

- `FMATERIALID`
- `FCHILDNUMBER`
- `FCHILDNAME`
- `FNUMERATOR`

这是本次改动的关键兼容点，因为 `eng_bomchild` staging 分支不是动态生成，而是手写列列表。

### Column Reorder

更新 `src/tools/sqlserver_business_layout.py` 中 `eng_bomchild` 的目标顺序，然后使用现有脚本：

- dry-run：
  - `python scripts/reorder_sqlserver_business_tables.py --tables eng_bomchild`
- 实际执行：
  - `python scripts/reorder_sqlserver_business_tables.py --execute --tables eng_bomchild`

脚本会校验：

- 临时表复制前后行数一致
- 换表后 live/backup 行数一致

## Error Handling

- 如果 `FCHILDNAME` 已存在，补列逻辑应幂等跳过
- 如果补列失败，应记录可见错误日志，不执行破坏性删除
- 如果 staging 列顺序不一致导致 SQL 组装异常，应通过单元测试提前暴露
- 如果重排脚本发现行数不一致，应停止执行，不删除备份表

## Testing

需要新增或更新以下测试：

- `tests/test_eng_bomchild_field_mapping.py`
  - 验证 `_prepare_eng_bom_child_data()` 能从字典载荷中提取 `FMATERIALIDCHILD.FNAME`
  - 验证 list 模式能正确映射 `FCHILDNAME`
  - 验证 SQL Server/MySQL 补列逻辑会生成 `FCHILDNAME` 的 `ALTER TABLE`
- `tests/test_sqlserver_business_layout.py`
  - 验证 `FCHILDNAME` 位于 `FCHILDNUMBER` 与 `FMATERIALTYPE` 之间
- `tests/test_upsert_engine_sqlserver.py`
  - 验证 `eng_bomchild` staging SQL 已包含 `FCHILDNAME`
  - 验证 `FCHILDNUMBER` 与 `FCHILDNAME` 的 cast 顺序正确

至少执行以下验证：

- 相关单元测试
- SQL Server 重排脚本 dry-run
- 如执行实际重排，再核对脚本输出的行数校验结果

建议验证命令：

```powershell
python -m unittest tests.test_eng_bomchild_field_mapping tests.test_sqlserver_business_layout tests.test_upsert_engine_sqlserver -v
```

```powershell
python scripts/reorder_sqlserver_business_tables.py --tables eng_bomchild
```

```powershell
python scripts/reorder_sqlserver_business_tables.py --execute --tables eng_bomchild
```

## Expected Logging

涉及 SQL Server 写入时，预期日志变化如下：

- 首次写入前如果字段不存在，预期出现类似：
  - `已为 eng_bomchild.FCHILDNAME 创建字段`
- 正常同步后，不应再出现类似：
  - `[eng_bomchild] 目标库缺失列，已自动忽略: ['FCHILDNAME']`
- SQL Server 重排脚本会输出：
  - `=== eng_bomchild ===`
  - `rows: ...`
  - `current: ...`
  - `desired: ...`
- 实际重排成功后，脚本输出：
  - `applied: eng_bomchild`

## Self-Review

- 无 `TBD`、`TODO` 或占位描述
- 作用域只覆盖 `eng_bomchild.FCHILDNAME` 新增与排序
- 字段来源、落库列名、类型、顺序、测试和验证步骤前后一致
- 已明确 SQL Server 不会自动补该字段，避免实现阶段误判
