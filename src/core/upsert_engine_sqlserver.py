"""SQL Server upsert engine extracted from MySQLManager batch insert logic."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any, List

from src.core.dedup_strategy import DeduplicationStrategy
from src.core.performance_logging import log_write_metrics
from src.core.type_converter import TypeConverter

if TYPE_CHECKING:
    from src.core.mysql_manager import MySQLManager


class UpsertEngineSqlServer:
    """Encapsulates SQL Server-specific batch upsert behavior."""

    _ENG_BOMCHILD_STAGING_COLUMNS = [
        "FID",
        "FENTRYID",
        "FSEQ",
        "FMATERIALID",
        "FCHILDNUMBER",
        "FCHILDNAME",
        "FNUMERATOR",
        "FDENOMINATOR",
        "FISSUETYPE",
        "FBACKFLUSHTYPE",
        "FSUPPLYORG",
        "FSTOCKID",
        "FENTRYROWID",
        "FREPLACEGROUP",
        "FQTY",
        "FACTUALQTY",
        "FMASTERID",
        "FMATERIALTYPE",
        "FMODIFYDATE",
    ]

    def __init__(self, manager: MySQLManager, *, logger: logging.Logger | None = None) -> None:
        self.manager = manager
        self.logger = logger or logging.getLogger(__name__)
        self.type_converter = TypeConverter(manager.cursor)
        self.dedup_strategy = DeduplicationStrategy(manager)

    def _is_driver18(self, manager: MySQLManager) -> bool:
        drv = getattr(manager, "config", {}).get("driver", "ODBC Driver 17 for SQL Server")
        return "ODBC Driver 18" in str(drv)

    def _normalize_column_name(self, column: Any) -> str:
        return str(column).strip().upper()

    def execute(
        self,
        sql: str,
        values: list[list[Any]],
        batch_size: int,
        commit_every_n_batches: int,
    ) -> int:
        manager = self.manager
        logger = self.logger
        total_inserted = 0
        is_d18 = self._is_driver18(manager)
        # SQL Server 路径：将 MySQL 的 INSERT ... ON DUPLICATE 语句转为 MERGE
        if getattr(manager, "db_type", "mysql") == "sqlserver":
            table, columns = manager._parse_insert_sql(sql)
            if not table or not columns:
                logger.error("无法解析插入语句以生成 MERGE 语法")
                return 0
            base_name = str(table).split(".")[-1].replace("[", "").replace("]", "").strip().lower()
            # 兼容目标表缺失列：动态过滤不存在的列与对应值，避免列名无效错误
            try:
                existing_cols = set(manager._get_table_columns_info(table).keys())
                # 计算需要保留的列索引（按解析出来的列顺序）
                keep_indices = [idx for idx, col in enumerate(columns) if col and col.upper() in existing_cols]
                missing_cols = [col for col in columns if col and col.upper() not in existing_cols]
                if missing_cols:
                    logger.warning(f"[{table}] 目标库缺失列，已自动忽略: {missing_cols}")
                    # 过滤列集合并同步过滤 values
                    columns = [columns[i] for i in keep_indices]
                    try:
                        values = [[row[i] for i in keep_indices] for row in values]
                    except Exception as e:
                        logger.error(f"过滤缺失列时重建参数失败: {e}")
                        return 0
            except Exception as e:
                logger.warning(f"读取 {table} 列信息失败，可能无法自动忽略缺失列: {e}")

            # 双重保险：确保 values 长度与 columns 一致
            if values and len(values) > 0:
                try:
                    row0 = values[0]
                    if len(row0) > len(columns):
                        logger.warning(
                            f"[{table}] 数据字段数({len(row0)}) > SQL列数({len(columns)})，自动截断多余字段"
                        )
                        values = [row[: len(columns)] for row in values]
                except Exception as e:
                    logger.warning(f"[{table}] 数据对齐检查失败: {e}")

            # 过滤必填字段为空的行
            required_map = {
                "sal_deliverynotice": ["FID", "FENTRYID"],
                "prd_instock": ["FID", "FENTRYID"],
                "ap_payable": ["FID", "FENTRYID"],
            }
            required_cols = required_map.get(base_name)
            if required_cols:
                values = self.dedup_strategy.filter_required_fields(values, columns, required_cols, table)

            is_inventory_table = str(table).strip().lower() == "stk_inventory"
            # 即时库存：为了提升速度，使用较大批次并由临时表一次性提交
            if is_inventory_table:
                try:
                    batch_size = int(manager.config.get("batch_size", "50000"))
                except Exception:
                    batch_size = 50000
                commit_every_n_batches = 0

            # AP_Payable 表使用固定20000批次
            if str(table).strip().lower() == "ap_payable":
                batch_size = 20000

            pk = manager._get_primary_key(table) or columns[0]

            # 特殊处理：BD_MATERIAL 使用唯一索引列作为合并键，解决 Error 2601 唯一索引冲突
            # try:
            #     if str(table).strip().lower() == 'bd_material':
            #         pk = "FMASTERID,FMATERIALGROUP,FUSEORGID,FNUMBER"
            # except Exception:
            #     pass

            source_dedup_enabled = str(manager.config.get("source_dedup_enabled", "true")).strip().lower() == "true"
            # 支持复合主键排除
            pk_col_set = {c.strip().upper() for c in pk.split(",")}
            non_pk_cols = [c for c in columns if c.strip().upper() not in pk_col_set]

            # 通用去重：按主键列对源数据进行去重，避免 MERGE 8672（同一目标行被多次匹配）
            values = self.dedup_strategy.deduplicate_by_primary_key(values, columns, table, source_dedup_enabled)
            # 如目标表包含 SYNC_TIME，则在 UPDATE/INSERT 中写入当前时间
            has_sync_time = manager._table_has_column(table, "SYNC_TIME")
            # 标识列(IDENTITY)不可更新/插入：在普通 MERGE 路径也进行过滤
            identity_col = None
            try:
                identity_col = manager._get_identity_columns(table)
            except Exception:
                identity_col = None
            if identity_col:
                non_pk_cols = [c for c in non_pk_cols if c.strip().upper() != identity_col.strip().upper()]
            # 避免将 NULL 写入目标非空列：当源值为 NULL 时保留原值
            update_set_parts = [f"t.{c} = COALESCE(s.{c}, t.{c})" for c in non_pk_cols]
            if has_sync_time and all(str(c).strip().upper() != "SYNC_TIME" for c in columns):
                update_set_parts.append("t.SYNC_TIME = GETDATE()")
            update_clause = (
                ("WHEN MATCHED THEN UPDATE SET " + ", ".join(update_set_parts)) if update_set_parts else ""
            )
            insert_cols = columns[:]
            insert_vals = [f"s.{c}" for c in columns]
            if identity_col:
                # INSERT 时也避开标识列，交由 SQL Server 自动生成，避免 544/8102 错误
                insert_pairs = [
                    (c, v)
                    for c, v in zip(insert_cols, insert_vals)
                    if c.strip().upper() != identity_col.strip().upper()
                ]
                if insert_pairs:
                    insert_cols = [pair[0] for pair in insert_pairs]
                    insert_vals = [pair[1] for pair in insert_pairs]
            if has_sync_time and all(str(c).strip().upper() != "SYNC_TIME" for c in columns):
                insert_cols.append("SYNC_TIME")
                insert_vals.append("GETDATE()")
            # 支持复合主键（使用之前确定的 pk 变量，其中已包含 bd_material 的特殊覆盖）
            pk_raw = pk
            pk_cols = (
                [c.strip() for c in pk_raw.split(",")] if isinstance(pk_raw, str) and ("," in pk_raw) else [pk_raw]
            )
            on_clause = " AND ".join([f"t.{c} = s.{c}" for c in pk_cols])
            source_sql = f"USING (VALUES ({', '.join(['?' for _ in columns])})) AS s({', '.join(columns)}) "
            # 对所有表启用类型安全转换：将非数值字符串（如 'C'）安全转换为数值，避免 8114 错误
            col_type_map = self.type_converter.get_column_type_map(base_name)
            source_parts = self.type_converter.build_source_conversion_parts(columns, col_type_map)
            source_sql = f"USING (SELECT {', '.join(source_parts)}) AS s({', '.join(columns)}) "
            merge_sql = (
                f"MERGE INTO {table} AS t "
                + source_sql
                + f"ON {on_clause} "
                + (update_clause)
                + f" WHEN NOT MATCHED THEN INSERT ({', '.join(insert_cols)}) VALUES ({', '.join(insert_vals)});"
            )
            # 对 bd_material 的 FMATERIALID 去重，避免重复记录导致 MERGE/INSERT 冲突
            if str(table).strip().lower() == "bd_material" and source_dedup_enabled:
                values = self.dedup_strategy.deduplicate_by_column(values, columns, "FMATERIALID", table)
            values_len = len(values) if isinstance(values, list) else 0
            insert_threads = 1
            try:
                insert_threads = int(manager.config.get("insert_threads", "1"))
            except Exception:
                insert_threads = 1
            if insert_threads < 1:
                insert_threads = 1
            if insert_threads > 8:
                insert_threads = 8
            use_staging = False
            try:
                use_staging = str(manager.config.get("use_staging", "false")).strip().lower() == "true"
            except Exception:
                use_staging = False
            try:
                if values_len <= 2000:
                    insert_threads = 1
                    use_staging = False
                    try:
                        batch_size = min(batch_size, 2000)
                    except Exception:
                        pass
                    try:
                        commit_every_n_batches = 0
                    except Exception:
                        pass
                elif values_len <= 50000:
                    try:
                        insert_threads = min(max(insert_threads, 1), 2)
                    except Exception:
                        insert_threads = 1
                    try:
                        batch_size = max(batch_size, 5000)
                    except Exception:
                        pass
                    try:
                        commit_every_n_batches = 2
                    except Exception:
                        pass
                else:
                    # 大数据量（>50000）默认启用 staging 以提升性能，
                    # 但尊重全局 use_staging 配置：用户明确禁用时不再强制启用
                    use_staging = str(manager.config.get("use_staging", "true")).strip().lower() == "true"
                    insert_threads = 1
            except Exception:
                pass
            # 全局强制并发：若启用，则统一关闭 staging（即使部分表默认会强制开启）
            force_threads_all = False
            try:
                force_threads_all = str(manager.config.get("force_threads_all", "false")).strip().lower() == "true"
            except Exception:
                force_threads_all = False
            if force_threads_all and insert_threads > 1:
                use_staging = False

            # 检查 force_staging_tables 配置，强制启用 staging 模式（优先级高于默认策略，但低于 force_threads_all）
            try:
                force_tables_str = str(manager.config.get("force_staging_tables", "")).strip().lower()
                if force_tables_str:
                    force_tables = [
                        t.strip().replace("'", "").replace('"', "") for t in force_tables_str.split(",")
                    ]
                    current_table_base = str(table).split(".")[-1].replace("[", "").replace("]", "").strip().lower()
                    if (current_table_base in force_tables) and (not force_threads_all):
                        use_staging = True
                        insert_threads = 1  # 强制单线程，防止 staging 失败后回退到并发路径导致死锁
                        logger.info(f"表 {table} 在 force_staging_tables 列表中，强制启用 staging 模式（单线程）")
            except Exception as e:
                logger.warning(f"解析 force_staging_tables 配置失败: {e}")

            # 对关键表强制启用临时表（即使 force_threads_all 为 true）
            try:
                current_table_base = str(table).split(".")[-1].replace("[", "").replace("]", "").strip().lower()
                always_stage_tables: set = set()  # 空集：禁用硬编码强制 staging，通过配置控制
                force_subreq_staging = False
                force_subreq_staging = (
                    str(manager.config.get("force_subreq_staging", "false")).strip().lower() == "true"
                )
                if (current_table_base in always_stage_tables) or (
                    current_table_base == "sub_subreqorder" and force_subreq_staging
                ):
                    use_staging = True
                    insert_threads = 1
                    logger.info(f"表 {table} 强制启用 staging 模式（单线程）")
            except Exception:
                pass
            # 销售订单：默认通过 use_staging 配置控制，不再硬编码启用
            # 采购订单：默认通过 use_staging 配置控制
            # 即时库存：默认通过 use_staging 配置控制
            try:
                if (
                    (str(table).strip().lower() == "pur_purchaseorder")
                    and (not force_threads_all)
                    and values_len > 50000
                ):
                    pass  # 不再强制启用 staging，通过 use_staging 配置统一控制
            except Exception:
                pass
            # 即时库存：默认通过 use_staging 配置控制，不再强制启用
            if is_inventory_table and (not force_threads_all):
                pass  # staging 由 use_staging 配置统一控制
            try:
                if current_table_base == "sub_subreqorder":
                    allow_subreq_threads = True
                    try:
                        allow_subreq_threads = (
                            str(manager.config.get("allow_threads_sub_subreqorder", "false")).strip().lower() == "true"
                        )
                    except Exception:
                        allow_subreq_threads = False
                    if allow_subreq_threads:
                        use_staging = False
                        logger.info(f"表 {table} 已启用多线程模式，线程数: {insert_threads}")
            except Exception:
                pass
            try:
                # 临时表极速模式（单连接单事务，适合超大批次）
                if use_staging:
                    try:
                        if hasattr(manager.connection, "autocommit"):
                            manager.connection.autocommit = False
                        # 为提升插入速度，开启 fast_executemany；ODBC Driver 18 禁用以避免崩溃
                        if hasattr(manager.cursor, "fast_executemany"):
                            manager.cursor.fast_executemany = not is_d18
                        # 生成安全的临时表名（去掉架构/括号/特殊字符），避免 dbo.TableName 带点导致失败
                        base_name = table.split(".")[-1].replace("[", "").replace("]", "")
                        safe_name = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in base_name)
                        # 为避免驱动在预编译语句中无法识别临时表（#/##），改用会话唯一的物理阶段表（dbo.__stage_*），同步完成后删除
                        suffix = hex(int(time.time() * 1000) & 0xFFFF)[2:]
                        stage_table = f"[dbo].[__stage_{safe_name}_{suffix}]"
                        stage_ref = stage_table
                        logger.info(f"[STAGE] 启用阶段表极速模式：目标表 {table}，阶段表 {stage_table}")
                        # 创建阶段表，复制目标列结构（分两步执行以提高兼容性）
                        drop_stage_sql = f"IF OBJECT_ID(N'dbo.__stage_{safe_name}_{suffix}', N'U') IS NOT NULL DROP TABLE {stage_table};"
                        create_stage_sql = f"SELECT TOP 0 * INTO {stage_table} FROM {table};"
                        try:
                            manager.cursor.execute(drop_stage_sql)
                        except Exception:
                            # 即使不存在也忽略
                            pass
                        manager.cursor.execute(create_stage_sql)
                        # 显式验证阶段表已创建，避免后续加载时报“对象名无效”
                        try:
                            manager.cursor.execute(f"SELECT OBJECT_ID(N'dbo.__stage_{safe_name}_{suffix}', N'U')")
                            objid = manager.cursor.fetchone()
                            if not objid or objid[0] is None:
                                raise Exception(f"阶段表创建失败: dbo.__stage_{safe_name}_{suffix}")
                            # 重要：立即提交阶段表的创建，避免在后续连接抖动或事务回滚时导致对象丢失（触发 208 无效对象）
                            try:
                                manager.connection.commit()
                                logger.debug(f"[STAGE] 阶段表创建已提交: {stage_table}")
                            except Exception as c_err:
                                logger.warning(f"[STAGE] 阶段表创建提交失败，后续可能出现对象不可见: {c_err}")
                        except Exception as v_err:
                            logger.error(f"[STAGE] 阶段表验证失败: {v_err}")
                            raise
                        if base_name.strip().lower() == "prd_instock":
                            try:
                                manager.cursor.execute(
                                    """
                                    SELECT COLUMN_NAME, DATA_TYPE, NUMERIC_PRECISION, NUMERIC_SCALE
                                    FROM INFORMATION_SCHEMA.COLUMNS
                                    WHERE TABLE_NAME = ? AND COLUMN_NAME IN ('FID','FENTRYID')
                                    """,
                                    (base_name,),
                                )
                                col_rows = manager.cursor.fetchall() or []
                                for r in col_rows:
                                    if isinstance(r, dict):
                                        col_name = r.get("COLUMN_NAME")
                                        data_type = r.get("DATA_TYPE")
                                        prec = r.get("NUMERIC_PRECISION")
                                        scale = r.get("NUMERIC_SCALE")
                                    else:
                                        col_name = r[0] if len(r) > 0 else None
                                        data_type = r[1] if len(r) > 1 else None
                                        prec = r[2] if len(r) > 2 else None
                                        scale = r[3] if len(r) > 3 else None
                                    if not col_name:
                                        continue
                                    dtype = str(data_type).lower() if data_type is not None else ""
                                    if dtype in ("decimal", "numeric") and prec is not None and scale is not None:
                                        type_sql = f"{dtype.upper()}({int(prec)},{int(scale)})"
                                    elif dtype:
                                        type_sql = dtype.upper()
                                    else:
                                        type_sql = "INT"
                                    manager.cursor.execute(
                                        f"ALTER TABLE {stage_ref} ALTER COLUMN {col_name} {type_sql} NULL"
                                    )
                            except Exception:
                                pass
                        # 阶段表创建已提交后，启用 fast_executemany 加速批量插入；
                        # 若后续批次遇到驱动兼容问题，下面的异常分支会自动重建/降级处理
                        try:
                            # 对于 eng_bomchild 等表，fast_executemany 可能会导致 8114 (varchar to numeric) 转换错误
                            # 因此针对该表显式禁用 fast_executemany，以兼容模式插入
                            if base_name.strip().lower() in ("eng_bomchild", "prd_ppbomentry", "sub_subreqorder"):
                                manager.cursor.fast_executemany = False
                                logger.debug(
                                    f"[STAGE] 针对表 {base_name} 禁用 fast_executemany 以避免驱动类型转换错误"
                                )
                            elif hasattr(manager.cursor, "fast_executemany"):
                                manager.cursor.fast_executemany = not is_d18
                                logger.debug("[STAGE] fast_executemany=%s (ODBC Driver 18 compat)", not is_d18)
                        except Exception:
                            pass
                        identity_insert_enabled = False
                        # 将数据加载到临时表
                        identity_col = None
                        try:
                            identity_col = manager._get_identity_columns(table)
                        except Exception:
                            identity_col = None

                        select_parts = None
                        if is_inventory_table:
                            # 即时库存：根据列集合动态构造阶段插入语句，并为每列显式 TRY_CAST 保证类型安全
                            # 使用解析后的 columns 顺序，确保与 values 对齐
                            cast_map = {
                                "FID": "TRY_CAST(? AS VARCHAR(36))",
                                "FSTOCKORGID": "TRY_CAST(? AS INT)",
                                "FSTOCKID": "TRY_CAST(? AS INT)",
                                "FSTOCKLOCID": "TRY_CAST(? AS INT)",
                                "FSTOCKSTATUSID": "TRY_CAST(? AS INT)",
                                "FBASEUNITID": "TRY_CAST(? AS INT)",
                                "FBASEQTY": "TRY_CAST(? AS DECIMAL(23,10))",
                                "FMATERIALID": "TRY_CAST(? AS INT)",
                                "FMODIFYDATE": "TRY_CAST(? AS DATETIME)",
                            }
                            select_parts = []
                            for c in columns:
                                c_up = str(c).strip().upper()
                                select_parts.append(cast_map.get(c_up, "?"))
                            insert_stage_sql = (
                                f"INSERT INTO {stage_ref} ({', '.join(columns)}) SELECT {', '.join(select_parts)}"
                            )
                            stage_insert_cols = columns[:]
                        else:
                            # 针对部分表（如 prd_ppbomentry）显式进行 TRY_CAST，避免 varchar→numeric 报错
                            if base_name.strip().lower() == "prd_ppbomentry" or base_name.strip().lower() == "sub_subreqorder":
                                col_type_map = manager._get_table_columns_info(base_name)
                                int_types = {"int", "bigint", "smallint", "tinyint"}
                                dec_types = {"numeric", "decimal", "float", "real", "money", "smallmoney"}
                                dt_types = {"datetime", "datetime2", "smalldatetime", "date", "time"}
                                select_parts = []
                                for c in columns:
                                    c_up = str(c).strip().upper()
                                    dtype = col_type_map.get(c_up, "")
                                    if dtype in int_types:
                                        select_parts.append(
                                            "COALESCE(TRY_CONVERT(BIGINT, CONVERT(NVARCHAR(64), ?)), 0)"
                                        )
                                    elif dtype in dec_types:
                                        select_parts.append(
                                            "COALESCE(TRY_CONVERT(DECIMAL(23,10), CONVERT(NVARCHAR(64), ?)), 0)"
                                        )
                                    elif dtype in dt_types:
                                        select_parts.append("TRY_CONVERT(DATETIME, ?)")
                                    else:
                                        select_parts.append("TRY_CONVERT(NVARCHAR(255), ?)")
                                insert_stage_sql = (
                                    f"INSERT INTO {stage_ref} ({', '.join(columns)}) "
                                    f"SELECT {', '.join(select_parts)}"
                                )
                            elif base_name.strip().lower() == "eng_bomchild":
                                # 针对 eng_bomchild 显式构建 TRY_CAST，防止 8114 (varchar to numeric) 错误
                                # 字段: FID, FENTRYID, FSEQ, FMATERIALID, FCHILDNUMBER, FCHILDNAME, FNUMERATOR, FDENOMINATOR, FISSUETYPE, FBACKFLUSHTYPE,
                                #       FSUPPLYORG, FSTOCKID, FENTRYROWID, FREPLACEGROUP, FQTY, FACTUALQTY, FMASTERID, FMATERIALTYPE, FMODIFYDATE
                                expected_columns = [
                                    self._normalize_column_name(column)
                                    for column in self._ENG_BOMCHILD_STAGING_COLUMNS
                                ]
                                actual_columns = [self._normalize_column_name(column) for column in columns]
                                if actual_columns != expected_columns:
                                    raise ValueError(
                                        "eng_bomchild staging column order mismatch: "
                                        f"expected {self._ENG_BOMCHILD_STAGING_COLUMNS}, got {columns}"
                                    )
                                insert_stage_sql = (
                                    f"INSERT INTO {stage_ref} (FID, FENTRYID, FSEQ, FMATERIALID, FCHILDNUMBER, FCHILDNAME, FNUMERATOR, FDENOMINATOR, FISSUETYPE, FBACKFLUSHTYPE, "
                                    f"FSUPPLYORG, FSTOCKID, FENTRYROWID, FREPLACEGROUP, FQTY, FACTUALQTY, FMASTERID, FMATERIALTYPE, FMODIFYDATE) "
                                    f"SELECT "
                                    f"TRY_CAST(? AS INT), "  # FID
                                    f"TRY_CAST(? AS INT), "  # FENTRYID
                                    f"TRY_CAST(? AS INT), "  # FSEQ
                                    f"TRY_CAST(? AS NVARCHAR(64)), "  # FMATERIALID
                                    f"TRY_CAST(? AS NVARCHAR(255)), "  # FCHILDNUMBER
                                    f"TRY_CAST(? AS NVARCHAR(255)), "  # FCHILDNAME
                                    f"COALESCE(TRY_CAST(? AS DECIMAL(23,10)), 0), "  # FNUMERATOR
                                    f"COALESCE(TRY_CAST(? AS DECIMAL(23,10)), 0), "  # FDENOMINATOR
                                    f"TRY_CAST(? AS NVARCHAR(32)), "  # FISSUETYPE
                                    f"TRY_CAST(? AS NVARCHAR(32)), "  # FBACKFLUSHTYPE
                                    f"TRY_CAST(? AS INT), "  # FSUPPLYORG
                                    f"TRY_CAST(? AS INT), "  # FSTOCKID
                                    f"TRY_CAST(? AS NVARCHAR(50)), "  # FENTRYROWID
                                    f"TRY_CAST(? AS INT), "  # FREPLACEGROUP
                                    f"COALESCE(TRY_CAST(? AS DECIMAL(23,10)), 0), "  # FQTY
                                    f"COALESCE(TRY_CAST(? AS DECIMAL(23,10)), 0), "  # FACTUALQTY
                                    f"TRY_CAST(? AS INT), "  # FMASTERID
                                    f"TRY_CAST(? AS NVARCHAR(32)), "  # FMATERIALTYPE
                                    f"TRY_CAST(? AS DATETIME)"  # FMODIFYDATE
                                )
                            else:
                                insert_stage_sql = f"INSERT INTO {stage_ref} ({', '.join(columns)}) VALUES ({', '.join(['?' for _ in columns])})"
                            stage_insert_cols = columns[:]
                        try:
                            if identity_col and any(
                                str(c).strip().upper() == identity_col.strip().upper() for c in stage_insert_cols
                            ):
                                manager.cursor.execute(f"SET IDENTITY_INSERT {stage_ref} ON")
                                identity_insert_enabled = True
                                logger.debug(f"[STAGE] 为阶段表 {stage_ref} 开启 IDENTITY_INSERT")
                        except Exception:
                            identity_insert_enabled = False
                        if base_name.strip().lower() == "prd_instock":
                            try:
                                fid_idx = None
                                fentry_idx = None
                                for i, c in enumerate(columns):
                                    c_up = str(c).strip().upper()
                                    if c_up == "FID":
                                        fid_idx = i
                                    elif c_up == "FENTRYID":
                                        fentry_idx = i
                                if fid_idx is not None or fentry_idx is not None:
                                    original_count = len(values)
                                    filtered = []
                                    for row in values:
                                        try:
                                            fid_val = row[fid_idx] if fid_idx is not None else None
                                            fentry_val = row[fentry_idx] if fentry_idx is not None else None
                                            if (
                                                fid_idx is not None
                                                and (fid_val is None or str(fid_val).strip() == "")
                                            ) or (
                                                fentry_idx is not None
                                                and (fentry_val is None or str(fentry_val).strip() == "")
                                            ):
                                                continue
                                        except Exception:
                                            continue
                                        filtered.append(row)
                                    values = filtered
                                    if len(values) < original_count:
                                        logger.warning(
                                            f"[prd_instock] staging 跳过主键为空记录: {original_count - len(values)} 条"
                                        )
                            except Exception:
                                pass
                        total_batches = (len(values) - 1) // batch_size + 1
                        loaded = 0
                        for b_idx, i in enumerate(range(0, len(values), batch_size), start=1):
                            batch = values[i : i + batch_size]
                            batch_exec_seconds = 0.0
                            logger.info(f"[STAGE] 加载批次 {b_idx}/{total_batches}，记录数: {len(batch)}")
                            try:
                                manager.cursor.executemany(insert_stage_sql, batch)
                            except Exception as load_err:
                                # 若为 42S02/对象名无效，多半是阶段表尚未提交或被回滚，尝试重建并重试一次
                                if ("42S02" in str(load_err)) or (
                                    "对象名" in str(load_err) and "无效" in str(load_err)
                                ):
                                    logger.warning(f"[STAGE] 检测到阶段表不可用，尝试重新创建并重试：{load_err}")
                                    try:
                                        # 重新创建阶段表（使用同名或新后缀均可，这里保持同名以兼容后续 MERGE）
                                        try:
                                            manager.cursor.execute(drop_stage_sql)
                                        except Exception:
                                            pass
                                        manager.cursor.execute(create_stage_sql)
                                        # 再次验证并提交创建
                                        manager.cursor.execute(
                                            f"SELECT OBJECT_ID(N'dbo.__stage_{safe_name}_{suffix}', N'U')"
                                        )
                                        objid2 = manager.cursor.fetchone()
                                        if not objid2 or objid2[0] is None:
                                            raise Exception(f"阶段表重建失败: dbo.__stage_{safe_name}_{suffix}")
                                        try:
                                            manager.connection.commit()
                                        except Exception:
                                            pass
                                        # 重试当前批次加载（仍用 executemany）
                                        manager.cursor.executemany(insert_stage_sql, batch)
                                        logger.info("[STAGE] 阶段表重建后批次加载成功")
                                    except Exception as retry_err:
                                        logger.warning(f"[STAGE] 阶段表重建后仍加载失败，改为逐行插入：{retry_err}")
                                        for r in batch:
                                            manager.cursor.execute(insert_stage_sql, r)
                                else:
                                    logger.warning(f"[STAGE] 批量加载失败，切换为逐行插入：{load_err}")
                                    for r in batch:
                                        manager.cursor.execute(insert_stage_sql, r)
                            loaded += len(batch)
                        logger.info(f"[STAGE] 临时表加载完成，记录数: {loaded}")
                        # 关闭临时表的 IDENTITY_INSERT（如前面已开启）
                        try:
                            if identity_insert_enabled:
                                try:
                                    manager.cursor.execute(f"SET IDENTITY_INSERT {stage_ref} OFF")
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        # 集合 MERGE（一次性进行更新/插入）
                        # 当目标表包含 SYNC_TIME 时，在 UPDATE/INSERT 写入当前时间
                        # 同样在临时表 MERGE 中避免 NULL 覆盖非空值
                        stage_non_pk_cols = non_pk_cols
                        if base_name.strip().lower() == "prd_instock":
                            stage_non_pk_cols = [
                                c for c in stage_non_pk_cols if str(c).strip().upper() not in ("FID", "FENTRYID")
                            ]
                        stage_update_parts = [f"t.{c} = COALESCE(s.{c}, t.{c})" for c in stage_non_pk_cols]
                        # 避免更新标识列（如 SQL Server 的 IDENTITY 列），否则会触发 8102 错误
                        try:
                            identity_col = manager._get_identity_columns(table)
                            if identity_col:
                                stage_update_parts = [
                                    p for p in stage_update_parts if not p.startswith(f"t.{identity_col} ")
                                ]
                        except Exception:
                            pass
                        if has_sync_time and all(str(c).strip().upper() != "SYNC_TIME" for c in columns):
                            stage_update_parts.append("t.SYNC_TIME = GETDATE()")
                        stage_update_clause = (
                            ("WHEN MATCHED THEN UPDATE SET " + ", ".join(stage_update_parts))
                            if stage_update_parts
                            else ""
                        )
                        # 插入时也避开标识列，交由 SQL Server 自动生成，避免 544/8102 错误
                        identity_col = None
                        try:
                            identity_col = manager._get_identity_columns(table)
                        except Exception:
                            identity_col = None
                        if identity_col:
                            stage_insert_cols = [
                                c for c in columns if c.strip().upper() != identity_col.strip().upper()
                            ]
                            stage_insert_vals = [
                                f"s.{c}" for c in columns if c.strip().upper() != identity_col.strip().upper()
                            ]
                        else:
                            stage_insert_cols = columns[:]
                            stage_insert_vals = [f"s.{c}" for c in columns]
                        if has_sync_time and all(str(c).strip().upper() != "SYNC_TIME" for c in columns):
                            stage_insert_cols.append("SYNC_TIME")
                            stage_insert_vals.append("GETDATE()")
                        # 支持复合主键（如 eng_bomchild 使用 FID+FENTRYID）
                        pk_raw_stage = manager._get_primary_key(table) or columns[0]
                        # 特殊处理：BD_MATERIAL 使用唯一索引列作为合并键
                        # try:
                        #     if str(table).strip().lower() == 'bd_material':
                        #         pk_raw_stage = "FMASTERID,FMATERIALGROUP,FUSEORGID,FNUMBER"
                        # except Exception:
                        #     pass
                        pk_cols_stage = (
                            [c.strip() for c in pk_raw_stage.split(",")]
                            if isinstance(pk_raw_stage, str) and ("," in pk_raw_stage)
                            else [pk_raw_stage]
                        )
                        manager._maybe_create_stage_index(stage_ref, base_name, pk_cols_stage, loaded)
                        on_clause_stage = " AND ".join([f"t.{c} = s.{c}" for c in pk_cols_stage])
                        source_stage_ref = stage_ref
                        if base_name.strip().lower() == "prd_instock":
                            source_stage_ref = (
                                f"(SELECT * FROM {stage_ref} WHERE FID IS NOT NULL AND FENTRYID IS NOT NULL)"
                            )
                        set_merge_sql = (
                            f"MERGE INTO {table} AS t "
                            f"USING {source_stage_ref} AS s "
                            f"ON {on_clause_stage} "
                            + stage_update_clause
                            + f" WHEN NOT MATCHED THEN INSERT ({', '.join(stage_insert_cols)}) VALUES ({', '.join(stage_insert_vals)});"
                        )
                        manager.cursor.execute(set_merge_sql)
                        total_inserted = loaded
                        # 清理临时表
                        try:
                            manager.cursor.execute(f"DROP TABLE {stage_table}")
                        except Exception:
                            pass
                        manager.connection.commit()
                        if hasattr(manager.connection, "autocommit"):
                            manager.connection.autocommit = True
                        logger.info(f"成功插入/更新 {total_inserted} 条记录 (SQL Server, 临时表 MERGE)")
                        return total_inserted
                    except Exception as e:
                        if isinstance(e, ValueError):
                            raise
                        try:
                            manager.connection.rollback()
                        except Exception:
                            pass
                        if hasattr(manager.connection, "autocommit"):
                            manager.connection.autocommit = True
                        logger.error(f"临时表极速模式失败，已回滚: {e}")

                        # 诊断：如果是 8114 错误，尝试分析数据
                        if "8114" in str(e) or "data type" in str(e).lower():
                            manager._diagnose_data_type_error(table, columns, values)

                        # 确保失败情况下也清理阶段临时表，避免遗留 __stage_* 物理表
                        try:
                            # 优先使用已构造的 drop 语句
                            if "drop_stage_sql" in locals():
                                try:
                                    manager.cursor.execute(drop_stage_sql)
                                except Exception:
                                    pass
                            # 若上面未生效，尝试直接根据变量名删除
                            if "stage_table" in locals():
                                try:
                                    manager.cursor.execute(f"DROP TABLE {stage_table}")
                                except Exception:
                                    pass
                            try:
                                manager.connection.commit()
                            except Exception:
                                pass
                        except Exception:
                            pass
                        # 失败时回退到普通路径（下方）
                # 单线程路径：整次同步一次提交（未使用临时表时）
                if insert_threads == 1 and not use_staging:
                    try:
                        if hasattr(manager.connection, "autocommit"):
                            manager.connection.autocommit = False
                        # 普通路径：ODBC Driver 18 禁用 fast_executemany 以避免崩溃；eng_bomchild 禁用以避免 8114 错误
                        if hasattr(manager.cursor, "fast_executemany"):
                            if str(table).strip().lower() in ("eng_bomchild",) or is_d18:
                                manager.cursor.fast_executemany = False
                                logger.debug(f"针对表 {table} 禁用 fast_executemany (is_d18={is_d18})")
                            else:
                                manager.cursor.fast_executemany = True
                        total_batches = (len(values) - 1) // batch_size + 1
                        # 对 bd_material 的唯一索引（FNUMBER）做兼容处理：
                        # 1) 先更新已存在 FNUMBER 的记录（按 FNUMBER），不改 FMATERIALID；
                        # 2) 再按 FMATERIALID MERGE 插入/更新剩余记录（仅插入 FNUMBER 不存在的行）。
                        existing_fnumbers = set()
                        fnum_idx = None
                        try:
                            if str(table).strip().lower() == "bd_material":
                                # 取现有 FNUMBER 集合
                                manager.cursor.execute(f"SELECT FNUMBER FROM {table}")
                                for row in manager.cursor.fetchall():
                                    key = row[0]
                                    key_str = None if key is None else str(key).strip()
                                    if not key_str:
                                        key_str = ""
                                    existing_fnumbers.add(key_str)
                                # 定位 FNUMBER 列索引
                                for idx, col in enumerate(columns):
                                    if str(col).strip().upper() == "FNUMBER":
                                        fnum_idx = idx
                                        break
                        except Exception as e:
                            logger.warning(f"读取 bd_material 现有 FNUMBER 集合失败：{e}")

                        # 构建按 FNUMBER 更新的 MERGE（无 INSERT）
                        update_only_merge_sql = None
                        if str(table).strip().lower() == "bd_material" and fnum_idx is not None:
                            update_only_merge_sql = (
                                f"MERGE INTO {table} AS t "
                                + source_sql
                                + "ON t.FNUMBER = s.FNUMBER "
                                + (
                                    "WHEN MATCHED THEN UPDATE SET "
                                    + ", ".join([f"t.{c} = COALESCE(s.{c}, t.{c})" for c in non_pk_cols])
                                )
                                + ";"
                            )

                        for b_idx, i in enumerate(range(0, len(values), batch_size), start=1):
                            batch = values[i : i + batch_size]
                            logger.info(f"处理批次 {b_idx}/{total_batches}，记录数: {len(batch)}")
                            batch_exec_seconds = 0.0
                            is_bd_material = str(table).strip().lower() == "bd_material" and fnum_idx is not None
                            if is_bd_material:
                                # 先更新已存在 FNUMBER 的记录
                                update_rows = []
                                insert_rows = []
                                # 对待插入集按 FNUMBER 去重，保留最新
                                dedup_new_map = {}
                                for row in batch:
                                    key = row[fnum_idx]
                                    key_str = None if key is None else str(key).strip()
                                    if not key_str:
                                        key_str = ""
                                    if key_str in existing_fnumbers:
                                        update_rows.append(row)
                                    else:
                                        dedup_new_map[key_str] = row
                                insert_rows = list(dedup_new_map.values())
                                if update_rows and update_only_merge_sql:
                                    exec_started_at = time.perf_counter()
                                    manager.cursor.executemany(update_only_merge_sql, update_rows)
                                    batch_exec_seconds += time.perf_counter() - exec_started_at
                                    logger.info(f"[bd_material] 按 FNUMBER 更新 {len(update_rows)} 条记录")
                                    total_inserted += len(update_rows)
                                if insert_rows:
                                    exec_started_at = time.perf_counter()
                                    manager.cursor.executemany(merge_sql, insert_rows)
                                    batch_exec_seconds += time.perf_counter() - exec_started_at
                                    logger.info(f"[bd_material] 按 FMATERIALID 插入/更新 {len(insert_rows)} 条记录")
                                    total_inserted += len(insert_rows)
                                    # 将新插入的 FNUMBER 加入集合，避免后续批次重复
                                    for row in insert_rows:
                                        key = row[fnum_idx]
                                        key_str = None if key is None else str(key).strip()
                                        if not key_str:
                                            key_str = ""
                                        existing_fnumbers.add(key_str)
                            else:
                                # 非库存表：在批次内剔除主键为空的行，避免将 NULL 主键写入阶段表
                                try:
                                    pk_raw_stage = manager._get_primary_key(table) or columns[0]
                                    pk_cols_stage = (
                                        [c.strip() for c in pk_raw_stage.split(",")]
                                        if isinstance(pk_raw_stage, str) and ("," in pk_raw_stage)
                                        else [pk_raw_stage]
                                    )
                                    pk_idx_stage = []
                                    for pkc in pk_cols_stage:
                                        idx = None
                                        for i, c in enumerate(columns):
                                            if str(c).strip().upper() == str(pkc).strip().upper():
                                                idx = i
                                                break
                                        if idx is not None:
                                            pk_idx_stage.append(idx)
                                    if pk_idx_stage:
                                        filtered_batch = []
                                        for row in batch:
                                            try:
                                                key_tuple = (
                                                    tuple([manager._hashable_key(row[i]) for i in pk_idx_stage])
                                                    if len(pk_idx_stage) > 1
                                                    else (manager._hashable_key(row[pk_idx_stage[0]]),)
                                                )
                                            except Exception:
                                                key_tuple = tuple()
                                            try:
                                                if any((kv is None) or (str(kv).strip() == "") for kv in key_tuple):
                                                    continue
                                            except Exception:
                                                continue
                                            filtered_batch.append(row)
                                        batch = filtered_batch
                                except Exception:
                                    pass
                                # 其他表：按原逻辑执行 MERGE
                                exec_started_at = time.perf_counter()
                                manager.cursor.executemany(merge_sql, batch)
                                batch_exec_seconds = time.perf_counter() - exec_started_at
                                logger.info(f"批次 {b_idx} 执行成功，写入 {len(batch)} 条记录")
                                total_inserted += len(batch)
                            # 间隔提交策略（>0 时每 N 批提交一次，==0 时每批提交以降低大事务风险）
                            batch_commit_seconds = 0.0
                            if commit_every_n_batches > 0:
                                if b_idx % commit_every_n_batches == 0:
                                    commit_started_at = time.perf_counter()
                                    manager.connection.commit()
                                    batch_commit_seconds = time.perf_counter() - commit_started_at
                                    logger.debug(f"已间隔提交至批次 {b_idx}")
                            else:
                                commit_started_at = time.perf_counter()
                                manager.connection.commit()
                                batch_commit_seconds = time.perf_counter() - commit_started_at
                            log_write_metrics(
                                logger,
                                table_name=base_name,
                                batch_index=b_idx,
                                total_batches=total_batches,
                                row_count=len(batch),
                                exec_seconds=batch_exec_seconds,
                                commit_seconds=batch_commit_seconds,
                            )
                        # 循环结束后统一最终提交（确保无遗漏）
                        manager.connection.commit()
                        logger.info(f"成功插入/更新 {total_inserted} 条记录 (SQL Server)")
                        return total_inserted
                    except Exception as e:
                        try:
                            manager.connection.rollback()
                        except Exception:
                            pass
                        logger.error(f"批量插入过程中发生错误，已回滚: {str(e)}")
                        # 诊断：如果是 8114 错误，尝试分析数据
                        if "8114" in str(e) or "data type" in str(e).lower():
                            manager._diagnose_data_type_error(table, columns, values)
                        if "right truncation" in str(e).lower() or "string data" in str(e).lower():
                            manager._diagnose_string_truncation(table, columns, batch)
                        raise
                else:
                    # 多线程路径：分片并发，每线程独立连接与提交
                    def worker(shard_vals: list[list[Any]], shard_idx: int) -> int:
                        import random
                        import time

                        local_total = 0
                        local_conn = None
                        local_cursor = None

                        max_retries = 5
                        for attempt in range(max_retries):
                            try:
                                local_conn = manager.pool.connection() if manager.pool else None
                                if not local_conn:
                                    logger.error("连接池不可用，无法进行并发插入")
                                    return 0
                                local_cursor = local_conn.cursor()
                                if hasattr(local_conn, "autocommit"):
                                    local_conn.autocommit = False
                                if hasattr(local_cursor, "fast_executemany"):
                                    if base_name == "sub_subreqorder" or is_d18:
                                        local_cursor.fast_executemany = False
                                    else:
                                        local_cursor.fast_executemany = True

                                local_total = 0  # 重置计数
                                total_sub_batches = (len(shard_vals) - 1) // batch_size + 1
                                for sb_idx, j in enumerate(range(0, len(shard_vals), batch_size), start=1):
                                    batch = shard_vals[j : j + batch_size]
                                    logger.info(
                                        f"线程#{shard_idx} (尝试 {attempt + 1}/{max_retries}) 处理子批次 {sb_idx}/{total_sub_batches}，记录数: {len(batch)}"
                                    )
                                    local_cursor.executemany(merge_sql, batch)
                                    local_total += len(batch)
                                    if commit_every_n_batches > 0 and (sb_idx % commit_every_n_batches == 0):
                                        local_conn.commit()
                                        logger.debug(f"线程#{shard_idx} 已间隔提交至子批次 {sb_idx}")

                                local_conn.commit()
                                if hasattr(local_conn, "autocommit"):
                                    local_conn.autocommit = True
                                logger.info(f"线程#{shard_idx} 提交完成: {local_total} 条")
                                return local_total

                            except Exception as e:
                                try:
                                    if local_conn:
                                        local_conn.rollback()
                                except Exception:
                                    pass

                                # 检查死锁 (1205)
                                is_deadlock = "1205" in str(e) or "deadlock" in str(e).lower()
                                if is_deadlock:
                                    if attempt < max_retries - 1:
                                        sleep_time = random.uniform(0.5, 2.0) * (attempt + 1)
                                        logger.warning(
                                            f"线程#{shard_idx} 遇到死锁，{sleep_time:.2f}s 后重试 ({attempt + 1}/{max_retries})..."
                                        )
                                        time.sleep(sleep_time)
                                        continue
                                    logger.error(f"线程#{shard_idx} 死锁重试耗尽: {e}")
                                else:
                                    logger.error(f"线程#{shard_idx} 批量插入失败: {e}")

                                return 0
                            finally:
                                try:
                                    if local_cursor:
                                        local_cursor.close()
                                except Exception:
                                    pass
                                try:
                                    if local_conn:
                                        local_conn.close()
                                except Exception:
                                    pass
                        return 0

                    # 构造分片（按连续块分片以减少主键冲突概率）
                    shard_size = (len(values) + insert_threads - 1) // insert_threads
                    shards = [values[i : i + shard_size] for i in range(0, len(values), shard_size)]
                    with ThreadPoolExecutor(max_workers=insert_threads) as executor:
                        futures = {executor.submit(worker, shard, idx + 1): idx for idx, shard in enumerate(shards)}
                        for fut in as_completed(futures):
                            cnt = fut.result()
                            total_inserted += cnt
                    logger.info(f"成功并发插入/更新 {total_inserted} 条记录 (SQL Server, 线程数 {insert_threads})")
                    return total_inserted
            except Exception as e:
                if isinstance(e, ValueError):
                    raise
                logger.error(f"批量插入数据失败 (SQL Server): {str(e)}")
                return 0

        return 0
