## Problem

即时库存同步前按 `FUPDATETIME > 本地最大 FMODIFYDATE` 构造增量过滤。对库存余额快照来说，这个游标不可靠：全表分页期间如果前面页的库存被业务更新，而后面页存在更晚更新时间，本地最大更新时间会被推进，下一次增量就可能跳过那条前面页变化。

## Solution

在 `FilterBuilder.build_filter_string()` 中对 `form_name == "即时库存"` 做快照同步处理：

- 当同步类型是 `incremental` 时，直接返回配置中的基础过滤条件。
- 当前配置基础过滤条件是 `1=1`，因此会查询金蝶当前完整库存快照。
- 写库逻辑仍走现有 `insert_stk_inventory`，按 `FID` upsert 覆盖本地记录。

## Verification

- 单元测试验证即时库存增量同步不会拼接 `FUPDATETIME > last_time`。
- 单元测试验证普通表单仍使用既有增量过滤。
- 编译检查确认语法无误。
