## Why

即时库存是库存余额快照，不是单据流水。按 `MAX(FMODIFYDATE)` 做普通增量会在分页同步期间漏掉部分较早页发生的库存变化，导致本地库存与金蝶当前库存对不上。（原因：库存更新不是按本地最大更新时间严格单调推进）

## What Changes

- 将“即时库存”在增量同步模式下改为查询当前完整快照，并继续按 `FID` 幂等 upsert 覆盖本地 `stk_inventory`。（原因：保持同步入口不变，同时避免时间游标漏数）
- 保留其他表单的原有增量过滤逻辑不变。（原因：单据类表单仍适合按修改时间增量同步）
- 增加过滤器回归测试，锁定即时库存不拼接 `FUPDATETIME > last_time`。（原因：防止后续误把余额表改回普通增量）

## Capabilities

### New Capabilities

- `inventory-sync`: 即时库存同步按金蝶当前库存快照覆盖本地库存余额。（原因：仓库中尚无即时库存同步主规格，本次补齐行为合同）

### Modified Capabilities

- 无。（原因：仓库中尚无即时库存同步的正式 OpenSpec 主规格）

## Impact

- 影响代码：`src/core/filter_builder.py`。
- 影响测试：`tests/test_filter_builder.py`。
- 不涉及数据库结构变更，不新增依赖，不改变对外接口。（原因：仅调整查询过滤口径）
