## Context

项目已有 `sync-data-authenticity` 能力，核心模块通过声明式 `AuthenticitySpec` 比对数据库行和金蝶 API 行；维护脚本已经能对采购订单、采购入库单执行 dry-run/verify，并处理 SQL Server 大批量参数拆批。（原因：扩展全表单应复用现有比较器、分类和报告模型）

当前同步表单定义分散在 `src/config/form-queries.json`、`src/config/tables.json` 和 writer 准备函数中。仅靠人工维护全表单映射容易出现 DB 列名、API 字段名、身份键不一致。（原因：字段映射需要先被发现和报告，再进入阻断规则）

## Goals / Non-Goals

**Goals:**

- 生成全同步表单真实性映射草案报告，包含表单、目标表、API FormId、身份键候选、阻断字段候选、warning 字段候选、字段覆盖状态。（原因：实现前先形成可审阅证据）
- 将除科目余额表外的已同步表单纳入 dry-run 规划，分批执行并输出 summary/detail/blockers。（原因：覆盖所有同步单据但控制执行风险）
- 对无法可靠确认身份键的表单标记 `[待确认]`，不默认进入自动回灌门禁。（原因：身份键不确定时不能自动写入）
- 保持所有脚本只读，禁止写 SQL Server。（原因：本 change 是真实性校验扩展，不是数据修复）

**Non-Goals:**

- 不执行生产数据回灌或补写。
- 不修改数据库 schema、主键、索引或报表表结构。
- 不把科目余额表纳入第一批字段级真实性审计。（原因：报表接口参数和行身份模型不同，需要单独设计）
- 不把弱字段如描述、规格、条码、自定义文本作为第一版阻断项。（原因：先降低噪声，聚焦业务真实性核心）

## Decisions

### Decision 1: 先做 schema discovery，再扩展阻断规则

实现一个 discovery 报告，读取 `form-queries.json`、`tables.json`、当前 DB 列和已有 `AUDIT_SPECS`，输出 `authenticity_mapping_draft.csv`。（原因：全表字段多且命名不统一，先做发现能减少硬编码误判）

备选方案是直接手写所有 `AuthenticitySpec`。该方案速度快，但容易遗漏 DB 字段和 writer 实际落库列，暂不采用。（原因：真实性校验最怕错字段造成假通过）

### Decision 2: 表单分三批 dry-run

第一批覆盖业务单据：销售、采购、应收应付、委外、发货通知单。第二批覆盖生产与预测。第三批覆盖即时库存、基础资料、BOM。（原因：按业务域分批能隔离 API 超时、字段口径差异和数据量风险）

### Decision 3: 身份键不确定时进入报告，不进入自动回灌候选

没有明确 `FID` 或分录 ID 的表单先输出 `[待确认]`，dry-run 可报告缺口，但不得把这些表单标记为可自动回灌。（原因：身份键不可靠时写库风险最高）

### Decision 4: 即时库存采用快照组合键

即时库存不依赖增量时间；真实性身份使用库存组织、仓库、仓位、库存状态、物料、基本单位组成快照键，`FBASEQTY` 作为阻断数量，`FUPDATETIME` 作为 warning。（原因：即时库存是当前状态快照，不适合按单据分录身份校验）

## Risks / Trade-offs

- [Risk] 部分 DB 表列名与 API 字段名不一致 → 通过 discovery 报告标记 `missing_db_field` / `missing_api_field`，先人工确认再阻断。（原因：避免把字段命名问题误判为业务差异）
- [Risk] 大表 dry-run 查询耗时或 API 超时 → 按批次、拆批参数、分页查询，并记录每批耗时。（原因：降低一次性全量扫描风险）
- [Risk] warning 字段过多导致报告噪声大 → 第一版 summary 单独统计 warning，不阻断 dry-run 通过。（原因：日期和状态常随业务流程变化）
- [Risk] 基础资料没有分录结构 → 使用主数据 ID/编码作为身份键，并只比较核心编码、名称、组织、状态。（原因：基础资料真实性口径不同于单据）

## Migration Plan

1. 新增 discovery 报告，不影响现有采购 dry-run 命令。
2. 增量补充 `AuthenticitySpec`，每批有单元测试覆盖身份键、阻断项、warning 项。
3. 先执行 discovery，再执行第一批 dry-run；确认报告后再推进第二、第三批。
4. 如任一表单出现身份键缺失或大量 blocker，暂停该表单，保留报告供人工确认。（原因：真实性校验不能在身份不明时继续自动化）
