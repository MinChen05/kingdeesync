# ADR-0007: 快照表单的 TRUNCATE 并入写入事务

- **状态**：Accepted（2A、2B 已实现并提交；真实实例原子性验证待补）
- **日期**：2026-11-02
- **相关**：`docs/adr/0001`（Staging + MERGE）、`docs/adr/0004`（移除影子表与切换）、
  `docs/adr/0006`（脏运行恢复）、`docs/superpowers/reports/2026-11-02-target-db-memory-grant-starvation.md`

## 背景

快照表单（`即时库存` → `stk_inventory`、`科目余额表` → `gl_rpt_accountbalance`，
判定见 `syncengine/engine.go:1867 isSnapshotForm`）当前的执行顺序是两段彼此独立的写：

```
① db.DB.Exec("TRUNCATE TABLE dbo.<表>")      ← 无 ctx、自动提交、不参与任何事务   engine.go:1307
② writer.Upsert(ctx, …) → staging + MERGE    ← 自己 BeginTxx / Commit            sqlserver_writer.go:129-146
```

只要 ① 成功而 ② 失败，目标表就变成**空表**，且无法通过回滚恢复。

2026-11-02 事故实测：目标库内存授予队列被外部报表作业占住（FIFO，我方 MERGE 拿不到授予），
12:00 起连续 5 轮"清空成功、写入 0 行、30 分钟超时"，`dbo.stk_inventory` 取证时 **0 行**，
`MAX(SYNC_TIME)` 为 NULL。次生效应：增量窗口下界取自目标表 `MAX(SYNC_TIME)`
（`db/database.go:182 GetLastSyncTime`），空表使每轮退化为全量拉取。

这与 ADR-0001 宣称的正面结论"MERGE 天然幂等，重跑安全"直接矛盾：**幂等性被事务外的
TRUNCATE 破坏了**。快照表单因此成为全系统唯一"失败即丢数据"的写入路径。

## 决策

快照表单的写入改为**单事务内整体替换**，其余表单保持 ADR-0001 的 Staging + MERGE 不变：

1. staging 装载仍在事务外（沿用 `stagingUpsert` 的建表与批量插入，`sqlserver_writer.go:93-101`）。
2. 替换动作合并为一个事务：

   ```
   BEGIN TRAN
     TRUNCATE TABLE dbo.<目标表>            -- 无替换作用域时
     -- 或 DELETE t FROM dbo.<目标表> AS t JOIN dbo.<staging> AS s ON t.<作用域列> = s.<作用域列>
     INSERT INTO dbo.<目标表> (列…) SELECT 列… FROM dbo.<staging>
   COMMIT      -- 任一步失败 → ROLLBACK，目标表保持上一轮数据
   ```

   作用域列由 `snapshotSpecFor` 逐表单声明（`即时库存` 无作用域＝整表替换；`科目余额表`
   按 `FACCTYEAR,FACCTPERIOD` 只替换本批涉及的期间）。事务边界与"整体换入"语义不变，
   变的只是删除范围（原因：增量轮只取最近若干期，整表删除会抹掉窗口外的历史期间，issue #7）。
   提交前额外核对 `行数(affected) == staging 装载行数`，不一致同样回滚
   （原因：半张表比整轮回滚更糟）。空快照与 0 行装载一律拒绝执行，
   绝不允许"清空而不写回"。

3. staging 的 `DROP` 移出业务上下文：用 `context.WithoutCancel(ctx)` + 独立短超时执行，
   失败时记录表名（不再静默丢弃）。事务回滚不属同一问题——`database/sql` 的 `Tx` 没有
   `RollbackContext`，`Rollback()` 内部使用独立上下文，取消信号不会令其失败，
   因此只补错误可见性（原因：只有事务外的 staging DDL 才是真实泄漏点，事故遗留 9 张表已证实）。
4. 落地方式：`RowWriter` 增加**可选能力接口**（如 `SnapshotReplacer`），由
   `SQLServerWriter` 实现；引擎在 `isSnapshotForm` 分支改调该接口并删除裸 `TRUNCATE`
   （`engine.go:1289-1316`）。未实现该接口的写入器保持现行为，避免把 SQL Server 语义
   渗进抽象层。

### 已否决 / 备选

- **B3 换表 / 重命名切换**：否决。ADR-0004 已明确移除"影子表、切换、快照审批机制"。
- **B2 取消 TRUNCATE，改 MERGE + 按 PK 集合删孤儿**（走 `SnapshotManager` 完整性校验，
  `written ≠ fetched` 即拒绝删除）：可行且无 DDL，但 6 万级 PK 差集删除成本需评估，
  且失败时会留下"上一轮 + 本轮混合"数据，语义不如整体替换清晰。作为退路保留。

## 后果

- 正面：
  - 快照表单失败降级为"本轮没更新"，不再是"表被清空"；目标表在读侧永远只呈现完整快照。
  - 事务内 `TRUNCATE + INSERT…SELECT` 比 6 万行 MERGE 更省（无需 PK 比对、无 `UPDATE SET` 分支），
    也顺带消除 ADR-0001 记录过的"必须在 MERGE 前统计已存在 PK"这类计数坑。
  - 配合取消路径的 `WithoutCancel` 清理，停止在生产库堆积 `stg_*`（本次事故遗留 9 张、约 46 万行）。
