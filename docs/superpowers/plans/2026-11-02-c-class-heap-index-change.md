# C 类堆表索引变更方案（gl_rpt_accountbalance / sal_returnstock）

- 状态：部分落地——sal_returnstock 一支脚本已定稿入库（docs/sqlserver-change-sal-returnstock-unique-index.sql，
  等 DBA 执行窗口，见 issue #6，窗口依赖 #5 解除）；gl_rpt_accountbalance 一支的快照作用域替换（路线 A）
  已先行落地（issue #7，代码 12ffae9，生产已验证），其改键/列宽收窄/唯一索引仍待评审与 DDL 窗口（需 DBA 与业务口径确认）
- 关联：issue #3（主键契约）、issue #4（快照粒度决策）、ADR-0007
- 数据取自 2026-11-02 23:26 对生产目标库 `10.10.10.191/Kingdee` 的只读实测

## 1. 范围

只处理 issue #3 对账中的 **C 类**：目标表存在但**没有任何主键或唯一索引**的两张表。

A 类（代码键是唯一键超集）与 B 类（按业务码匹配）不在本方案内；
`gl_rpt_accountbalance` 的键本身错误问题需要业务口径确认，本文只给出探查与两条路线，不擅自改。

## 2. 实测前置数据

| 指标 | `gl_rpt_accountbalance` | `sal_returnstock` |
|---|---|---|
| 行数 | 38,788 | 106,087 |
| 拟定键 | `FBALANCEID` | `FENTRYID` |
| 键为 NULL 的行 | 0 | 0 |
| 键为空串的行 | **6** | 0 |
| 重复键组数 / 最大重复度 | **318 组 / 5,145 次** | **0 组** |
| 重复样例 | `2202.02 ×5145`、`6601.11 ×4522`、`1122 ×4140`、`6601.23 ×2772`、`6401.01.01 ×2732` | — |
| 被外键引用 | 无 | 无 |
| 现有索引 | 堆表，无索引 | 堆表，无索引 |

环境事实：SQL Server 2022 **Developer Edition**（含企业版特性，支持 `ONLINE` 索引操作）；
`max server memory = 2147483647`（未设上限）、`query wait (s) = -1`（无限等待）、tempdb 约 1.1 GB。

## 3. 分表结论

### 3.1 `sal_returnstock`：可以直接建唯一索引 ✅

106,087 行、0 重复、0 NULL，当前数据即满足唯一约束，无需清理。

```sql
-- 变更前复核（必须返回 0 行）
SELECT FENTRYID, COUNT(*) AS c
FROM dbo.sal_returnstock
GROUP BY FENTRYID
HAVING COUNT(*) > 1 OR COUNT_BIG(*) > 1;

-- 建索引（Developer/Enterprise 支持 ONLINE，不阻塞 DML）
CREATE UNIQUE NONCLUSTERED INDEX UQ_sal_returnstock_FENTRYID
    ON dbo.sal_returnstock (FENTRYID)
    WITH (ONLINE = ON, DATA_COMPRESSION = NONE);
```

回滚：

```sql
DROP INDEX IF EXISTS UQ_sal_returnstock_FENTRYID ON dbo.sal_returnstock;  -- 2022 支持 DROP INDEX IF EXISTS
```

收益：`FENTRYID` 从"靠约定"变成数据库约束；MERGE 匹配歧义（8672）与重复行堆积同时被封死。

### 3.2 `gl_rpt_accountbalance`：**不能建**，且发现更根本的缺陷

`FBALANCEID` 的取值形如 `2202.02`、`6601.11`、`6401.01.01` —— 这是**会计科目编码**，不是余额记录主键。
一行是"某科目某期间的余额"，同科目跨期重复出现完全正常。实测印证：

```
总行数 38,788；2025 年行数 0；2026 年 1-4 期行数 0；2026 年 5-10 期行数 38,788
DISTINCT(FACCTYEAR|FACCTPERIOD) = 6；SYNC_TIME 单批 2026-11-02 10:03:30
```

即当前表内容恰好等于**一次增量轮 6 期窗口**的产物，2025 年历史期间一行不剩。

## 3.3 【新发现，优先级高于索引】快照语义与期间窗口不自洽

该表被登记为快照表单（`isSnapshotForm`）→ **每轮整表替换**；但它拉取的期间随模式不同：

| 模式 | 期间窗口 | 代码位置 |
|---|---|---|
| `incremental`（工作日每 2 小时） | 最近 6 期 | `accountBalanceStartPeriod(now, 6)` |
| `full` / `reset`（周日 02:00） | `2025-01` 至上期（约 22 期） | `startYear, startPeriod := 2025, 1` |

因此**每一次增量轮都会静默删除 6 期之外的全部历史期间**，只有周日全量才短暂恢复；
表内容取决于"上一次跑的是哪种模式"。下游报表若引用超过 6 期，会随时点不同而查不到数据。

这与 ADR-0001 记录的优化直接相关：当年为把 14 分钟降到 4 分钟，只改了**拉取窗口**，
没有改**写入语义**（仍是整表替换）——两者组合才产生丢期。

两条修复路线（需业务口径确认，二选一）：

- **路线 A（推荐）：按期间作用域替换**。快照只删除并重写本批覆盖的 `(FACCTYEAR, FACCTPERIOD)`，
  保留窗口外历史期间。这样增量与全量不再互相抹除，且唯一键自然成为
  `(FBALANCEID, FDETAILNUMBER, FACCTYEAR, FACCTPERIOD)`，可随之建唯一索引。
