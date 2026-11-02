# 路线 A 实现设计：科目余额表按期间作用域替换

- 关联：issue #7（本设计）、#5（内存授予，前置）、#3（主键契约）、ADR-0007（快照原子替换）
- 作者：同步系统侧；状态：待评审
- 实测依据（2026-11-02 23:49，只读）：表内仅 2026 年 5–10 期共 38,788 行，2025 年 0 行，
  期间组合 6 个，`SYNC_TIME` 单批；键列实际最大字符长度 `FBALANCEID=10`、`FDETAILNUMBER=46`、
  `FACCTYEAR=4`、`FACCTPERIOD=2`；`NULL` 年/期行数 0

## 1. 目标

消除"模式决定表内容"：增量轮（6 期窗口）不得再抹掉窗口外的历史期间；全量轮照常覆盖其窗口。
顺带把该表的业务键从错误的 `FBALANCEID`（科目编码）修正为真实唯一组合。

## 2. 核心改法：staging 驱动的作用域删除

复用 ADR-0007 已有的 staging 装载，只把事务内的 `TRUNCATE` 换成"按本批期间 JOIN 删除"：

```
staging 装载（事务外，不变）
BEGIN TRAN
  -- scopeCols 非空时（科目余额表）
  DELETE t FROM dbo.gl_rpt_accountbalance AS t
    JOIN dbo.<staging> AS s
      ON t.[FACCTYEAR] = s.[FACCTYEAR] AND t.[FACCTPERIOD] = s.[FACCTPERIOD]
  INSERT INTO dbo.gl_rpt_accountbalance (cols…) SELECT cols… FROM dbo.<staging>
  -- 行数核对（staged vs affected）后
COMMIT
```

`scopeCols` 为空时（即时库存）保持 `TRUNCATE` 语义不变。

选 JOIN 删除而不是 `WHERE (year,period) IN (值对)` 的原因：SQL Server 不支持行值元组 `IN`，
而 JOIN 复用已装载好的 staging，无需枚举值、无长度限制、无参数膨胀（原因：避免第二个实现分支）。

## 3. 接口与代码落点

| 位置 | 改动 |
|---|---|
| `engine.go` `isSnapshotForm` | 扩展为单一事实点 `snapshotSpec(formName) (scopeCols []string)`：`科目余额表 → {FACCTYEAR, FACCTPERIOD}`、`即时库存 → nil`（原因：现在快照语义分散在 `isSnapshotForm` 与聚合白名单两处，再加作用域必须有唯一出处） |
| `writer.go` `SnapshotReplacer` | 追加作用域参数：`ReplaceSnapshot(ctx, tableName, rows, cols, pkCols, fieldMap, scopeCols []string)`（原因：只有一种实现、无兼容负担，加参数比新增第二个接口更清楚） |
| `sqlserver_writer.go` `ReplaceSnapshot` | 事务内按 `scopeCols` 二选一执行 `DELETE…JOIN` 或 `TRUNCATE`；其余（staging 装载、行数核对、回滚、清理）不变 |
| `engine.go` `writeRowsWithMode` | 把 `scopeCols` 透传给 replacer；键校验复用现有 `FindDuplicateBusinessKeys` |
| `db/database.go` `primaryKeyMap` | `gl_rpt_accountbalance: "FBALANCEID"` → `"FBALANCEID,FDETAILNUMBER,FACCTYEAR,FACCTPERIOD"` |
| `db/pk_contract_test.go` | 该表从 `acceptedKeyDrift` 的 C 类登记改为"待建索引"注记（索引落地后删除登记） |

## 4. 必须有的护栏（每条都对应一次已发生的事故类型）

1. **`scopeCols` 必须全部出现在写列 `cols` 中**，否则直接拒绝执行。
   （原因：静默退化成整表删除就是本 bug 的成因，绝不能靠"应该有"）
2. **scope 列值不得为 NULL/空串**：`DELETE…JOIN` 对 NULL 不相等 → 删不掉旧行会留下重复。
   实测当前为 0，但必须由代码拒绝而不是假设（原因：`科目余额表` 的年/期由 `appendDerivedWriteFields` 注入，注入失败就是 NULL）。
