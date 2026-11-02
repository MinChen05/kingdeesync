/* ============================================================================
 * 变更单：为 dbo.sal_returnstock（销售退货单）建 FENTRYID 唯一索引
 * ----------------------------------------------------------------------------
 * 关联   : issue #6（本变更）、issue #3（22 表主键对账）、方案 §3.1
 * 环境   : 10.10.10.191 / 库 Kingdee / SQL Server 2022 Developer（支持 ONLINE）
 * 归属   : 表由本项目 DDL 建立（docs/sqlserver-tables-kingdee-sync.sql），非 ERP 原生表
 * 执行者 : DBA 在场；驱动者：同步系统侧
 * 预计   : 表 21 MB / 2,765 页，ONLINE 构建秒级到十几秒
 * 键宽   : FENTRYID NVARCHAR(64) NOT NULL → 索引键 128 字节，远低于 900 上限
 * 回滚   : 脚本末段 DROP INDEX，一条语句
 * ==========================================================================*/

/* ----------------------------------------------------------------------------
 * 阶段 0：前置门禁（任一不满足则本次不执行，不进入阶段 2）
 * --------------------------------------------------------------------------*/

/* 0.1 内存授予队列必须已恢复正常（见 issue #5；饥饿时建索引会排队甚至失败）
   期望：0 */
SELECT COUNT(*) AS grant_waiters
FROM sys.dm_exec_requests
WHERE wait_type LIKE 'RESOURCE_SEMAPHORE%';

/* 0.2 tempdb 余量确认（ONLINE 构建与排序需要临时空间）
   期望：每文件剩余 MB 合计远大于 512 MB */
SELECT name, size * 8 / 1024 AS size_mb
FROM tempdb.sys.database_files;

/* 0.3 重复键必须为 0 行（2026-11-02 23:26 实测为 0 组） */
SELECT FENTRYID, COUNT(*) AS duplicates
FROM dbo.sal_returnstock
GROUP BY FENTRYID
HAVING COUNT(*) > 1;

/* 0.4 NULL 键必须为 0（列声明本身是 NOT NULL，2026-11-02 实测 0） */
SELECT COUNT(*) AS null_keys
FROM dbo.sal_returnstock
WHERE FENTRYID IS NULL;

/* 0.5 现有索引基线（预期：仅一行 index_id=0 的堆） */
SELECT i.index_id, ISNULL(i.name, '(heap)') AS index_name, i.type_desc, i.is_unique
FROM sys.indexes i
WHERE i.object_id = OBJECT_ID('dbo.sal_returnstock');

/* ----------------------------------------------------------------------------
 * 阶段 1：变更窗口准备（同步侧动作，不是 SQL）
 * ----------------------------------------------------------------------------
 *   PUT /api/v1/schedules/1  body {"enabled": false}      -- 停用增量任务
 *   GET /api/v1/schedules/status                          -- 期望 {"enabled":false}
 *   GET /api/v1/sync/status                               -- 期望 404 no active sync run
 *   避开 :00 / :10 / :40（同步轮次与报表作业触发点）
 * -------------------------------------------------------------------------*/

/* ----------------------------------------------------------------------------
 * 阶段 2：主体变更
 * --------------------------------------------------------------------------*/

BEGIN TRY
    CREATE UNIQUE NONCLUSTERED INDEX UQ_sal_returnstock_FENTRYID
        ON dbo.sal_returnstock (FENTRYID)
        WITH (ONLINE = ON, DATA_COMPRESSION = NONE, SORT_IN_TEMPDB = ON);
END TRY
BEGIN CATCH
    /* 失败时索引不会被保留（在线构建失败自动回滚），仅报告错误供决策是否重试。
       不要在此处吞掉错误：DBA 需要看到原始报错。 */
    SELECT ERROR_NUMBER()  AS error_number,
           ERROR_SEVERITY() AS severity,
           ERROR_STATE()    AS state,
           ERROR_MESSAGE()  AS message;
END CATCH;

/* ----------------------------------------------------------------------------
 * 阶段 3：验证
 * --------------------------------------------------------------------------*/

/* 3.1 唯一索引存在且生效（期望：UQ_... 行 is_unique=1, is_disabled=0） */
SELECT i.name, i.is_unique, i.is_disabled, i.has_been_validated, i.type_desc
FROM sys.indexes i
WHERE i.object_id = OBJECT_ID('dbo.sal_returnstock');

/* 3.2 表未被改名/破坏：行数与变更前一致 */
SELECT COUNT(*) AS rows_now FROM dbo.sal_returnstock;

/* ----------------------------------------------------------------------------
 * 阶段 4：收尾（同步侧动作）
 * ----------------------------------------------------------------------------
 *   PUT /api/v1/schedules/1  body {"enabled": true}       -- 恢复增量任务
 *     → updateSchedule 内部会 ReloadJobs，/schedules/status 随即变 {"enabled":true}
 *   观察一轮同步：
 *     GET /api/v1/runs?limit=3
 *     期望该轮 status=success 且 销售退货单 表单不在 errors 中
 * -------------------------------------------------------------------------*/

/* ----------------------------------------------------------------------------
 * 阶段 5：代码侧登记回收（必须做，否则契约测试会反向报错）
 * ----------------------------------------------------------------------------
 *   1) 编辑 apps/server/internal/db/pk_contract_test.go，
 *      从 acceptedKeyDrift 中删除 "sal_returnstock" 这一行；
 *   2) 跑门控对账测试（只读）：
 *        MSSQL_INTEGRATION=1 go test ./internal/db/ -run PrimaryKeyContract -v
 *      期望：PASS，且日志中该表已按"一致"处理
 *   3) 在 issue #6 记录完成时间与索引元数据截图/结果
 * -------------------------------------------------------------------------*/

/* ----------------------------------------------------------------------------
 * 回滚（任一阶段异常或后续写入因约束失败时执行）
 * --------------------------------------------------------------------------*/

-- DROP INDEX IF EXISTS UQ_sal_returnstock_FENTRYID ON dbo.sal_returnstock;

/* ----------------------------------------------------------------------------
 * 后置观察（可选，一周内回看）
 * ----------------------------------------------------------------------------
 * 若出现 "Violation of UNIQUE KEY constraint / 8672" 类写入失败，说明源侧同一
 * FENTRYID 出现多行：这正是本索引想暴露的问题，应当回到 issue #3/#7 讨论键口径，
 * 而不是直接回滚索引了事。
 * -------------------------------------------------------------------------*/