- **路线 B：承认"报表只需最近 N 期"**。则全量窗口也应收敛到同样的 N 期，
  并显式声明该表不含历史；不能维持现在"两种模式写出两种内容"的状态。

无论选哪条，键与索引的收尾步骤一致：

```sql
-- 该表真实列清单（实测）：FBALANCEID、FBALANCENAME、FDETAILNUMBER、FDETAILNAME、
-- 各类期初/借贷/本年累计 decimal 度量列、SYNC_TIME、FACCTYEAR、FACCTPERIOD
-- 注意：FACCTYEAR / FACCTPERIOD 由 appendDerivedWriteFields 自动补写（engine.go window.go:199），
-- 不在表单 field_keys 里，容易被误认为"表无期间维度"。

-- 唯一键候选实测（聚合查询需要内存授予，须在任务 1 恢复后执行）
SELECT COUNT(*) AS total,
       COUNT(DISTINCT CONCAT(FBALANCEID,'|',ISNULL(FDETAILNUMBER,''),'|',FACCTYEAR,'|',FACCTPERIOD)) AS distinct_candidate
FROM dbo.gl_rpt_accountbalance;
```

收尾动作（口径确定后执行）：

1. 把 `primaryKeyMap["gl_rpt_accountbalance"]` 改成实测唯一的列组合（当前是错的 `FBALANCEID` 单列）；
2. 按该组合建唯一索引，走 §3.1 的 ONLINE 做法；建前清理历史重复与 6 行空串键；
3. 从 `internal/db/pk_contract_test.go` 的 `acceptedKeyDrift` 中删除该登记（契约测试会主动提示偏差已不存在）；
4. 若选路线 B，则第 2 步改为建**非唯一**索引，并在 `primaryKeyMap` 注释与 `CONTEXT.md` 标注
   "该表业务键仅用于 staging 聚簇顺序，不代表唯一性"，避免再次被当作 MERGE/孤儿判定依据。

**推荐**：路线 A。理由是它同时消除"增量抹除历史期间"这个已经发生的数据缺陷
（实测 2025 年期间行数为 0），而路线 B 只是把当前的丢期行为合法化。
键的唯一性验证依赖内存授予恢复，见 §4 前置条件。

## 4. 执行前置条件（不满足则不排期）

1. **目标库内存授予恢复常态**：当前 `RESOURCE_SEMAPHORE` 队列被报表作业长期占据（见事故报告）。
   `CREATE INDEX` 需要内存授予与 tempdb 空间，在饥饿状态下可能长时间等待或失败。
   先决条件：报表作业整改完成，`SELECT COUNT(*) FROM sys.dm_exec_requests WHERE wait_type LIKE 'RESOURCE_SEMAPHORE%'` 稳定为 0。
2. **tempdb 余量**：现有 tempdb 数据文件共约 1.1 GB；106k 行索引排序通常需要几十 MB 到数百 MB，执行前确认
   `SELECT name, size*8/1024 AS mb FROM tempdb.sys.database_files` 且磁盘剩余充足。
3. **同步暂停窗口**：变更期间停用 `default_incremental`（`PUT /api/v1/schedules/1 {"enabled":false}`），
   避免与同步写入争锁；完成后恢复。表规模小，ONLINE 建索引预期秒级到十几秒。
4. **不要在整点±10 分钟执行**（避开同步轮次与报表作业的 `:10/:40` 触发）。

## 5. 步骤与验证

| # | 动作 | 预期 |
|---|---|---|
| 1 | 停用增量任务 | `/schedules/status` → `enabled:false` |
| 2 | 复核 §3.1 的重复探测 SQL | 0 行 |
| 3 | `CREATE UNIQUE ... ONLINE = ON` | 成功；耗时记录 |
| 4 | 验证约束存在 | `SELECT name, is_unique FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.sal_returnstock')` |
| 5 | 恢复增量任务 | `PUT /api/v1/schedules/1 {"enabled":true}` → `enabled:true` |
| 6 | 观察一轮同步 | `success`，`销售退货单` 表单无新增失败 |
| 7 | 代码侧收尾 | 从 `acceptedKeyDrift` 删除 `sal_returnstock` 登记（契约测试会主动提示"偏差已不存在"），跑 `MSSQL_INTEGRATION=1 go test ./internal/db/ -run PrimaryKeyContract` |

失败处理：建索引失败或超时会话被取消 → SQL Server 自动回滚在线索引构建，表保持原状；
若索引已建但引发后续写入失败（例如历史脏数据在 MERGE 时撞唯一键）→ 立即 `DROP INDEX`（ONLINE）并回到 issue #3 讨论。

## 6. 风险与不做清单

- **不给 22 张表一律补索引**：A 类 6 张的代码键是唯一键超集，改动会削弱匹配；B 类需要先定口径。
- **不在生产直接 `ALTER TABLE ... ADD CONSTRAINT`**：唯一性未验证前先建索引而非约束，避免表级锁与回滚成本。
- **不动 `sal_outstock` / `sal_returnstock` 的字段语义**：本方案只加索引。
- 未决：`gl_rpt_accountbalance` 的真实粒度（路线 A/B 选择）、`stk_inventory` 是否继续覆盖 ERP 自有表（#4）。

## 7. 顺带发现的代码侧事实（已修）

上一版"写入前业务键重复校验"对快照替换路径也拒写，会让 `科目余额表` 立刻失败
（因其键本就允许重复）。已在 `ad2196a` 改为：**MERGE 路径拒写并给出键与样例，快照替换路径仅 WARN**。
这也是本方案 §3.2 判定的直接证据来源。