3. **空批次不写**（沿用现有 `len(rows)==0` 拒绝）。
4. **失败整体回滚**（沿用 ADR-0007）；作用域删除同样满足"要么全成要么全不动"。
5. **删除行数不作相等要求**：目标表在窗口外的行必须存活，因此只做
   `staged == inserted` 核对，不核对 deleted（原因：deleted 与目标表历史状态有关，强行相等会误杀）。

## 5. 唯一索引的宽度障碍（必须先解决，否则 §7 的索引建不出来）

`docs/sqlserver-tables-kingdee-sync.sql` 声明的是
`FBALANCEID NVARCHAR(255)`、`FDETAILNUMBER NVARCHAR(255)`、`FACCTYEAR/FACCTPERIOD NVARCHAR(10)`，
四列合计 **1060 字节 > SQL Server 非聚集索引键 900 字节上限** → `CREATE UNIQUE INDEX` 会直接失败。
实测实际长度只有 10 / 46 / 4 / 2 字符。

两个方案：

- **A1（推荐）收窄列宽**：`FBALANCEID`、`FDETAILNUMBER` 改为 `NVARCHAR(120)`（对实测 10/46 有 2 倍余量），
  键宽变为 `120*2 + 120*2 + 10*2 + 10*2 = 500` 字节 < 900。
  理由：这些表由本项目 DDL 建立（非 ERP 原生表），列宽是我们自己的选择；收窄后索引键直白可读，
  超长数据会**写入报错**而不是被静默截断，失败模式明确。
- A2 备选：加持久化计算列 `BKEY_HASH AS CONVERT(varchar(64), HASHBYTES('SHA2_256', CONCAT(...)), 2) PERSISTED`
  并在其上建唯一索引。理由：不改动既有列宽；代价是多一个人造列，报表与排障要多解释一层。

`ALTER COLUMN` 前置检查：`LEN()` 分布已实测（10/46），无截断风险；表为堆表无索引，
变更只需重写 21 MB 级数据，秒级。

## 6. 测试计划

| 层级 | 内容 |
|---|---|
| 纯函数单测 | `snapshotSpec` 两个分支；scope 列缺失 / NULL 值 → 拒绝（含错误信息断言） |
| 门控集成测试（`MSSQL_INTEGRATION=1`，真实库临时表） | ①预置 2 个期间，写入只含 1 个期间的批次 → 断言窗口外期间旧行**保留**、本期间被整体替换；②`scopeCols=nil` 时仍为整表替换（`即时库存` 回归）；③中途失败（CHECK 约束）→ 两个期间的数据都保持原状；④scope 值含 NULL → 拒绝且表未改动；⑤无 `stg_*` 残留 |
| 契约测试 | 改键后 `MSSQL_INTEGRATION=1 go test ./internal/db -run PrimaryKeyContract` 通过（登记同步更新） |
| 生产验证 | 见 §8 回填步骤 |

## 7. 数据库侧配套变更（与代码解耦，另走变更窗口）

```sql
-- 前置（必须在 #5 内存授予恢复后执行，聚合查询当前会超时）
SELECT COUNT(*) AS total,
       COUNT(DISTINCT CONCAT(FBALANCEID,'|',ISNULL(FDETAILNUMBER,''),'|',FACCTYEAR,'|',FACCTPERIOD)) AS distinct_key
FROM dbo.gl_rpt_accountbalance;   -- 期望 total = distinct_key，否则先清理再建

-- 收窄列宽（A1）
ALTER TABLE dbo.gl_rpt_accountbalance ALTER COLUMN [FBALANCEID]   NVARCHAR(120) NULL;
ALTER TABLE dbo.gl_rpt_accountbalance ALTER COLUMN [FDETAILNUMBER] NVARCHAR(120) NULL;

-- 唯一索引（键宽 500 字节 < 900）
CREATE UNIQUE NONCLUSTERED INDEX UQ_gl_rpt_accountbalance_key
    ON dbo.gl_rpt_accountbalance (FACCTYEAR, FACCTPERIOD, FBALANCEID, FDETAILNUMBER)
    WITH (ONLINE = ON);

-- 作用域删除所需（同一索引的前缀已可服务 DELETE…JOIN，无需额外索引）
```

