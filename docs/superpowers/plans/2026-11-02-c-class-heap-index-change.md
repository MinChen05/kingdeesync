# C 类堆表索引变更方案（gl_rpt_accountbalance / sal_returnstock）

- 状态：待评审（需 DBA 与业务口径确认）
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

### 3.2 `gl_rpt_accountbalance`：**不能建**，是键选错 ❌

`FBALANCEID` 的取值形如 `2202.02`、`6601.11`、`6401.01.01` —— 这是**会计科目编码**，不是余额记录主键。一行是"某科目某期间"的一条余额，同科目跨期重复出现完全正常（5,145 次即约 30 期 × 多个组织/币种维度）。

因此该表的真实粒度需要口径确认，先跑探查：

```sql
-- 列清单与形态
SELECT c.name, t.name AS type, c.max_length, c.is_nullable
FROM sys.columns c JOIN sys.types t ON t.user_type_id = c.user_type_id
WHERE c.object_id = OBJECT_ID('dbo.gl_rpt_accountbalance') ORDER BY c.column_id;

-- 候选复合键的唯一性试验（按需替换列名）
SELECT COUNT(*) AS total,
       COUNT(DISTINCT CONCAT(FBALANCEID,'|',FPERIOD,'|',FACCOUNTID)) AS distinct_candidate
FROM dbo.gl_rpt_accountbalance;
```

两条路线（需业务拍板，二选一）：

- **路线 A：修正映射**（若存在真实业务唯一键，例如科目+期间+维度组合）
  1. 把 `primaryKeyMap["gl_rpt_accountbalance"]` 改成实测唯一的列组合；
  2. 按该组合建唯一索引（同 §3.1 的 ONLINE 做法，先清理历史重复，含 6 行空串键）；
  3. 从 `pk_contract_test.go` 的 `acceptedKeyDrift` 中删除该登记。
- **路线 B：承认"无业务唯一键，仅整表快照"**
  1. 明确该表只走 ADR-0007 的快照替换（当前已是），不参与按匹配的 MERGE；
  2. 为查询性能建**非唯一**索引（如 `FBALANCEID`、`(FBALANCEID, 期间列)`），不加唯一约束；
  3. 在 `primaryKeyMap` 注释与 `CONTEXT.md` 中标注"该表业务键仅用于 staging 聚簇顺序，不代表唯一性"，避免再次被误用为 MERGE/孤儿判定依据。

**推荐先做路线 B 的第 2、3 步**（零风险、消除误用），路线 A 等口径明确后再做。

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
