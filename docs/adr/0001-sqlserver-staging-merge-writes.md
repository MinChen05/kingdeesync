# ADR-0001: 目标库统一为 SQL Server，采用 Staging + MERGE 写入

- **状态**：Accepted
- **日期**：2026-08-03（提交 `9488ead`）
- **相关**：`docs/adr/0004`、`docs/adr/0003`

## 背景

写入引擎原先面向 Doris（MySQL 协议 OLAP）。生产实际数据仓库为 SQL Server
（`10.10.10.191/Kingdee`），双写目标造成维护成本与文案漂移（前端多处仍写 Doris）。

## 决策

删除 `doris_writer.go`，新增 `sqlserver_writer.go`，业务数据只写入 SQL Server 主表：

- 每批数据先落 **staging 表**，再 `MERGE` 进目标表（内联聚集索引）。
- 规避 go-mssqldb 不支持 `?` 占位符的问题（改用 VALUES 文本 / `@pN` 参数）。
- 科目余额表增量同步限定最近 6 个月窗口（单次 14 分钟 → 4 分钟）。
- API 触发同步的超时从 30 分钟提高到 2 小时，与调度一致。

## 后果

- 正面：单一写入目标，链路简化；MERGE 天然幂等，重跑安全。
- 负面：孤儿删除、分区守卫等全部逻辑需按 SQL Server 方言重写；
  `inserted` 计数必须在 MERGE **前**统计（该缺陷由 `1631797` 修复，教训固化在
  `docs/adr/0003`）。
- 所有 "Doris" 措辞从前端与文档清除（`1f4b806`、`137190e`）。
