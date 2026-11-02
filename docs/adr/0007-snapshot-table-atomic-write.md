# ADR-0007: 快照表单的 TRUNCATE 并入写入事务

- **状态**：Proposed（草稿，未实施）
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
     TRUNCATE TABLE dbo.<目标表>
     INSERT INTO dbo.<目标表> (列…) SELECT 列… FROM dbo.<staging>
   COMMIT      -- 任一步失败 → ROLLBACK，目标表保持上一轮数据
   ```

3. staging 的 `DROP` 移出业务上下文：用 `context.WithoutCancel(ctx)` + 独立短超时执行，
   失败时记录表名（不再静默丢弃）。同一处理用于 `ROLLBACK`。
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

- [ ] `SQLServerWriter` 实现事务内替换；`engine.go` 移除裸 `TRUNCATE`
- [ ] staging `DROP` / `ROLLBACK` 改用 `context.WithoutCancel` + 独立超时，失败记录表名
- [ ] 单表单级超时（新增 `form_run_timeout_minutes`，默认 10）
- [ ] `RecoverAbnormalRuns`（心跳超时路径）同样补写 `duration_seconds`
- [ ] 测试：取消路径清理仍执行；终态不被覆盖；集成测试门控下跑通快照表单整轮替换
- [ ] 更新 `CONTEXT.md` 快照表单定义与 `docs/architecture/current-runtime.md`