回滚：`DROP INDEX IF EXISTS UQ_gl_rpt_accountbalance_key ON dbo.gl_rpt_accountbalance;`
（列宽可回退为 `NVARCHAR(255)`，扩宽无数据风险）。

## 8. 上线与回填步骤（顺序不可颠倒）

1. 代码合入 + 部署（`scopeCols` 生效）；
2. 手工触发一次全量以找回历史期间：
   `POST /api/v1/runs {"forms":["科目余额表"],"sync_type":"full"}`
   —— 必须在 §7 建索引**之后**做，否则全量写入撞上重复键会整表单失败；
3. 验证：`FACCTYEAR='2025'` 行数 > 0；
4. 等一轮增量（或手工增量）后再验证：2025 年行数**不再归零** → 路线 A 达成；
5. 更新 `CONTEXT.md` 快照表单定义（"整表替换"→"按声明的作用域替换，无作用域列时整表替换"）与 ADR-0007 落地清单。

## 9. 已知残留缺口（明确接受或另行排期）

若某期间在源侧彻底不再返回记录，作用域删除不会覆盖它，目标表会永久残留该期间旧行。
低频对账可发现（比较目标表期间集合与源期间集合），或显式接受（期间不会凭空消失）。
不建议用"整表删除窗口外期间"来解决——那正是本 bug。

## 10. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 键组合实测唯一性尚未验证（聚合超时） | §7 前置检查作为硬门禁；不通过则不建索引，只上作用域删除（作用域删除本身不依赖唯一索引） |
| 改键影响其他读点 | 已逐点核对 `db.GetPrimaryKey` 在引擎内只有 3 处使用：`engine.go:1668`（游标路径，`!isSnapshotForm` 已排除快照表单）、`engine.go:1982`（`writeRowsWithMode`：staging 聚簇索引 + 重复键校验）、`engine.go:2128`（`deleteOrphanedWithSnapshot`，**全仓无调用点**）。另 `ReconcileOrphans` 也只被其集成测试调用。因此对本表而言改键只影响 staging 索引与校验，不触碰孤儿判定 |
| 与报表读争锁 | 作用域删除把锁范围从整表缩到 6/22 期间，实际是改善 |
| 上线窗口叠加 #5 未解决 | 步骤 1 只做代码；步骤 2/3/4 等 #5 关闭后执行 |

## 11. 顺带发现（需要单独确认，不在本设计内处理）

孤儿删除的两套实现**都没有生产调用点**：`deleteOrphanedWithSnapshot`（engine.go:2112）全仓无人调用，
`ReconcileOrphans`（orphan_reconcile.go）只被其集成测试调用。
这意味着"全量同步删除源侧已不存在的记录"这件事可能根本没有在主链路生效——
`CONTEXT.md` 与 ADR-0003 描述的孤儿治理能力与现实实现不一致。需要单独立项确认：
是曾经接线后被摘除，还是从未接上。

## 12. 落地清单（实现顺序）

- [x] `snapshotSpec` + `ReplaceSnapshot` 作用域参数与 `DELETE…JOIN` 实现
- [x] 护栏：scope 列缺失 / NULL 值拒绝执行（含单测）
- [x] 门控集成测试**已在真实实例通过**（2026-11-03 00:18，暂停调度后执行，101s）：跨期间保留、
      scope 为空退化为整表、失败回滚、NULL 作用域无副作用、无 `stg_*` 残留；跑后只读复核 `stg_*=0 snap_sc_*=0`
- [ ] **`primaryKeyMap` 改四列**——必须与 §7 的列宽收窄**同一个发布窗口**落地，不得先行：
      `createStagingTable` 会在 pkCols 上建 CLUSTERED 索引，四列 `NVARCHAR(255)` 键宽 ≈ 2040 字节，
      超过 900 上限会让 staging 建表直接失败，进而使整轮写入失败（原因：收窄后 500 字节才安全）
- [ ] `acceptedKeyDrift` 注记更新 + 契约测试重跑（随上一项一起做）
- [x] `CONTEXT.md` 快照定义与 ADR-0007 落地清单更新
- [ ] §7 数据库变更（列宽收窄 + 唯一索引，走 DBA 窗口，依赖 #5）
- [ ] §8 全量回填与两轮验证