- 负面与风险：
  - **锁持有时间变长**：替换期间目标表被写锁保护，长查询可能等待（此前 TRUNCATE 是瞬时点）。
    以 `stk_inventory` 6 万行为例，基线耗时 22~32 秒（2026-11-02 10:04 轮实测 32.2 秒）。
  - **事务日志集中增长**：整体替换在一个事务内完成，日志峰值高于分批 MERGE。
  - **取消仍可能留下已提交写入**：若事务已 COMMIT 而 ctx 随后取消，本轮数据是完整的，属可接受结果。
  - 无单测覆盖真实 mssql 路径（项目既有约束：`sqlserver_writer.go:327-329` 已记录"mssql 路径无单测覆盖"），
    需以带门控的集成测试 + 灰度轮次验证。
- 需要同步的文档：
  - `CONTEXT.md` 术语表中"快照表单……TRUNCATE 重写后无孤儿"须改为"单事务内整体替换，失败保留上一轮快照"。
  - 排队守卫（检测目标库 `RESOURCE_SEMAPHORE` 排队即跳过本轮）与单表单级超时属不同决策，
    实现后另立 `ADR-0008`（草稿待补）。
- 回滚：本变更集中在 `sqlserver_writer.go` 与 `engine.go` 的 `isSnapshotForm` 分支，
  不引入配置开关，回滚即 `git revert`（原因：避免为一次性迁移保留双路径）。

## 落地清单

- [x] `SQLServerWriter` 实现事务内替换（`ReplaceSnapshot`）；引擎快照分支改调该接口，不再事务外 `TRUNCATE`
      原子性集成测试 `TestSQLServerReplaceSnapshotIsAtomic`（需 `MSSQL_INTEGRATION=1`）**已在真实实例通过**：
      违反约束的换入整体回滚、目标表保持上一轮行数与取值，空快照被拒绝，覆盖后无旧主键残留，失败不留 `stg_*`
- [x] staging `DROP` 改用 `context.WithoutCancel` + 独立超时，失败记录表名；`Rollback` 补错误可见性（2A）
- [x] 单表单预算 `form_run_timeout_minutes`（默认 10）：超预算只失败该表单并写明原因，整轮继续（2C）
- [x] 目标库排队守卫 `grant_wait_guard_seconds`（默认 60，-1 关闭）：`RESOURCE_SEMAPHORE` 排队超阈值时
      跳过本轮并推送通知；探测失败按放行处理，避免把抖动放大成停摆（2E）
- [x] 排队守卫扩展至 API 手动触发路径：`createRun` 与 `retryFailedForms` 复用
      `schedule.GuardGrantQueueForTrigger`，命中返回 409 `TARGET_DB_GRANT_QUEUE_BUSY`；守卫探测置于取
      `syncMutex` 之前，不反向阻塞其他 runs 接口
      （原因：2026-11-03 卡死的是 API 手动触发的全量，手动路径不经过 runJob、完全绕过守卫，
      同样会发起注定超时的空跑并清空快照表）
- [x] 单表单预算支持按表单覆盖 `form_run_timeout_overrides`（"表单名=分钟" 逗号分隔，非法条目忽略）：
      历史过千万的大单据与小表共用预算时只能按最大者放宽，按键覆盖兼顾小表卡死保护
- [x] `RecoverAbnormalRuns`（心跳超时路径）同样补写 `duration_seconds`
      （原因：该路径与超时中止路径产出同一个 `failed_abnormal_exit` 告警，缺耗时即显示 0 秒）
- [x] 测试：取消路径清理仍执行；终态不被覆盖；整表替换原子性集成测试已在真实实例通过
- [x] 作用域替换集成测试 `TestSQLServerReplaceSnapshotScoped` **已在真实实例通过**（2026-11-03 00:18，
      停调度后执行，101s）：跨期间保留、作用域内旧行换入、违反约束整体回滚、NULL 作用域拒绝且无副作用、
      空作用域退化整表、全程无 `stg_*` 残留（原因：单测只能覆盖拒绝分支，`DELETE t FROM … JOIN staging`
      必须由真实 SQL Server 验证）
- [x] 快照表单替换作用域化（issue #7 路线 A）：`snapshotSpecFor` 声明作用域列，
      `ReplaceSnapshot` 用 `DELETE t FROM 目标 JOIN staging` 替换作用域内行，
      `scopeCols` 为空才 `TRUNCATE` 整表；作用域列缺失或取值 NULL 直接拒绝且不接触数据库
- [x] 更新 `CONTEXT.md` 快照表单定义（"整表替换"→"按声明的作用域替换"）；
      `docs/architecture/current-runtime.md` 不含快照写入语义描述，无需改动
- [ ] 上线验证：`科目余额表` 全量回填后，增量轮不得把窗口外期间归零（见设计文档 §8）
