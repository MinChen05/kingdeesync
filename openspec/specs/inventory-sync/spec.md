## ADDED Requirements

### Requirement: Inventory sync uses current snapshot
The system SHALL synchronize `即时库存` from the current `STK_Inventory` snapshot and upsert rows by `FID` into `stk_inventory`, even when the selected sync mode is incremental.

#### Scenario: Incremental inventory sync queries snapshot
- **WHEN** `即时库存` is synchronized with sync mode `incremental`
- **THEN** the query filter MUST use the configured base filter without adding a `FUPDATETIME > last_time` condition

#### Scenario: Inventory snapshot preserves dimensions
- **WHEN** rows are written to `stk_inventory`
- **THEN** the system MUST preserve stock organization, stock, stock location, stock status, base unit, material, base quantity, and update time from the Kingdee row
