"""数据库连接和操作模块（支持 MySQL / SQL Server），
负责与数据库进行数据交互，并使用连接池提高性能。"""

import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

import pymysql
import pyodbc
from dbutils.pooled_db import PooledDB

from src.config.config_manager import config_manager
from src.core.field_mapping_resolver import FieldMappingResolver
from src.core.performance_logging import log_prepare_metrics
from src.core.sync_log_repository import SyncLogRepository
from src.core.sync_run_repository import SyncRunRepository
from src.core.upsert_engine_mysql import UpsertEngineMySQL
from src.core.upsert_engine_sqlserver import UpsertEngineSqlServer
from src.core.write_outcome import WriteOutcome
from src.core.writers_registry import WriterRegistry


# 轻量连接池（失败降级用）：每次调用返回一个新连接
class SimpleConnectionPool:
    def __init__(self, factory):
        self.factory = factory

    def connection(self):
        return self.factory()


# 配置日志
logger = logging.getLogger(__name__)


class MySQLManager:
    """数据库管理器：使用连接池优化（支持 MySQL / SQL Server）。"""

    _metadata_cache_lock = threading.Lock()
    _table_columns_cache: dict[tuple[str, str], dict[str, str]] = {}
    _identity_column_cache: dict[tuple[str, str], str | None] = {}

    def _maybe_create_stage_index(self, stage_ref: str, base_name: str, pk_cols: list[str], row_count: int) -> None:
        """为大批量 staging 表创建主键索引，加速后续 MERGE 匹配。

        注意：使用独立 cursor 执行，避免与同一连接上其他 cursor 的状态冲突。
        """
        if getattr(self, "db_type", "mysql") != "sqlserver":
            return
        if not stage_ref or not pk_cols or row_count <= 0:
            return

        try:
            threshold = int(self.config.get("stage_index_threshold", "80000"))
        except Exception:
            threshold = 80000
        if row_count < threshold:
            return

        try:
            max_cols = int(self.config.get("stage_index_max_columns", "3"))
        except Exception:
            max_cols = 3
        if max_cols < 1:
            max_cols = 1

        stage_pk_cols = [str(c).strip() for c in pk_cols if str(c).strip()]
        stage_pk_cols = stage_pk_cols[:max_cols]
        if not stage_pk_cols:
            return

        idx_suffix = f"{abs(hash(stage_ref)) % 100000:05d}"
        idx_name = f"IX_STAGE_{base_name[:40]}_{idx_suffix}"
        idx_cols_sql = ", ".join(stage_pk_cols)
        create_idx_sql = f"CREATE CLUSTERED INDEX [{idx_name}] ON {stage_ref} ({idx_cols_sql})"

        # 使用独立的 cursor 创建索引，避免与其他操作的 cursor 状态冲突
        idx_cursor = None
        try:
            if self.connection:
                idx_cursor = self.connection.cursor()
                idx_cursor.execute(create_idx_sql)
                logger.info(f"[STAGE] 已为阶段表创建聚集索引: {idx_name} ({idx_cols_sql})")
        except Exception as e:
            logger.debug(f"[STAGE] 创建阶段表索引失败，继续执行无索引 MERGE: {e}")
        finally:
            if idx_cursor:
                try:
                    idx_cursor.close()
                except Exception:
                    pass

    def __init__(self):
        self.pool = None
        self.connection = None
        self.cursor = None
        self._pool_init_failed = False
        self._last_write_outcome = WriteOutcome()
        self.sync_run_repository = SyncRunRepository(self, logger=logger)
        self.sync_log_repository = SyncLogRepository(self, logger=logger)
        self.mysql_upsert_engine = UpsertEngineMySQL(self, logger=logger)
        self.sqlserver_upsert_engine = UpsertEngineSqlServer(self, logger=logger)
        self.writer_registry = WriterRegistry(logger=logger)
        self.reload_config()

    def reload_config(self):
        """重新加载配置并初始化连接池"""
        cfg = config_manager.get_db_config()
        self.db_type = cfg.get("type", "mysql").lower()
        get_field_mappings = getattr(config_manager, "get_field_mappings", None)
        field_mappings = get_field_mappings() if callable(get_field_mappings) else {}
        self.field_mapping_resolver = FieldMappingResolver(field_mappings)
        # 依据类型选择对应配置
        if self.db_type == "sqlserver":
            self.config = cfg.get("sqlserver", {})
        else:
            self.config = cfg.get("mysql", {})

        # 重置状态
        if self.pool or self.connection:
            self.disconnect()
        self.pool = None
        self._pool_init_failed = False
        self.sync_run_repository.reset()
        missing_writers = self.writer_registry.missing_methods(config_manager.get_insert_method_map())
        if missing_writers:
            logger.error("tables.json contains unmapped writers: %s", missing_writers)
        self._init_pool()

    def _init_pool(self) -> bool:
        """初始化数据库连接池"""
        try:
            if self.db_type == "sqlserver":
                host = self.config.get("host")
                port = int(self.config.get("port", 1433))
                database = self.config.get("database")
                user = self.config.get("user")
                password = self.config.get("password")
                dsn = self.config.get("dsn", "").strip()
                trusted_conn_cfg = str(self.config.get("trusted_connection", "false")).lower() == "true"
                encrypt_cfg = str(self.config.get("encrypt", "auto")).lower()  # auto/true/false
                trust_cert_cfg = str(self.config.get("trust_server_certificate", "true")).lower() == "true"
                login_timeout = int(self.config.get("login_timeout", "15"))
                # 选择可用的 ODBC 驱动
                configured_driver = self.config.get("driver", "ODBC Driver 17 for SQL Server")
                available_drivers = []
                try:
                    available_drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
                except Exception:
                    available_drivers = []
                preferred = [
                    "ODBC Driver 17 for SQL Server",
                    "ODBC Driver 18 for SQL Server",
                    "ODBC Driver 13 for SQL Server",
                    "SQL Server",
                ]
                driver = configured_driver
                if available_drivers:
                    # 如果配置的驱动在可用列表中，直接使用（跳过 preferred 优先级遍历）
                    if configured_driver and configured_driver in available_drivers:
                        driver = configured_driver
                    else:
                        for cand in preferred:
                            if cand in available_drivers:
                                driver = cand
                                break
                        if driver not in available_drivers:
                            driver = available_drivers[0]
                logger.info(f"检测到可用SQL Server ODBC驱动列表: {available_drivers}")
                logger.info(f"使用 SQL Server ODBC 驱动: {driver}")
                # 统一构建连接字符串，确保 DRIVER 名称被花括号包裹
                driver_part = "{" + driver + "}"

                # 加密策略：ODBC 18 默认 Encrypt=yes；ODBC 17 可选。auto 表示按驱动版本选择
                if encrypt_cfg == "auto":
                    encrypt_value = "yes" if "ODBC Driver 18" in driver else "no"
                else:
                    encrypt_value = "yes" if encrypt_cfg == "true" else "no"

                # DSN 优先
                base_params = []
                if dsn:
                    base_params.append(f"DSN={dsn}")
                else:
                    base_params.append(f"DRIVER={driver_part}")
                    base_params.append(f"SERVER={host}")
                    # 先尝试分号形式的端口参数；必要时降级到逗号形式
                    base_params.append(f"PORT={port}")

                base_params.append(f"DATABASE={database}")

                # 认证参数
                if trusted_conn_cfg:
                    base_params.append("Trusted_Connection=yes")
                else:
                    # 转义并包裹特殊字符，防止密码中包含分号等字符破坏连接字符串结构
                    safe_user = str(user).replace("}", "}}")
                    safe_password = str(password).replace("}", "}}")
                    base_params.append(f"UID={{{safe_user}}}")
                    base_params.append(f"PWD={{{safe_password}}}")
                    base_params.append("Trusted_Connection=no")

                # 安全与稳定参数
                base_params.append(f"Encrypt={'yes' if encrypt_value == 'yes' else 'no'}")
                if trust_cert_cfg:
                    base_params.append("TrustServerCertificate=Yes")
                base_params.append(f"LoginTimeout={login_timeout}")
                # 可选：启用多活动结果集，提升并发读取能力
                base_params.append("MARS_Connection=Yes")

                conn_str = ";".join(base_params)

                # 直连预检，提前发现连接字符串或驱动问题
                def _try_connect(s):
                    return pyodbc.connect(s, autocommit=True)

                try:
                    _test_conn = _try_connect(conn_str)
                    _test_conn.close()
                    logger.info("SQL Server直连预检通过 (SERVER=host;PORT=port 模式)")
                except Exception as e1:
                    logger.warning(f"预检失败(分号端口模式)，尝试逗号端口模式: {str(e1)}")
                    # 尝试 SERVER=host,port 形式
                    parts = [p for p in base_params if not p.startswith("SERVER=") and not p.startswith("PORT=")]
                    parts.insert(1, f"SERVER={host},{port}")
                    conn_str_alt = ";".join(parts)
                    try:
                        _test_conn = _try_connect(conn_str_alt)
                        _test_conn.close()
                        conn_str = conn_str_alt
                        logger.info("SQL Server直连预检通过 (SERVER=host,port 模式)")
                    except Exception as e2:
                        logger.error(f"SQL Server直连预检失败(两种端口模式均失败): {str(e2)}")
                        self._pool_init_failed = True
                        return False

                logger.info(f"正在初始化 SQL Server 连接 {host}:{port}")
                # 在驱动直连模式（未配置 DSN）下，直接使用轻量直连池，避免 PooledDB 初始化阶段出现 IM002 提示
                if not dsn:
                    self.pool = SimpleConnectionPool(lambda: pyodbc.connect(conn_str, autocommit=True))
                    logger.info("SQL Server轻量直连池初始化成功（驱动直连模式）")
                    return True
                try:
                    _max_conn = int(self.config.get("pool_maxconnections", 10))
                    _min_cached = int(self.config.get("pool_mincached", 2))
                    _max_cached = int(self.config.get("pool_maxcached", 5))
                    self.pool = PooledDB(
                        creator=pyodbc.connect,
                        maxconnections=_max_conn,
                        mincached=_min_cached,
                        maxcached=_max_cached,
                        maxshared=3,
                        blocking=True,
                        maxusage=None,
                        setsession=[],
                        ping=1,
                        # 连接字符串作为位置参数传入
                        args=(conn_str,),
                        kwargs={"autocommit": True},
                    )
                    logger.info(f"SQL Server连接池初始化成功: {database}")
                    return True
                except Exception as pe:
                    # 某些环境下，直连预检通过，但 PooledDB 内部初始化可能抛出 IM002（未指定DSN/默认驱动），
                    # 此处无需告警，直接降级为轻量直连池即可，不影响后续同步。
                    msg = str(pe)
                    if "IM002" in msg and "SQLDriverConnect" in msg:
                        logger.info(
                            "SQL Server连接池初始化失败(IM002)，已自动降级为轻量直连池；直连预检已通过，不影响后续同步"
                        )
                    else:
                        logger.warning(f"SQL Server连接池初始化失败，使用轻量直连池降级: {msg}")
                    self.pool = SimpleConnectionPool(lambda: pyodbc.connect(conn_str, autocommit=True))
                    logger.info("SQL Server轻量直连池初始化成功")
                    return True
            else:
                # MySQL 路径
                charset = self.config.get("charset", "utf8mb4")
                if "_" in charset:
                    charset = charset.split("_")[0]
                logger.info(f"正在初始化 MySQL 连接: {self.config['host']}:{self.config.get('port', 3306)}")
                _max_conn = int(self.config.get("pool_maxconnections", 10))
                _min_cached = int(self.config.get("pool_mincached", 2))
                _max_cached = int(self.config.get("pool_maxcached", 5))
                self.pool = PooledDB(
                    creator=pymysql,
                    maxconnections=_max_conn,
                    mincached=_min_cached,
                    maxcached=_max_cached,
                    maxshared=3,
                    blocking=True,
                    maxusage=None,
                    setsession=[],
                    ping=1,
                    host=self.config["host"],
                    user=self.config["user"],
                    password=self.config["password"],
                    database=self.config["database"],
                    charset=charset,
                    port=int(self.config.get("port", 3306)),
                    autocommit=True,
                    cursorclass=pymysql.cursors.DictCursor,
                    connect_timeout=30,
                    read_timeout=30,
                    write_timeout=30,
                )
                logger.info(f"MySQL连接池初始化成功: {self.config['database']}")
                return True
        except Exception as e:
            logger.error(f"初始化{('SQL Server' if self.db_type == 'sqlserver' else 'MySQL')}连接池失败: {str(e)}")
            return False

    def connect(self) -> bool:
        """从连接池获取连接"""
        retries = max(1, int(self.config.get("connect_retries", 3) or 3))
        retry_delay = max(0.2, float(self.config.get("connect_retry_delay_secs", 1.0) or 1.0))

        for attempt in range(1, retries + 1):
            try:
                self.disconnect()

                if not self.pool:
                    if getattr(self, "_pool_init_failed", False):
                        return False
                    if not self._init_pool():
                        raise ConnectionError("连接池初始化失败")

                self.connection = self.pool.connection()
                self.cursor = self.connection.cursor()

                self.cursor.execute("SELECT 1")
                result = self.cursor.fetchone()
                valid = False
                if isinstance(result, dict):
                    valid = (result.get("1") == 1) or (list(result.values())[0] == 1 if result else False)
                else:
                    try:
                        valid = result[0] == 1
                    except Exception:
                        valid = bool(result)

                if valid:
                    logger.debug("成功从连接池获取数据库连接")
                    return True

                raise ConnectionError("从连接池获取的连接无效")
            except (pymysql.OperationalError, pyodbc.OperationalError) as exc:
                logger.warning("数据库连接操作失败（第 %s/%s 次）: %s", attempt, retries, exc)
            except Exception as exc:
                logger.warning("获取数据库连接失败（第 %s/%s 次）: %s: %s", attempt, retries, type(exc).__name__, exc)

            self.disconnect()
            self._init_pool()
            if attempt < retries:
                time.sleep(retry_delay)

        logger.error("数据库连接在 %s 次重试后仍然失败", retries)
        return False

    def disconnect(self):
        """归还连接到连接池"""
        if self.cursor:
            try:
                self.cursor.close()
            except Exception:
                pass
            self.cursor = None

        if self.connection:
            try:
                self.connection.close()  # 使用连接池时，close实际上是归还连接
            except Exception:
                pass
            self.connection = None

        logger.debug("已关闭并归还数据库连接到连接池")

    def test_connection(self) -> bool:
        """测试数据库连接"""
        retries = max(1, int(self.config.get("connect_retries", 3) or 3))
        retry_delay = max(0.2, float(self.config.get("connect_retry_delay_secs", 1.0) or 1.0))

        for attempt in range(1, retries + 1):
            test_conn = None
            try:
                test_conn = self.pool.connection() if self.pool else None
                if not test_conn:
                    return self.connect()

                with test_conn.cursor() as test_cursor:
                    test_cursor.execute("SELECT 1")
                    result = test_cursor.fetchone()
                    success = False
                    if isinstance(result, dict):
                        success = result is not None and ((result.get("1") == 1) or (list(result.values())[0] == 1))
                    else:
                        try:
                            success = result is not None and result[0] == 1
                        except Exception:
                            success = result is not None

                return success
            except Exception as exc:
                logger.warning("测试数据库连接失败（第 %s/%s 次）: %s", attempt, retries, exc)
                if attempt < retries:
                    time.sleep(retry_delay)
            finally:
                if test_conn is not None:
                    try:
                        test_conn.close()
                    except Exception:
                        pass

        logger.error("测试数据库连接在 %s 次重试后仍然失败", retries)
        return False

    def insert_generic_data(self, table_name: str, data: list[dict[str, Any]]) -> int:
        """通用数据插入方法，依据字典键自动匹配列"""
        if not data:
            return 0

        if not self.connection or not self.cursor:
            if not self.connect():
                return 0

        inserted_count = 0
        try:
            # 1. 获取第一条数据的键，作为列名
            # 假设所有数据字典结构一致
            columns = list(data[0].keys())

            # 2. 构建插入SQL
            if self.db_type == "sqlserver":
                placeholders = ", ".join(["?"] * len(columns))
                # 使用方括号包裹列名以防关键字冲突
                safe_columns = [f"[{col}]" for col in columns]
                cols_str = ", ".join(safe_columns)
                # 使用 MERGE INTO 替代简单的 INSERT，以支持更新/去重（这里简化为覆盖插入或直接插入）
                # 为保持逻辑简单和高效，这里采用先删后插（全量覆盖）或直接插入（增量追加）
                # 考虑到同步逻辑中通常会先处理时间戳或FID去重，这里直接使用INSERT，依赖上层逻辑控制
                sql = f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})"
            else:
                placeholders = ", ".join(["%s"] * len(columns))
                safe_columns = [f"`{col}`" for col in columns]
                cols_str = ", ".join(safe_columns)
                sql = f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})"

            # 3. 预计算每列的数字类型推断，避免行级重复字符串匹配
            NUMERIC_KEYWORDS = ["DEBIT", "CREDIT", "AMOUNT", "QTY", "PRICE", "RATE", "LOCAL", "BALANCE"]
            EXCLUDE_KEYWORDS = ["ID", "NAME", "NUMBER", "BILLNO", "CODE"]
            col_is_numeric = {}
            for col in columns:
                upper_col = col.upper()
                excluded = any(ex in upper_col for ex in EXCLUDE_KEYWORDS)
                col_is_numeric[col] = (not excluded) and any(kw in upper_col for kw in NUMERIC_KEYWORDS)

            # 4. 批量执行
            values_list = []
            for row in data:
                # 确保值的顺序与列名一致
                values = []
                for col in columns:
                    val = row.get(col)

                    # 使用预计算的列类型缓存，避免行级重复字符串匹配
                    if val is None:
                        if col_is_numeric[col]:
                            val = 0
                    elif isinstance(val, (dict, list)):
                        val = str(val)
                    elif isinstance(val, str) and col_is_numeric[col]:
                        clean_val = val.strip()
                        if clean_val == "":
                            val = 0
                        else:
                            val = clean_val.replace(",", "")
                    values.append(val)
                values_list.append(tuple(values))

            # 分批插入以避免参数过多
            try:
                batch_size = int(self.config.get("batch_size", "1000"))
            except Exception:
                batch_size = 1000
            if batch_size < 100:
                batch_size = 100
            if self.db_type == "sqlserver" and hasattr(self.cursor, "fast_executemany"):
                # ODBC Driver 18 的 fast_executemany 在并发/大批量场景下会触发驱动崩溃，改为禁用
                configured_driver = self.config.get("driver", "ODBC Driver 17 for SQL Server")
                if "ODBC Driver 18" in configured_driver:
                    self.cursor.fast_executemany = False
                    logger.warning("检测到 ODBC Driver 18，已禁用 fast_executemany 以避免驱动崩溃")
                else:
                    self.cursor.fast_executemany = True
            for i in range(0, len(values_list), batch_size):
                batch = values_list[i : i + batch_size]
                self.cursor.executemany(sql, batch)
                inserted_count += len(batch)

            self.connection.commit()
            return inserted_count

        except pymysql.IntegrityError as e:
            logger.error(f"插入表 {table_name} 违反唯一约束: {str(e)}")
            if self.connection:
                self.connection.rollback()
            return 0
        except pymysql.OperationalError as e:
            logger.error(f"插入表 {table_name} 数据库操作失败: {str(e)}")
            if self.connection:
                self.connection.rollback()
            return 0
        except pyodbc.IntegrityError as e:
            logger.error(f"插入表 {table_name} 违反唯一约束 (SQL Server): {str(e)}")
            if self.connection:
                self.connection.rollback()
            return 0
        except pyodbc.OperationalError as e:
            logger.error(f"插入表 {table_name} 数据库操作失败 (SQL Server): {str(e)}")
            if self.connection:
                self.connection.rollback()
            return 0
        except Exception as e:
            logger.error(f"通用插入表 {table_name} 失败 ({type(e).__name__}): {str(e)}")
            if self.connection:
                self.connection.rollback()
            return 0

    def execute_writer_with_outcome(self, method_name: str, data: list[dict]) -> WriteOutcome:
        """Execute a writer and preserve structured write outcome metadata."""
        self._last_write_outcome = WriteOutcome()
        inserted = self.writer_registry.execute(self, method_name, data)
        if self._last_write_outcome.inserted == 0:
            self._last_write_outcome.inserted = WriteOutcome.from_insert_count(inserted).inserted
        return self._last_write_outcome

    def execute_writer(self, method_name: str, data: list[dict]) -> int:
        """Execute a registered writer by name."""
        return self.execute_writer_with_outcome(method_name, data).inserted

    def recover_stale_sync_runs(
        self,
        reason: str | None = None,
        heartbeat_timeout_seconds: int | None = None,
    ) -> int:
        """Recover leftover sync runs that are still marked as running."""
        return self.sync_run_repository.recover_running_runs(
            reason=reason,
            heartbeat_timeout_seconds=heartbeat_timeout_seconds,
        )

    def table_exists(self, table_name: str) -> bool:
        """检查数据表是否存在。"""
        try:
            if not self.connection or not self.cursor:
                if not self.connect():
                    return False

            if self.db_type == "sqlserver":
                self.cursor.execute(
                    "SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = ?",
                    (table_name,),
                )
            else:
                self.cursor.execute("SHOW TABLES LIKE %s", (table_name,))
            return self.cursor.fetchone() is not None
        except Exception as e:
            logger.debug(f"检查表 {table_name} 是否存在失败: {e}")
            return False

    @staticmethod
    def _format_forms_summary(forms: list[str] | None) -> str:
        """Format forms via the dedicated sync run repository."""
        return SyncRunRepository.format_forms_summary(forms)

    def ensure_sync_runs_table(self) -> bool:
        """Ensure sync_runs exists via the dedicated sync run repository."""
        return self.sync_run_repository.ensure_table()

    def start_sync_run(self, run_id: str, sync_type: str, forms: list[str] | None, start_time: datetime) -> bool:
        """Delegate sync run start persistence to the sync run repository."""
        return self.sync_run_repository.start_run(run_id, sync_type, forms, start_time)

    def heartbeat_sync_run(self, run_id: str, message: str | None = None, heartbeat_at: datetime | None = None) -> bool:
        """Delegate running task heartbeat persistence to the sync run repository."""
        return self.sync_run_repository.heartbeat_run(
            run_id=run_id,
            message=message,
            heartbeat_at=heartbeat_at,
        )

    def finish_sync_run(
        self,
        run_id: str,
        sync_type: str,
        forms: list[str] | None,
        total_records: int,
        success_count: int,
        failure_count: int,
        status: str,
        message: str,
        start_time: datetime,
        end_time: datetime,
        failed_forms: list[str] | None = None,
        details: dict[str, Any] | None = None,
    ) -> bool:
        """Delegate sync run completion persistence to the sync run repository."""
        return self.sync_run_repository.finish_run(
            run_id=run_id,
            sync_type=sync_type,
            forms=forms,
            total_records=total_records,
            success_count=success_count,
            failure_count=failure_count,
            status=status,
            message=message,
            start_time=start_time,
            end_time=end_time,
            failed_forms=failed_forms,
            details=details,
        )

    def mark_sync_run_abnormal_exit(
        self,
        run_id: str,
        reason: str,
        end_time: datetime | None = None,
    ) -> bool:
        """Delegate abnormal-exit task persistence to the sync run repository."""
        return self.sync_run_repository.mark_run_abnormal_exit(
            run_id=run_id,
            reason=reason,
            end_time=end_time,
        )

    def log_sync_operation(
        self,
        sync_type: str,
        table_name: str,
        operation: str,
        record_count: int,
        status: str,
        message: str,
        start_time: datetime,
        end_time: datetime,
        error_type: str = None,
    ) -> bool:
        """Delegate sync log persistence to the sync log repository."""
        return self.sync_log_repository.log_operation(
            sync_type=sync_type,
            table_name=table_name,
            operation=operation,
            record_count=record_count,
            status=status,
            message=message,
            start_time=start_time,
            end_time=end_time,
            error_type=error_type,
        )

    def get_last_modify_time(self, table_name: str) -> datetime | None:
        """获取表中最后同步时间 (SYNC_TIME)"""
        try:
            if not self.connection or not self.cursor:
                logger.warning("数据库连接丢失，尝试重新连接...")
                if not self.connect():
                    logger.error("重新连接数据库失败，无法获取最后修改时间")
                    return None
            # 确保 SYNC_TIME 列存在
            try:
                self._ensure_sync_time_column(table_name)
            except Exception as e:
                logger.warning(f"尝试为 {table_name} 添加 SYNC_TIME 列失败: {e}")

            # 始终使用 SYNC_TIME 作为本地比较基准
            modify_time_field = "SYNC_TIME"
            sql = f"SELECT MAX({modify_time_field}) AS last_modify_time FROM {table_name}"
            self.cursor.execute(sql)
            result = self.cursor.fetchone()

            last_time = None
            if result:
                if isinstance(result, dict):
                    last_time = result.get("last_modify_time")
                else:
                    try:
                        last_time = result[0]
                    except Exception:
                        last_time = None

            return last_time

        except Exception as e:
            logger.error(f"获取 {table_name} 最后修改时间失败: {str(e)}")
            return None

    def get_last_time(self, table_name: str, time_field: str) -> datetime | None:
        """获取指定表的最大时间字段值，用于增量同步"""
        try:
            if not self.connection or not self.cursor:
                logger.warning("数据库连接丢失，尝试重新连接...")
                if not self.connect():
                    logger.error("重新连接数据库失败，无法获取最后时间")
                    return None
            sql = f"SELECT MAX({time_field}) AS last_time FROM {table_name}"
            self.cursor.execute(sql)
            result = self.cursor.fetchone()
            if result:
                if isinstance(result, dict):
                    return result.get("last_time")
                try:
                    return result[0]
                except Exception:
                    return None
            return None
        except Exception as e:
            logger.error(f"获取 {table_name}.{time_field} 最大时间失败: {str(e)}")
            return None

    def create_tables(self, create_tables: bool = True) -> bool:
        """创建数据表（已禁用自动建表与字段修复，始终跳过）"""
        try:
            logger.info("已禁用自动建表，直接使用现有数据库结构。")
            return True
        except Exception as e:
            logger.warning(f"跳过建表时发生非致命错误: {e}")
            return True

    def _parse_date(self, date_str):
        """解析日期字符串"""
        if not date_str:
            return None
        try:
            date_str = self._extract_scalar(date_str)
            # 尝试解析日期格式
            if isinstance(date_str, str):
                if "T" in date_str:
                    # ISO格式: 2023-01-01T00:00:00
                    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                if len(date_str) == 10:
                    # 日期格式: 2023-01-01
                    return datetime.strptime(date_str, "%Y-%m-%d")
                # 其他格式尝试
                return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            if isinstance(date_str, datetime):
                return date_str
            return None
        except Exception as e:
            logger.warning(f"日期解析失败: {date_str}, 错误: {str(e)}")
            return None

    def _parse_datetime(self, dt_str):
        """解析日期时间字符串"""
        return self._parse_date(dt_str)

    def _extract_scalar(self, value):
        if value is None or isinstance(value, (str, int, float, bool, datetime, Decimal)):
            return value
        try:
            if isinstance(value, dict):
                preferred_keys = (
                    "FID",
                    "FENTRYID",
                    "FId",
                    "Id",
                    "ID",
                    "id",
                    "FNumber",
                    "Number",
                    "number",
                    "FName",
                    "Name",
                    "name",
                    "Value",
                    "value",
                )
                for k in preferred_keys:
                    if k in value:
                        v = self._extract_scalar(value.get(k))
                        if v is not None and str(v).strip() != "":
                            return v
                if len(value) == 1:
                    return self._extract_scalar(next(iter(value.values())))
                return str(value)
            if isinstance(value, (list, tuple, set)):
                seq = list(value)
                if len(seq) == 1:
                    return self._extract_scalar(seq[0])
                return str(value)
            return str(value)
        except Exception:
            return str(value)

    def _normalize_row(self, row):
        if isinstance(row, tuple):
            return tuple(self._extract_scalar(v) for v in row)
        if isinstance(row, list):
            return [self._extract_scalar(v) for v in row]
        return self._extract_scalar(row)

    def _hashable_key(self, value):
        try:
            v = self._extract_scalar(value)
            if isinstance(v, dict):
                return tuple(sorted((str(k), self._hashable_key(val)) for k, val in v.items()))
            if isinstance(v, (list, tuple, set)):
                return tuple(self._hashable_key(i) for i in v)
            return v
        except Exception:
            return str(value)

    def _format_date_only(self, dt_val):
        """格式化为仅日期字符串 YYYY-MM-DD"""
        if dt_val is None:
            return None
        if isinstance(dt_val, datetime):
            return dt_val.strftime("%Y-%m-%d")
        # 字符串或其他类型先解析为 datetime
        parsed = self._parse_date(dt_val)
        return parsed.strftime("%Y-%m-%d") if isinstance(parsed, datetime) else None

    def _to_decimal_or_none(self, value):
        """将输入安全转换为数值（float），无法转换返回 None。
        - 支持 int/float/Decimal 直接转换
        - 字符串会去除逗号、空白，处理会计负数格式 (123)
        - 无效值如空字符串、'null'、'none'、'n/a'、'-' 返回 None
        - 对数值进行 6 位小数量化，并限制整数位不超过 17 位（DECIMAL(23,6)）
        """
        try:
            value = self._extract_scalar(value)
            if value is None:
                return None
            if isinstance(value, (int, float, Decimal)):
                d = Decimal(str(value))
                try:
                    d = d.quantize(Decimal("0.000001"))
                except InvalidOperation:
                    pass
                # 限制整数位长度，超过则返回 None，避免精度丢失错误
                if d.copy_abs() >= Decimal("1e17"):
                    return None
                return float(d)
            if isinstance(value, str):
                s = value.strip()
                if not s:
                    return None
                s_lower = s.lower()
                if s_lower in ("null", "none", "n/a", "na") or s in ("-",):
                    return None
                # 处理会计负数格式 (123)
                negative = False
                if s.startswith("(") and s.endswith(")"):
                    negative = True
                    s = s[1:-1]
                # 去掉千位分隔符
                s = s.replace(",", "")
                try:
                    d = Decimal(s)
                except InvalidOperation:
                    # 尝试移除非数字字符
                    import re

                    cleaned = re.sub(r"[^0-9\.-]", "", s)
                    if not cleaned:
                        return None
                    try:
                        d = Decimal(cleaned)
                    except InvalidOperation:
                        return None
                # 量化为 6 位小数
                try:
                    d = d.quantize(Decimal("0.000001"))
                except InvalidOperation:
                    pass
                # 限制整数位长度，超过则返回 None
                if d.copy_abs() >= Decimal("1e17"):
                    return None
                d = -d if negative else d
                return float(d)
            return None
        except Exception:
            return None

    def _to_int_or_none(self, value):
        """将输入安全转换为整数，无法转换则返回 None。
        - 支持 int 直接返回
        - 字符串会去除逗号、空白，处理会计负数格式 (123)
        - 无效值如空字符串、'null'、'none'、'n/a'、'-' 返回 None
        """
        try:
            value = self._extract_scalar(value)
            if value is None:
                return None
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                # 仅当为整数值时接受
                if value.is_integer():
                    return int(value)
                return None
            if isinstance(value, str):
                s = value.strip()
                if not s:
                    return None
                s_lower = s.lower()
                if s_lower in ("null", "none", "n/a", "na") or s in ("-",):
                    return None
                negative = False
                if s.startswith("(") and s.endswith(")"):
                    negative = True
                    s = s[1:-1]
                s = s.replace(",", "")
                if s.startswith("+"):
                    s = s[1:]
                try:
                    n = int(float(s)) if "." in s else int(s)
                except Exception:
                    return None
                return -n if negative else n
            return None
        except Exception:
            return None

    def insert_production_orders(self, data: list[dict]) -> int:
        return self.execute_writer("insert_production_orders", data)

    def insert_prd_moentry(self, data: list[dict]) -> int:
        return self.execute_writer("insert_prd_moentry", data)

    def _parse_insert_sql(self, sql: str) -> tuple[str | None, list[str]]:
        """解析 INSERT 语句，提取表名与列名列表（用于 SQL Server MERGE 生成）"""
        try:
            import re

            m = re.search(r"INSERT\s+INTO\s+([A-Za-z_][\w]*)\s*\(([^)]*)\)\s*VALUES", sql, re.IGNORECASE | re.DOTALL)
            if not m:
                return None, []
            table = m.group(1)
            cols_raw = m.group(2)
            columns = [c.strip() for c in cols_raw.split(",") if c.strip()]
            return table, columns
        except Exception:
            return None, []

    def _normalize_table_cache_key(self, table_name: str) -> str:
        return str(table_name or "").split(".")[-1].replace("[", "").replace("]", "").strip().lower()

    def _invalidate_table_metadata_cache(self, table_name: str) -> None:
        cache_key = (getattr(self, "db_type", "mysql"), self._normalize_table_cache_key(table_name))
        with self._metadata_cache_lock:
            self._table_columns_cache.pop(cache_key, None)
            self._identity_column_cache.pop(cache_key, None)

    def _get_table_columns_info(self, table_name: str) -> dict[str, str]:
        cache_key = (getattr(self, "db_type", "mysql"), self._normalize_table_cache_key(table_name))
        with self._metadata_cache_lock:
            cached = self._table_columns_cache.get(cache_key)
        if cached is not None:
            return cached

        columns_info: dict[str, str] = {}
        if not self.cursor or not table_name:
            return columns_info

        try:
            normalized_table = self._normalize_table_cache_key(table_name)
            if getattr(self, "db_type", "mysql") == "sqlserver":
                self.cursor.execute(
                    """
                    SELECT COLUMN_NAME, DATA_TYPE
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE LOWER(TABLE_NAME)=?
                    """,
                    (normalized_table,),
                )
            else:
                self.cursor.execute(
                    """
                    SELECT COLUMN_NAME, DATA_TYPE
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE LOWER(TABLE_NAME)=%s
                    """,
                    (normalized_table,),
                )
            for row in self.cursor.fetchall() or []:
                if isinstance(row, dict):
                    col_name = row.get("COLUMN_NAME")
                    data_type = row.get("DATA_TYPE")
                else:
                    col_name = row[0] if len(row) > 0 else None
                    data_type = row[1] if len(row) > 1 else None
                if col_name:
                    columns_info[str(col_name).upper()] = str(data_type or "").lower()
        except Exception as e:
            logger.debug(f"读取 {table_name} 列信息失败: {e}")
            return {}

        with self._metadata_cache_lock:
            self._table_columns_cache[cache_key] = columns_info
        return columns_info

    def _table_has_column(self, table_name: str, column_name: str) -> bool:
        if not table_name or not column_name:
            return False
        return str(column_name).upper() in self._get_table_columns_info(table_name)

    def _get_primary_key(self, table_name: str) -> str | None:
        """获取已知表的主键列名（用于 SQL Server MERGE）"""
        mapping = {
            "prd_mo": "FID",
            "saleorder": "FENTRYID",
            "sal_xorder": "FENTRYID",
            "sal_returnstock": "FENTRYID",
            "sal_outstock": "FENTRYID",
            "sal_deliverynotice": "FENTRYID",
            "pln_forecast": "FENTRYID",
            "prd_ppbomentry": "FENTRYID",
            "prd_ppbom": "FID",
            "customer": "FCUSTID",
            # 物料主数据改为以 FMATERIALID 作为合并匹配键
            "bd_material": "FMATERIALID",
            "prd_moentry": "FENTRYID",
            "bd_stock": "FSTOCKID",
            "eng_bomchild": "FID,FENTRYID",
            "prd_instock": "FENTRYID",
            "pur_purchaseorder": "FID,FENTRYID",
            "sub_subreqorder": "FID,FENTRYID",
            "ar_receivable": "FENTRYID",
            "ap_payable": "FENTRYID",
        }
        return mapping.get((table_name or "").lower())

    def _get_identity_columns(self, table_name: str) -> str | None:
        """返回指定表的标识(IDENTITY)列（用于 SQL Server，避免 UPDATE/INSERT 显式写入导致错误）
        注意：此映射按当前项目表结构维护；如表结构变更需同步更新。
        """
        cache_key = (getattr(self, "db_type", "mysql"), self._normalize_table_cache_key(table_name))
        with self._metadata_cache_lock:
            cached = self._identity_column_cache.get(cache_key, "__MISSING__")
        if cached != "__MISSING__":
            return cached

        identity_col = None
        try:
            if (getattr(self, "db_type", "mysql") == "sqlserver") and self.cursor and table_name:
                self.cursor.execute(
                    """
                    SELECT c.name
                    FROM sys.columns c
                    WHERE c.object_id = OBJECT_ID(?) AND c.is_identity = 1
                    """,
                    (table_name,),
                )
                rows = self.cursor.fetchall() or []
                if len(rows) == 1:
                    identity_col = rows[0][0] if not isinstance(rows[0], dict) else rows[0].get("name")
                if len(rows) > 1:
                    identity_col = rows[0][0] if not isinstance(rows[0], dict) else rows[0].get("name")
        except Exception:
            pass
        if identity_col is None:
            mapping = {
            # 'prd_instock': 'FID'  # 移除：FID非自增列，需显式插入
            }
            identity_col = mapping.get((table_name or "").lower())

        with self._metadata_cache_lock:
            self._identity_column_cache[cache_key] = identity_col
        return identity_col

    def _ensure_sync_time_column(self, table_name: str) -> None:
        """确保目标表存在 SYNC_TIME 列；若不存在则自动添加。
        - SQL Server: 添加 DATETIME 列
        - MySQL: 添加 DATETIME 列（不设置默认，避免与显式写入冲突）
        """
        if not table_name:
            return
        try:
            is_sqlserver = getattr(self, "db_type", "mysql") == "sqlserver"
            if self._table_has_column(table_name, "SYNC_TIME"):
                return
            # 不存在则新增列
            # MySQL 端设置默认值与自动更新，保证插入/更新均能写入当前时间
            if is_sqlserver:
                alter_sql = f"ALTER TABLE {table_name} ADD SYNC_TIME DATETIME NULL"
            else:
                alter_sql = f"ALTER TABLE {table_name} ADD COLUMN SYNC_TIME DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
            self.cursor.execute(alter_sql)
            try:
                self.connection.commit()
            except Exception:
                pass
            self._invalidate_table_metadata_cache(table_name)
            logger.info(f"[{table_name}] 已自动添加 SYNC_TIME 列")
        except Exception as e:
            # 非致命：记录警告，后续逻辑会根据 has_sync_time 判定是否写入
            logger.warning(f"[{table_name}] 自动添加 SYNC_TIME 列失败: {e}")

    def _batch_insert(self, sql: str, data: list[dict], prepare_func) -> int:
        """批量插入数据 - 优化版本，使用事务和分批处理"""
        if data and len(data) > 0:
            logger.debug(
                f"DB Insert Request: {len(data)} items to insert. First item: {list(data[0].keys()) if isinstance(data[0], dict) else '?'}"
            )

        try:
            # 检查数据库连接
            if not self.connection or not self.cursor:
                logger.warning("数据库连接丢失，尝试重新连接...")
                if not self.connect():
                    logger.error("重新连接数据库失败")
                    return 0

            # 准备数据
            table_name = "unknown_table"
            try:
                parsed_table_name, _cols = self._parse_insert_sql(sql)
                if parsed_table_name:
                    table_name = str(parsed_table_name)
            except Exception:
                pass

            prepare_started_at = time.perf_counter()
            values = []
            for item in data:
                prepared_data = prepare_func(item)
                if prepared_data:
                    values.append(self._normalize_row(prepared_data))
            prepare_duration = time.perf_counter() - prepare_started_at
            log_prepare_metrics(
                logger,
                table_name=table_name,
                source_rows=len(data or []),
                prepared_rows=len(values),
                duration_seconds=prepare_duration,
            )

            if not values:
                logger.warning("没有有效数据需要插入")
                return 0

            # 在插入/合并前统一确保目标表存在 SYNC_TIME 列
            try:
                if table_name:
                    self._ensure_sync_time_column(table_name)
            except Exception as e:
                # 非致命，记录日志后继续
                logger.debug(f"预检查 SYNC_TIME 列失败（可忽略）: {e}")

            batch_size = 10000
            commit_every_n_batches = 0
            if getattr(self, "db_type", "mysql") == "sqlserver":
                try:
                    batch_size = int(self.config.get("batch_size", "20000"))
                except Exception:
                    batch_size = 20000
                if batch_size < 1000:
                    batch_size = 1000
                if batch_size > 100000:
                    batch_size = 100000
                try:
                    commit_every_n_batches = int(self.config.get("commit_every_n_batches", "0"))
                except Exception:
                    commit_every_n_batches = 0
                if commit_every_n_batches < 0:
                    commit_every_n_batches = 0
            else:
                try:
                    batch_size = int(self.config.get("batch_size", str(batch_size)))
                except Exception:
                    pass
                if batch_size < 1000:
                    batch_size = 1000
                if batch_size > 100000:
                    batch_size = 100000

            if getattr(self, "db_type", "mysql") == "sqlserver":
                return self.sqlserver_upsert_engine.execute(
                    sql=sql,
                    values=values,
                    batch_size=batch_size,
                    commit_every_n_batches=commit_every_n_batches,
                )

            return self.mysql_upsert_engine.execute(
                sql=sql,
                values=values,
                batch_size=batch_size,
            )

        except Exception as e:
            logger.error(f"批量插入数据失败: {str(e)}")
            if "connection" in str(e).lower() or "packet" in str(e).lower():
                logger.warning("检测到连接错误，尝试重新连接...")
                self.connection = None
                self.cursor = None
            return 0

    def _convert_production_status(self, status_value):
        """转换生产订单状态
        状态值对应关系：
        1 -> 计划
        2 -> 计划确认
        3 -> 下达
        4 -> 开工
        5 -> 完工
        6 -> 结案
        7 -> 结算
        """
        status_map = {
            # 数字转中文（数据库字段已改为 varchar(4)）
            "1": "计划",
            "2": "计划确认",
            "3": "下达",
            "4": "开工",
            "5": "完工",
            "6": "结案",
            "7": "结算",
            # 处理可能的文本值（保持不变）
            "计划": "计划",
            "计划确认": "计划确认",
            "下达": "下达",
            "开工": "开工",
            "完工": "完工",
            "结案": "结案",
            "结算": "结算",
        }

        if status_value is None:
            return None

        # 转换为字符串并去除空白
        status_str = str(status_value).strip()

        # 返回映射值，如果没有对应的映射则返回原值
        return status_map.get(status_str, status_str)

    def _resolve_configured_field(self, table: str, field: str, row_map: dict[str, Any]) -> Any:
        resolver = getattr(self, "field_mapping_resolver", None)
        if resolver is None:
            return None
        return resolver.resolve_field(table, field, row_map)

    def _prepare_production_order_data(self, item) -> tuple | None:
        """准备生产订单数据（新增 FCREATEDATE）
        字段顺序: FID, FBILLNO, FBILLTYPE, FDATE, FPRDORGID, FWORKSHOPID, FDocumentStatus, FCREATEDATE, FMODIFYDATE, FCANCELSTATUS
        """
        try:
            # 检查数据类型
            if isinstance(item, dict):
                # 字典格式字段
                fid = self._to_int_or_none(item.get("FID") or item.get("FId") or item.get("Id")) or 0
                fbillno = self._safe_str(item.get("FBILLNO") or item.get("FBillNo"))
                fbilltype = self._safe_str(
                    item.get("FBILLTYPE.FNAME")
                    or item.get("FBillTypeID.FName")
                    or item.get("FBILLTYPE")
                    or item.get("FBillTypeID")
                )
                fdate = self._parse_datetime(item.get("FDATE") or item.get("FDate"))
                fprdorgid = self._to_int_or_none(item.get("FPrdOrgId") or item.get("FPRDORGID")) or 0
                fworkshopid = (
                    self._to_int_or_none(item.get("FWORKSHOPID") or item.get("FWorkShopID") or item.get("FWorkshopID"))
                    or 0
                )
                fdocstatus = self._convert_production_status(
                    item.get("FDocumentStatus") or item.get("FDOCUMENTSTATUS") or item.get("FSTATUS")
                )
                if fdocstatus is None:
                    fdocstatus = ""
                fcreated = self._parse_datetime(item.get("FCREATEDATE") or item.get("FCreateDate"))
                fmodifydate = self._parse_datetime(item.get("FMODIFYDATE") or item.get("FModifyDate"))
                cancel_row = dict(item)
                cancel_row["FDocumentStatus"] = item.get("FDocumentStatus") or item.get("FDOCUMENTSTATUS") or item.get(
                    "FSTATUS"
                )
                fcancel = self._resolve_configured_field("prd_mo", "FCANCELSTATUS", cancel_row)
                if fcancel is None:
                    fcancel = item.get("FCANCELSTATUS") or item.get("FCancelStatus")
                fcancel = self._safe_str(fcancel)
                if fcancel is None:
                    fcancel = ""
                return (
                    fid,
                    fbillno,
                    fbilltype,
                    fdate,
                    fprdorgid,
                    fworkshopid,
                    fdocstatus,
                    fcreated,
                    fmodifydate,
                    fcancel,
                )
            if isinstance(item, list):
                # 列表格式数据
                if len(item) == 10:
                    # 新FieldKeys: FID, FBILLNO, FBILLTYPE.FNAME, FDATE, FPRDORGID, FWORKSHOPID, FDocumentStatus, FCREATEDATE, FModifyDate, FCancelStatus
                    fid = self._to_int_or_none(item[0]) or 0
                    fbillno = self._safe_str(item[1])
                    fbilltype = self._safe_str(item[2])
                    fdate = self._parse_datetime(item[3])
                    fprdorgid = self._to_int_or_none(item[4]) or 0
                    fworkshopid = self._to_int_or_none(item[5]) or 0
                    fdocstatus = self._convert_production_status(item[6])
                    if fdocstatus is None:
                        fdocstatus = ""
                    fcreated = self._parse_datetime(item[7])
                    fmodifydate = self._parse_datetime(item[8])
                    cancel_row = {
                        "FID": item[0],
                        "FBILLNO": item[1],
                        "FBILLTYPE.FNAME": item[2],
                        "FDATE": item[3],
                        "FPRDORGID": item[4],
                        "FWORKSHOPID": item[5],
                        "FDocumentStatus": item[6],
                        "FCREATEDATE": item[7],
                        "FModifyDate": item[8],
                        "FCancelStatus": item[9],
                    }
                    fcancel = self._resolve_configured_field("prd_mo", "FCANCELSTATUS", cancel_row)
                    if fcancel is None:
                        fcancel = item[9]
                    fcancel = self._safe_str(fcancel)
                    if fcancel is None:
                        fcancel = ""
                    return (
                        fid,
                        fbillno,
                        fbilltype,
                        fdate,
                        fprdorgid,
                        fworkshopid,
                        fdocstatus,
                        fcreated,
                        fmodifydate,
                        fcancel,
                    )
                if len(item) >= 16:  # 旧字段集（含 FMATERIALID 等）
                    # 仅提取新字段
                    fid = self._to_int_or_none(item[0]) or 0
                    fbillno = self._safe_str(item[3])
                    fbilltype = self._safe_str(item[4])
                    fdate = self._parse_datetime(item[8])
                    fprdorgid = self._to_int_or_none(item[18] if len(item) > 18 else None) or 0
                    fworkshopid = 0
                    fdocstatus = ""
                    fcreated = None
                    fmodifydate = self._parse_datetime(item[14])
                    cancel_row = {
                        "FID": item[0],
                        "FBILLNO": item[3],
                        "FBILLTYPE": item[4],
                        "FDATE": item[8],
                        "FModifyDate": item[14],
                        "FCANCELSTATUS": item[15],
                    }
                    fcancel = self._resolve_configured_field("prd_mo", "FCANCELSTATUS", cancel_row)
                    if fcancel is None:
                        fcancel = item[15]
                    fcancel = self._safe_str(fcancel)
                    if fcancel is None:
                        fcancel = ""
                    return (
                        fid,
                        fbillno,
                        fbilltype,
                        fdate,
                        fprdorgid,
                        fworkshopid,
                        fdocstatus,
                        fcreated,
                        fmodifydate,
                        fcancel,
                    )
                logger.warning(f"列表数据项不完整: {len(item)}")
                return None
            logger.warning(f"不支持的数据类型: {type(item)}")
            return None
        except Exception as e:
            logger.error(f"准备生产订单数据失败: {str(e)}")
            return None

    def _prepare_prd_moentry_data(self, item) -> tuple | None:
        """准备生产订单明细数据（PRD_MOENTRY，19字段，含源单、辅助数量、F_ora_Text1）"""
        try:
            if isinstance(item, dict):
                fid = self._to_int_or_none(item.get("FID")) or 0
                fentryid = self._to_int_or_none(item.get("FTreeEntity_FENTRYID") or item.get("FENTRYID")) or 0
                fseq = self._to_int_or_none(item.get("FTreeEntity_FSEQ") or item.get("FSEQ")) or 0
                # 源单编号：兼容不同返回命名（主表/明细、大小写差异）
                fsrcbillno = item.get("FSRCBILLNO") or item.get("FSrcBillNo") or item.get("FTreeEntity_FSrcBillNo")
                fsrcbillentryid = self._to_int_or_none(
                    item.get("FSRCBILLENTRYID")
                    or item.get("FSrcBillEntryId")
                    or item.get("FTreeEntity_FSrcBillEntryId")
                )
                fsaleorderno = self._safe_str(item.get("FSALEORDERNO") or item.get("FSaleOrderNo"))
                fmaterialid = self._to_int_or_none(item.get("FMATERIALID") or item.get("FMaterialId")) or 0
                fqty = self._to_decimal_or_none(item.get("FQTY") or item.get("FQty")) or 0.0
                # 修复: FSTOCKINQUAAUXQTY 不允许 NULL，默认为 0
                fstockinquauxqty = (
                    self._to_decimal_or_none(item.get("FSTOCKINQUAAUXQTY") or item.get("FStockInQuaAuxQty")) or 0.0
                )
                fplanstart = self._parse_datetime(
                    item.get("FPLANSTARTDATE") or item.get("FPlanStartDate")
                ) or self._parse_date(item.get("FPLANSTARTDATE") or item.get("FPlanStartDate"))
                fplanfinish = self._parse_datetime(
                    item.get("FPLANFINISHDATE") or item.get("FPlanFinishDate")
                ) or self._parse_date(item.get("FPLANFINISHDATE") or item.get("FPlanFinishDate"))
                fbomid = self._to_int_or_none(item.get("FBOMID") or item.get("FBomId")) or 0
                freqorg = self._to_int_or_none(item.get("FREQUESTORGID") or item.get("FRequestOrgId")) or 0
                fstockinorg = self._to_int_or_none(item.get("FSTOCKINORGID") or item.get("FStockInOrgId")) or 0
                fstockid = self._to_int_or_none(item.get("FSTOCKID") or item.get("FStockId")) or 0
                fworkshopid = (
                    self._to_int_or_none(item.get("FWORKSHOPID") or item.get("FWorkShopID") or item.get("FWorkshopID"))
                    or 0
                )
                fstatus = item.get("FSTATUS") or item.get("FStatus")
                fmodifydate = self._parse_datetime(item.get("FMODIFYDATE") or item.get("FModifyDate"))
                f_ora_text1 = self._safe_str(item.get("F_ora_Text1"))
                fmaterialnumber = self._safe_str(item.get("FMaterialId.FNumber"))
                fdescription = self._safe_str(item.get("FMaterialId.FDescription"))
                fsrcbillentryseq = self._to_int_or_none(item.get("FSRCBILLENTRYSEQ") or 0) or item.get(
                    "FSrcBillEntrySeq"
                )
                return (
                    fid,
                    fentryid,
                    fseq,
                    fsrcbillno,
                    fsrcbillentryseq,
                    fsrcbillentryid,
                    fsaleorderno,
                    fmaterialid,
                    fmaterialnumber,
                    fdescription,
                    fqty,
                    fstockinquauxqty,
                    fplanstart,
                    fplanfinish,
                    fbomid,
                    freqorg,
                    fstockinorg,
                    fstockid,
                    fworkshopid,
                    fstatus,
                    f_ora_text1,
                    fmodifydate,
                )
            if isinstance(item, (list, tuple)) and len(item) >= 18:
                f_ora_text1 = self._safe_str(item[18]) if len(item) > 18 else None
                fmaterialnumber = self._safe_str(item[19]) if len(item) > 19 else None
                fdescription = self._safe_str(item[20]) if len(item) > 20 else None
                fsrcbillentryseq = self._to_int_or_none(item[21]) if len(item) > 21 else None
                return (
                    self._to_int_or_none(item[0]) or 0,
                    self._to_int_or_none(item[1]) or 0,
                    self._to_int_or_none(item[2]) or 0,
                    item[3],
                    fsrcbillentryseq,
                    (self._to_int_or_none(item[4]) or 0),
                    self._safe_str(item[5]),
                    self._to_int_or_none(item[6]) or 0,
                    fmaterialnumber,
                    fdescription,
                    self._to_decimal_or_none(item[7]) or 0.0,
                    self._to_decimal_or_none(item[8]) or 0.0,
                    self._parse_datetime(item[9]) or self._parse_date(item[9]),
                    self._parse_datetime(item[10]) or self._parse_date(item[10]),
                    self._to_int_or_none(item[11]) or 0,
                    self._to_int_or_none(item[12]) or 0,
                    self._to_int_or_none(item[13]) or 0,
                    self._to_int_or_none(item[14]) or 0,
                    self._to_int_or_none(item[15]) or 0,
                    item[16],
                    f_ora_text1,
                    self._parse_datetime(item[17]),
                )
            logger.warning(f"生产订单明细不支持的数据类型: {type(item)}")
            return None
        except Exception as e:
            logger.error(f"准备生产订单明细数据失败: {str(e)}")
            return None

    def insert_prd_ppbom(self, data: list[dict]) -> int:
        return self.execute_writer("insert_prd_ppbom", data)

    def insert_prd_ppbom_entry(self, data: list[dict]) -> int:
        return self.execute_writer("insert_prd_ppbom_entry", data)

    def _prepare_prd_ppbom_entry_data(self, item) -> tuple | None:
        """准备生产用料清单明细行数据映射，兼容字典与列表格式。
        FieldKeys 顺序: FID,FEntity_FENTRYID,FEntity_FSEQ,FMOID,FMOBILLNO,FMOENTRYID,FMOENTRYSEQ,FBOMENTRYID,FMATERIALID2,FNEEDDATE2,
        FBASESTDQTY,FBASENEEDQTY,FBASEMUSTQTY,FSTDQTY,FNEEDQTY2,FMUSTQTY,FBASEPICKEDQTY,F_ORA_DATETIME,FMODIFYDATE
        映射到库: FID,FENTRYID,FSEQ,FMOID,FMOBILLNO,FMOENTRYID,FMOENTRYSEQ,FBOMENTRYID,FMATERIALID2,FNEEDDATE2,
        FBASESTDQTY,FBASENEEDQTY,FBASEMUSTQTY,FSTDQTY,FNEEDQTY2,FMUSTQTY,FBASEPICKEDQTY,FPLANEND,FMODIFYDATE
        兼容别名: F_ora_Datetime 等价于 FPLANEND（与 F_ORA_DATETIME 同义）。
        """
        try:
            if isinstance(item, dict):
                needdate2 = self._parse_datetime(item.get("FNEEDDATE2"))
                # FPLANEND 优先，其次兼容 F_ORA_DATETIME / F_ora_Datetime
                plan_end = self._parse_datetime(
                    item.get("FPLANEND") or item.get("F_ORA_DATETIME") or item.get("F_ora_Datetime")
                )
                modify_date = self._parse_datetime(item.get("FMODIFYDATE"))
                return (
                    (self._to_int_or_none(item.get("FID") or 0)),
                    (self._to_int_or_none(item.get("FEntity_FENTRYID") or 0) or item.get("FENTRYID")),
                    (self._to_int_or_none(item.get("FEntity_FSEQ") or 0) or item.get("FSEQ")),
                    (self._to_int_or_none(item.get("FMOID") or 0) or item.get("FMOID1")),
                    self._safe_str(item.get("FMOBILLNO") or item.get("FMOBILLNO1")),
                    (self._to_int_or_none(item.get("FMOENTRYID") or 0) or item.get("FMOENTRYID1")),
                    (self._to_int_or_none(item.get("FMOENTRYSEQ") or 0) or item.get("FMOENTRYSEQ1")),
                    (self._to_int_or_none(item.get("FBOMENTRYID") or 0)),
                    self._safe_str(item.get("FMATERIALID2") or item.get("FMATERIALID")),
                    needdate2,
                    (self._to_decimal_or_none(item.get("FBASESTDQTY") or 0.0)),
                    (self._to_decimal_or_none(item.get("FBASENEEDQTY") or 0.0)),
                    (self._to_decimal_or_none(item.get("FBASEMUSTQTY") or 0.0)),
                    (self._to_decimal_or_none(item.get("FSTDQTY") or 0.0)),
                    (self._to_decimal_or_none(item.get("FNEEDQTY2") or 0.0) or item.get("FNEEDQTY")),
                    (self._to_decimal_or_none(item.get("FMUSTQTY") or 0.0)),
                    (self._to_decimal_or_none(item.get("FBASEPICKEDQTY") or 0.0)),
                    plan_end,
                    modify_date,
                )
            if isinstance(item, list):
                if len(item) < 19:
                    logger.warning(f"列表数据项不完整: {len(item)}")
                    return None
                # 对应 FieldKeys 的位置映射
                needdate2 = self._parse_datetime(item[9]) if item[9] else None
                plan_end = self._parse_datetime(item[17]) if item[17] else None
                modify_date = self._parse_datetime(item[18]) if item[18] else None
                return (
                    (self._to_int_or_none(item[0]) or 0),  # FID
                    (self._to_int_or_none(item[1]) or 0),  # FENTRYID
                    (self._to_int_or_none(item[2]) or 0),  # FSEQ
                    (self._to_int_or_none(item[3]) or 0),  # FMOID
                    self._safe_str(item[4]),  # FMOBILLNO
                    (self._to_int_or_none(item[5]) or 0),  # FMOENTRYID
                    (self._to_int_or_none(item[6]) or 0),  # FMOENTRYSEQ
                    (self._to_int_or_none(item[7]) or 0),  # FBOMENTRYID
                    self._safe_str(item[8]),  # FMATERIALID2
                    needdate2,  # FNEEDDATE2
                    (self._to_decimal_or_none(item[10]) or 0.0),  # FBASESTDQTY
                    (self._to_decimal_or_none(item[11]) or 0.0),  # FBASENEEDQTY
                    (self._to_decimal_or_none(item[12]) or 0.0),  # FBASEMUSTQTY
                    (self._to_decimal_or_none(item[13]) or 0.0),  # FSTDQTY
                    (self._to_decimal_or_none(item[14]) or 0.0),  # FNEEDQTY2
                    (self._to_decimal_or_none(item[15]) or 0.0),  # FMUSTQTY
                    (self._to_decimal_or_none(item[16]) or 0.0),  # FBASEPICKEDQTY
                    plan_end,  # FPLANEND
                    modify_date,  # FMODIFYDATE
                )
            logger.warning(f"不支持的数据类型: {type(item)}")
            return None
        except Exception as e:
            logger.error(f"准备生产用料清单明细数据失败: {str(e)}")
            return None

    def insert_prd_ppbom_main(self, data: list[dict]) -> int:
        return self.execute_writer("insert_prd_ppbom_main", data)

    def _prepare_prd_ppbom_main_data(self, item) -> tuple | None:
        """准备生产用料清单主表行数据映射，兼容字典与列表格式"""
        try:
            if isinstance(item, dict):
                return (
                    self._to_int_or_none(item.get("FID")) or 0,
                    item.get("FBILLNO"),
                    self._to_int_or_none(item.get("FMATERIALID")) or 0,
                    self._to_int_or_none(item.get("FPrdOrgId") or item.get("FPRDORGID")) or 0,
                    self._to_int_or_none(item.get("FWorkShopID") or item.get("FWorkshopID")) or 0,
                    self._to_decimal_or_none(item.get("FBaseQty")) or 0.0,
                    self._parse_datetime(item.get("FCREATEDATE") or item.get("FCreateDate")),
                    self._parse_datetime(item.get("FModifyDate")),
                )
            if isinstance(item, list):
                if len(item) < 8:
                    logger.warning(f"列表数据项不完整: {len(item)}")
                    return None
                return (
                    self._to_int_or_none(item[0]) or 0,  # FID
                    item[1],  # FBILLNO
                    self._to_int_or_none(item[2]) or 0,  # FMATERIALID
                    self._to_int_or_none(item[3]) or 0,  # FPrdOrgId
                    self._to_int_or_none(item[4]) or 0,  # FWorkShopID
                    self._to_decimal_or_none(item[5]) or 0.0,  # FBaseQty
                    self._parse_datetime(item[6]),  # FCreateDate
                    self._parse_datetime(item[7]),  # FModifyDate
                )
            logger.warning(f"不支持的数据类型: {type(item)}")
            return None
        except Exception as e:
            logger.error(f"准备生产用料清单主表数据失败: {str(e)}")
            return None

    def _prepare_prd_ppbom_data(self, item) -> tuple | None:
        """准备生产用料清单主表插入行数据映射（与扩展 FieldKeys 对应）。
        FieldKeys 顺序: FID, FBILLNO, FMATERIALID, FPRDORGID, FWORKSHOPID, FBOMID, FBASEQTY, FQTY, FMOTYPE, FMOID, FMOBILLNO, FMOENTRYID, FMOENTRYSEQ, FDOCUMENTSTATUS, FCREATEDATE, FMODIFYDATE, FAPPROVEDATE, FSALEORDERID, FSALEORDERNO, FSALEORDERENTRYID, FSALEORDERENTRYSEQ
        支持字典或列表格式。
        """
        try:
            if isinstance(item, dict):
                fid = self._to_int_or_none(item.get("FID")) or 0
                fbillno = self._safe_str(item.get("FBILLNO"))
                fmaterialid = self._to_int_or_none(item.get("FMATERIALID")) or 0
                forg = self._to_int_or_none(item.get("FPrdOrgId") or item.get("FPRDORGID")) or 0
                fworkshopid = (
                    self._to_int_or_none(item.get("FWorkShopID") or item.get("FWORKSHOPID") or item.get("FWorkshopID"))
                    or 0
                )
                fbomid = self._to_int_or_none(item.get("FBOMID")) or 0
                fbaseqty = self._to_decimal_or_none(item.get("FBaseQty") or item.get("FBASEQTY")) or 0.0
                fqty = self._to_decimal_or_none(item.get("FQTY")) or 0.0
                fmotype = self._safe_str(item.get("FMOTYPE"))
                fmoid = self._to_int_or_none(item.get("FMOID")) or 0
                fmobillno = self._safe_str(item.get("FMOBILLNO"))
                fmoentryid = self._to_int_or_none(item.get("FMOENTRYID") or 0)
                fmoentryseq = self._to_int_or_none(item.get("FMOENTRYSEQ") or 0)
                fdocstatus = self._safe_str(item.get("FDOCUMENTSTATUS") or item.get("FDocumentStatus"))
                fcreatedate = self._parse_datetime(item.get("FCREATEDATE") or item.get("FCreateDate"))
                fmodify_dt = self._parse_datetime(item.get("FMODIFYDATE") or item.get("FModifyDate"))
                fapprovedate = self._parse_datetime(item.get("FAPPROVEDATE") or item.get("FApproveDate"))
                fsaleorderid = self._to_int_or_none(item.get("FSALEORDERID") or 0)
                fsaleorderno = self._safe_str(item.get("FSALEORDERNO"))
                fsaleorderentryid = self._to_int_or_none(item.get("FSALEORDERENTRYID") or 0)
                fsaleorderentryseq = self._to_int_or_none(item.get("FSALEORDERENTRYSEQ") or 0)
                return (
                    fid,
                    fbillno,
                    fmaterialid,
                    forg,
                    fworkshopid,
                    fbomid,
                    fbaseqty,
                    fqty,
                    fmotype,
                    fmoid,
                    fmobillno,
                    fmoentryid,
                    fmoentryseq,
                    fdocstatus,
                    fcreatedate,
                    fmodify_dt,
                    fapprovedate,
                    fsaleorderid,
                    fsaleorderno,
                    fsaleorderentryid,
                    fsaleorderentryseq,
                )
            if isinstance(item, list):
                if len(item) < 21:
                    logger.warning(f"列表数据项不完整: {len(item)}")
                    return None
                fid = self._to_int_or_none(item[0]) or 0
                fbillno = self._safe_str(item[1])
                fmaterialid = self._to_int_or_none(item[2]) or 0
                forg = self._to_int_or_none(item[3]) or 0
                fworkshopid = self._to_int_or_none(item[4]) or 0
                fbomid = self._to_int_or_none(item[5]) or 0
                fbaseqty = self._to_decimal_or_none(item[6]) or 0.0
                fqty = self._to_decimal_or_none(item[7]) or 0.0
                fmotype = self._safe_str(item[8])
                fmoid = self._to_int_or_none(item[9]) or 0
                fmobillno = self._safe_str(item[10])
                fmoentryid = self._to_int_or_none(item[11]) or 0
                fmoentryseq = self._to_int_or_none(item[12]) or 0
                fdocstatus = self._safe_str(item[13])
                fcreatedate = self._parse_datetime(str(item[14]) if item[14] else None)
                fmodify_dt = self._parse_datetime(str(item[15]) if item[15] else None)
                fapprovedate = self._parse_datetime(str(item[16]) if item[16] else None)
                fsaleorderid = self._to_int_or_none(item[17]) or 0
                fsaleorderno = self._safe_str(item[18])
                fsaleorderentryid = self._to_int_or_none(item[19]) or 0
                fsaleorderentryseq = self._to_int_or_none(item[20]) or 0
                return (
                    fid,
                    fbillno,
                    fmaterialid,
                    forg,
                    fworkshopid,
                    fbomid,
                    fbaseqty,
                    fqty,
                    fmotype,
                    fmoid,
                    fmobillno,
                    fmoentryid,
                    fmoentryseq,
                    fdocstatus,
                    fcreatedate,
                    fmodify_dt,
                    fapprovedate,
                    fsaleorderid,
                    fsaleorderno,
                    fsaleorderentryid,
                    fsaleorderentryseq,
                )
            logger.warning(f"不支持的数据类型: {type(item)}")
            return None
        except Exception as e:
            logger.error(f"准备生产用料清单主表数据失败: {str(e)}")
            return None

    def insert_sales_orders(self, data: list[dict]) -> int:
        return self.execute_writer("insert_sales_orders", data)

    def insert_sales_returnstock(self, data: list[dict]) -> int:
        return self.execute_writer("insert_sales_returnstock", data)

    def insert_sales_outstock(self, data: list[dict]) -> int:
        return self.execute_writer("insert_sales_outstock", data)

    def insert_delivery_notice(self, data: list[dict]) -> int:
        return self.execute_writer("insert_delivery_notice", data)

    def insert_prd_instock(self, data: list[dict]) -> int:
        return self.execute_writer("insert_prd_instock", data)

    def _prepare_prd_instock_data(self, item) -> tuple | None:
        """准备生产入库单数据
        目标字段顺序: FID, FENTRYID, FBILLNO, FDATE, FMATERIALID, FREALQTY, FSRCENTRYSEQ, FSRCBILLNO, FMoEntrySeq, FDOCUMENTSTATUS, FMoBillNo, FModifyDate
        支持字典/列表两种返回结构，并做必要的容错与类型转换
        """
        try:
            def mark_invalid() -> None:
                outcome = getattr(self, "_last_write_outcome", None)
                if outcome is not None:
                    outcome.invalid = int(getattr(outcome, "invalid", 0) or 0) + 1

            if isinstance(item, dict):
                raw_fid = item.get("FID") or item.get("FId") or item.get("Id")
                fid = self._to_int_or_none(raw_fid)
                # 明细行主键可能返回为 FEntity_FENTRYID 或 FENTRYID
                raw_fentryid = item.get("FEntity_FENTRYID") or item.get("FENTRYID")
                fentryid = self._to_int_or_none(raw_fentryid)
                if fid is None or fentryid is None:
                    billno = item.get("FBILLNO") or item.get("FBillNo")
                    logger.warning(
                        "生产入库单主键为空，已跳过: FID=%s(%s) FENTRYID=%s(%s) FBILLNO=%s",
                        raw_fid,
                        type(raw_fid).__name__,
                        raw_fentryid,
                        type(raw_fentryid).__name__,
                        billno,
                    )
                    mark_invalid()
                    return None
                billno = self._safe_str(item.get("FBILLNO") or item.get("FBillNo"))
                if billno is None:
                    logger.warning("生产入库单单号为空，已跳过: FID=%s FENTRYID=%s", fid, fentryid)
                    mark_invalid()
                    return None
                fdate = self._parse_datetime(item.get("FDATE") or item.get("FDate"))
                materialid = self._to_int_or_none(item.get("FMATERIALID") or 0) or item.get("FMaterialId")
                realqty = self._to_decimal_or_none(item.get("FREALQTY") or 0.0) or item.get("FRealQty")
                if realqty is None:
                    realqty = 0
                srcentryseq = self._to_int_or_none(item.get("FSRCENTRYSEQ") or 0) or item.get("FSrcEntrySeq")
                srcbillno = item.get("FSRCBILLNO") or item.get("FSrcBillNo")
                fmoentryseq = self._to_int_or_none(item.get("FMoEntrySeq") or 0) or item.get("FMOENTRYSEQ")
                fdocstatus = item.get("FDOCUMENTSTATUS") or item.get("FDocumentStatus")
                fmobillno = item.get("FMoBillNo") or item.get("FMOBILLNO")
                fmodify = self._parse_datetime(item.get("FModifyDate") or item.get("FMODIFYDATE"))
                return (
                    fid,
                    fentryid,
                    billno,
                    fdate,
                    materialid,
                    realqty,
                    srcentryseq,
                    srcbillno,
                    fmoentryseq,
                    fdocstatus,
                    fmobillno,
                    fmodify,
                )
            if isinstance(item, list) and len(item) >= 1:
                # 按 FieldKeys 顺序: FID,FEntity_FENTRYID,FBILLNO,FDATE,FMATERIALID,FREALQTY,FSrcEntrySeq,FSRCBILLNO,FMoEntrySeq,FDOCUMENTSTATUS,FMoBillNo,FModifyDate
                def get_item(i):
                    return item[i] if i < len(item) else None

                raw_fid = get_item(0)
                raw_fentryid = get_item(1)
                fid = self._to_int_or_none(raw_fid)
                fentryid = self._to_int_or_none(raw_fentryid)
                if fid is None or fentryid is None:
                    logger.warning(
                        "生产入库单主键为空，已跳过: FID=%s(%s) FENTRYID=%s(%s) len=%s",
                        raw_fid,
                        type(raw_fid).__name__,
                        raw_fentryid,
                        type(raw_fentryid).__name__,
                        len(item),
                    )
                    mark_invalid()
                    return None
                billno = self._safe_str(get_item(2))
                if billno is None:
                    logger.warning("生产入库单单号为空，已跳过: FID=%s FENTRYID=%s", fid, fentryid)
                    mark_invalid()
                    return None
                fdate = self._parse_datetime(get_item(3))
                materialid = self._to_int_or_none(get_item(4) or 0)
                realqty = self._to_decimal_or_none(get_item(5) or 0.0)
                if realqty is None:
                    realqty = 0
                srcentryseq = self._to_int_or_none(get_item(6) or 0)
                srcbillno = get_item(7)
                fmoentryseq = self._to_int_or_none(get_item(8) or 0)
                fdocstatus = get_item(9)
                fmobillno = get_item(10)
                fmodify = self._parse_datetime(get_item(11))
                return (
                    fid,
                    fentryid,
                    billno,
                    fdate,
                    materialid,
                    realqty,
                    srcentryseq,
                    srcbillno,
                    fmoentryseq,
                    fdocstatus,
                    fmobillno,
                    fmodify,
                )
            return None
        except Exception as e:
            logger.error(f"准备生产入库单数据失败: {str(e)}")
            return None

    def insert_forecast_orders(self, data: list[dict]) -> int:
        return self.execute_writer("insert_forecast_orders", data)

    def insert_purchase_order(self, data: list[dict]) -> int:
        return self.execute_writer("insert_purchase_order", data)

    def _prepare_purchase_order_data(self, item) -> tuple | None:
        """准备采购订单数据映射
        API→SQL字段映射：
        FID→FID，FPOOrderEntry_FENTRYID→FENTRYID，FBillNo→FBillNo，FDocumentStatus→FDocumentStatus，
        FSupplierId.FNAME→FSupplier，FPurchaseDeptId.FNAME→FPurchaseDept，F_ora_Assistant→F_ora_Assistant，
        FMaterialId.FNUMBER→FNUMBER，FMaterialId.FNAME→FNAME，FMaterialId.FSpecification→FSpecification，
        FQTY→FQTY，FCreateDate→FCreateDate，FModifyDate→FModifyDate，FApproveDate→FApproveDate
        """
        try:
            if isinstance(item, dict):
                fid = self._to_int_or_none(item.get("FID") or 0)
                fentryid = self._to_int_or_none(item.get("FPOOrderEntry_FENTRYID") or 0) or item.get("FENTRYID")
                billno = item.get("FBillNo") or item.get("FBILLNO")
                docstatus = item.get("FDocumentStatus") or item.get("FDOCUMENTSTATUS")
                supplier = (
                    item.get("FSupplierId.FNAME") or item.get("FSupplierId.FName") or item.get("FSUPPLIERID.FNAME")
                )
                dept = (
                    item.get("FPurchaseDeptId.FNAME")
                    or item.get("FPurchaseDeptId.FName")
                    or item.get("FPURCHASEDEPTID.FNAME")
                )
                assistant = item.get("F_ora_Assistant")
                fnumber = item.get("FMaterialId.FNUMBER") or item.get("FMaterialId.FNumber")
                fname = item.get("FMaterialId.FNAME") or item.get("FMaterialId.FName")
                fspec = item.get("FMaterialId.FSpecification") or item.get("FMaterialId.FSPECIFICATION")
                fqty = self._to_decimal_or_none(item.get("FQTY") or 0.0) or item.get("FQty")
                fcreate = self._parse_datetime(item.get("FCreateDate") or item.get("FCREATEDATE"))
                fmodify = self._parse_datetime(item.get("FModifyDate") or item.get("FMODIFYDATE"))
                fapprove = self._parse_datetime(item.get("FApproveDate") or item.get("FAPPROVEDATE"))
                if fid is None or fentryid is None:
                    return None
                return (
                    fid,
                    fentryid,
                    billno,
                    docstatus,
                    supplier,
                    dept,
                    assistant,
                    fnumber,
                    fname,
                    fspec,
                    fqty,
                    fcreate,
                    fmodify,
                    fapprove,
                )
            if isinstance(item, (list, tuple)) and len(item) >= 14:
                fid = self._to_int_or_none(item[0]) or 0
                fentryid = self._to_int_or_none(item[1]) or 0
                billno = item[2]
                docstatus = item[3]
                supplier = item[4]
                dept = item[5]
                assistant = item[6]
                fnumber = item[7]
                fname = item[8]
                fspec = item[9]
                fqty = self._to_decimal_or_none(item[10]) or 0.0
                fcreate = self._parse_datetime(item[11])
                fmodify = self._parse_datetime(item[12])
                fapprove = self._parse_datetime(item[13])
                if fid is None or fentryid is None:
                    return None
                return (
                    fid,
                    fentryid,
                    billno,
                    docstatus,
                    supplier,
                    dept,
                    assistant,
                    fnumber,
                    fname,
                    fspec,
                    fqty,
                    fcreate,
                    fmodify,
                    fapprove,
                )
            return None
        except Exception:
            return None

    def insert_sub_subreqorder(self, data: list[dict]) -> int:
        return self.execute_writer("insert_sub_subreqorder", data)

    def _prepare_sub_subreqorder_data(self, item) -> tuple | None:
        try:
            if isinstance(item, dict):
                fid = self._to_int_or_none(item.get("FID") or 0)
                fentryid = self._to_int_or_none(item.get("FTreeEntity_FENTRYID") or 0) or item.get("FENTRYID")
                fsrcbillno = item.get("FSrcBillNO") or item.get("FSrcBillNo")
                fsrcbillentryseq = self._to_int_or_none(item.get("FSRCBILLENTRYSEQ") or 0)
                fsrcbillentryid = self._to_int_or_none(item.get("FSRCBILLENTRYID") or 0)
                fsrcbillid = self._to_int_or_none(item.get("FSrcBillId") or 0) or item.get("FSRCBILLID")
                fbilltypename = item.get("FBillType.FNAME") or item.get("FBillType.FName")
                fbillno = item.get("FBillNo") or item.get("FBILLNO")
                fdate = self._parse_date(item.get("FDATE") or item.get("FDate"))
                fcustomer = self._safe_str(item.get("F_ora_Base") or item.get("F_ora_Base.FNAME"))
                fnumber = item.get("FMaterialId.FNUMBER") or item.get("FMaterialId.FNumber")
                fqty = self._to_decimal_or_none(item.get("FQty") or 0.0) or item.get("FQTY")
                fstockinqty = self._to_decimal_or_none(item.get("FStockInQty") or 0.0) or item.get("FSTOCKINQTY")
                fsupplier = item.get("FSupplierId.FNAME") or item.get("FSupplierId.FName")
                fmodify = self._parse_datetime(item.get("FModifyDate") or item.get("FMODIFYDATE"))
                fdocstatus = item.get("FDOCUMENTSTATUS") or item.get("FDocumentStatus")
                fdescription = self._safe_str(item.get("FMaterialId.FDescription"))
                if fid is None or fentryid is None:
                    return None
                return (
                    fid,
                    fentryid,
                    fsrcbillno,
                    fsrcbillentryseq,
                    fsrcbillentryid,
                    fsrcbillid,
                    fbilltypename,
                    fbillno,
                    fdate,
                    fcustomer,
                    fnumber,
                    fqty,
                    fstockinqty,
                    fsupplier,
                    fmodify,
                    fdocstatus,
                    fdescription,
                )
            if isinstance(item, (list, tuple)) and len(item) >= 16:
                fid = self._to_int_or_none(item[0]) or 0
                fentryid = self._to_int_or_none(item[1]) or 0
                fsrcbillno = item[2]
                fsrcbillentryseq = self._to_int_or_none(item[3]) or 0
                fsrcbillentryid = self._to_int_or_none(item[4]) or 0
                fsrcbillid = self._to_int_or_none(item[5]) or 0
                fbilltypename = item[6]
                fbillno = item[7]
                fdate = self._parse_date(item[8])
                fcustomer = self._safe_str(item[9])
                fnumber = item[10]
                fqty = self._to_decimal_or_none(item[11]) or 0.0
                fstockinqty = self._to_decimal_or_none(item[12]) or 0.0
                fsupplier = item[13]
                fmodify = self._parse_datetime(item[14])
                fdocstatus = item[15]
                fdescription = self._safe_str(item[16]) if len(item) > 16 else None
                if fid is None or fentryid is None:
                    return None
                return (
                    fid,
                    fentryid,
                    fsrcbillno,
                    fsrcbillentryseq,
                    fsrcbillentryid,
                    fsrcbillid,
                    fbilltypename,
                    fbillno,
                    fdate,
                    fcustomer,
                    fnumber,
                    fqty,
                    fstockinqty,
                    fsupplier,
                    fmodify,
                    fdocstatus,
                    fdescription,
                )
            return None
        except Exception:
            return None

    def insert_ap_payable(self, data: list[dict]) -> int:
        return self.execute_writer("insert_ap_payable", data)

    def insert_ar_receivable(self, data: list[dict]) -> int:
        return self.execute_writer("insert_ar_receivable", data)

    def _prepare_ar_receivable_data(self, item) -> tuple | None:
        """准备应收单数据 - 返回顺序必须与SQL字段顺序一致"""
        try:
            if isinstance(item, dict):
                fid = self._to_int_or_none(item.get("FID"))
                fentryid = self._to_int_or_none(item.get("FEntityDetail_FENTRYID") or item.get("FENTRYID"))
                fseq = self._to_int_or_none(item.get("FEntityDetail_FSEQ") or item.get("FSEQ"))
                fbillname = self._safe_str(
                    item.get("FBillTypeID.FNAME")
                    or item.get("FBillTypeID.FName")
                    or item.get("FBILLTYPEID.FNAME")
                    or item.get("FBILLTYPEID.FName")
                    or item.get("FBILLNAME")
                )
                fbillno = self._safe_str(item.get("FBillNo") or item.get("FBILLNO"))
                fdate = self._parse_date(item.get("FDATE") or item.get("FDate"))
                fcustomername = self._safe_str(item.get("FCUSTOMERID.FNAME") or item.get("FCUSTOMERID.FName") or item.get("FCUSTOMERNAME"))
                fsetaccounttype = self._safe_str(item.get("FSETACCOUNTTYPE") or item.get("FSetAccountType"))
                fbaseproperty1 = self._safe_str(item.get("F_ora_BaseProperty1") or item.get("FBASEPROPERTY1"))
                fmaterialnumber = self._safe_str(item.get("FMATERIALID.FNUMBER") or item.get("FMATERIALID.FNumber") or item.get("FMATERIALNUMBER"))
                fmaterialname = self._safe_str(item.get("FMATERIALID.FNAME") or item.get("FMATERIALID.FName") or item.get("FMATERIALNAME"))
                ftaxprice = self._to_decimal_or_none(item.get("FTaxPrice") or item.get("FTAXPRICE") or 0)
                fpriceqty = self._to_decimal_or_none(item.get("FPriceQty") or item.get("FPRICEQTY") or 0)
                fallamountfor_d = self._to_decimal_or_none(item.get("FALLAMOUNTFOR_D") or 0)
                fmodifydate = self._parse_datetime(item.get("FModifyDate") or item.get("FMODIFYDATE"))

                if fid is None or fentryid is None or fid <= 0 or fentryid <= 0:
                    return None
                return (
                    fid,
                    fentryid,
                    fseq,
                    fbillname,
                    fbillno,
                    fdate,
                    fcustomername,
                    fsetaccounttype,
                    fbaseproperty1,
                    fmaterialnumber,
                    fmaterialname,
                    ftaxprice,
                    fpriceqty,
                    fallamountfor_d,
                    fmodifydate,
                )
            if isinstance(item, (list, tuple)) and len(item) >= 15:
                fid = self._to_int_or_none(item[0])
                fentryid = self._to_int_or_none(item[1])
                fseq = self._to_int_or_none(item[2])
                fbillname = self._safe_str(item[3])
                fbillno = self._safe_str(item[4])
                fdate = self._parse_date(item[5])
                fcustomername = self._safe_str(item[6])
                fsetaccounttype = self._safe_str(item[7])
                fbaseproperty1 = self._safe_str(item[8])
                fmaterialnumber = self._safe_str(item[9])
                fmaterialname = self._safe_str(item[10])
                ftaxprice = self._to_decimal_or_none(item[11]) or 0
                fpriceqty = self._to_decimal_or_none(item[12]) or 0
                fallamountfor_d = self._to_decimal_or_none(item[13]) or 0
                fmodifydate = self._parse_datetime(item[14])

                if fid is None or fentryid is None or fid <= 0 or fentryid <= 0:
                    return None
                return (
                    fid,
                    fentryid,
                    fseq,
                    fbillname,
                    fbillno,
                    fdate,
                    fcustomername,
                    fsetaccounttype,
                    fbaseproperty1,
                    fmaterialnumber,
                    fmaterialname,
                    ftaxprice,
                    fpriceqty,
                    fallamountfor_d,
                    fmodifydate,
                )
            return None
        except Exception:
            return None

    def _ensure_additional_columns_for_ap_payable(self) -> None:
        """确保 AP_Payable 存在应付单扩展字段与金额字段列。"""
        try:
            table = "AP_Payable"
            is_sqlserver = getattr(self, "db_type", "mysql") == "sqlserver"
            if is_sqlserver:
                self.cursor.execute(
                    "SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=?",
                    (table,),
                )
            else:
                self.cursor.execute(
                    "SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=%s",
                    (table,),
                )

            existing: dict[str, str] = {}
            for row in self.cursor.fetchall() or []:
                if isinstance(row, dict):
                    col = row.get("COLUMN_NAME")
                    data_type = row.get("DATA_TYPE")
                else:
                    col = row[0] if row else None
                    data_type = row[1] if row and len(row) > 1 else None
                if col:
                    existing[str(col).strip().upper()] = str(data_type or "").strip().lower()

            needed_decimal_cols = ["FALLAMOUNTFOR_D", "FNOTAXAMOUNTFOR", "FDISCOUNTAMOUNTFOR"]
            for col in needed_decimal_cols:
                if col in existing:
                    continue
                try:
                    if is_sqlserver:
                        self.cursor.execute(f"ALTER TABLE {table} ADD {col} DECIMAL(23,10) NULL")
                    else:
                        self.cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} DECIMAL(23,10) NULL")
                    logger.info(f"[AP_Payable] 已添加列 {col}")
                except Exception as e:
                    logger.warning(f"[AP_Payable] 添加列 {col} 失败或已存在: {e}")

            string_columns = {
                "FBILLNAME": ("NVARCHAR(255)", "VARCHAR(255)"),
                "FBILLNO": ("NVARCHAR(80)", "VARCHAR(80)"),
                "FCUSTOMER": ("NVARCHAR(255)", "VARCHAR(255)"),
                "FMATERIALNAME": ("NVARCHAR(255)", "VARCHAR(255)"),
            }
            for col, (sqlserver_type, mysql_type) in string_columns.items():
                col_type = existing.get(col)
                try:
                    if col_type is None:
                        if is_sqlserver:
                            self.cursor.execute(f"ALTER TABLE {table} ADD {col} {sqlserver_type} NULL")
                        else:
                            self.cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {mysql_type} NULL")
                        logger.info(f"[AP_Payable] 已添加列 {col}")
                    elif is_sqlserver and col_type != "nvarchar":
                        self.cursor.execute(f"ALTER TABLE {table} ALTER COLUMN {col} {sqlserver_type} NULL")
                        logger.info(f"[AP_Payable] 已将 {col} 调整为 {sqlserver_type}")
                    elif (not is_sqlserver) and col_type != "varchar":
                        self.cursor.execute(f"ALTER TABLE {table} MODIFY COLUMN {col} {mysql_type} NULL")
                        logger.info(f"[AP_Payable] 已将 {col} 调整为 {mysql_type}")
                except Exception as e:
                    logger.warning(f"[AP_Payable] 处理列 {col} 失败: {e}")

            seq_type = existing.get("FSEQ")
            try:
                if seq_type is None:
                    if is_sqlserver:
                        self.cursor.execute(f"ALTER TABLE {table} ADD FSEQ INT NULL")
                    else:
                        self.cursor.execute(f"ALTER TABLE {table} ADD COLUMN FSEQ INT NULL")
                    logger.info("[AP_Payable] 已添加列 FSEQ")
            except Exception as e:
                logger.warning(f"[AP_Payable] 处理列 FSEQ 失败: {e}")

            try:
                self.connection.commit()
            except Exception:
                pass
            self._invalidate_table_metadata_cache(table)
        except Exception as e:
            logger.debug(f"[AP_Payable] 检查/补列失败: {e}")

    def _prepare_ap_payable_data(self, item) -> tuple | None:
        """准备应付单数据 - 返回顺序必须与SQL字段顺序一致"""
        try:
            if isinstance(item, dict):
                fid = self._to_int_or_none(item.get("FID"))
                fentryid = self._to_int_or_none(item.get("FEntityDetail_FENTRYID") or item.get("FENTRYID"))
                fseq = self._to_int_or_none(item.get("FEntityDetail_FSEQ") or item.get("FSEQ"))
                fbillname = self._safe_str(
                    item.get("FBillTypeID.FNAME")
                    or item.get("FBillTypeID.FName")
                    or item.get("FBILLTYPEID.FNAME")
                    or item.get("FBILLTYPEID.FName")
                    or item.get("FBILLNAME")
                )
                fbillno = self._safe_str(item.get("FBillNo") or item.get("FBILLNO"))
                fdate = self._parse_date(item.get("FDATE"))
                fpurchasename = self._safe_str(item.get("FPURCHASEORGID.FNAME") or item.get("FPURCHASEORGID.FName"))
                fcustomer = self._safe_str(item.get("F_ora_Base1.FNAME") or item.get("F_ora_Base1.FName") or item.get("FCUSTOMER"))
                fsuppliername = self._safe_str(item.get("FSUPPLIERID.FNAME") or item.get("FSUPPLIERID.FName"))
                fsetaccounttype = self._safe_str(item.get("FSETACCOUNTTYPE"))
                fmaterialnumber = self._safe_str(item.get("FMATERIALID.FNUMBER") or item.get("FMATERIALID.FNumber"))
                fmaterialname = self._safe_str(item.get("FMATERIALID.FNAME") or item.get("FMATERIALID.FName") or item.get("FMATERIALNAME"))
                fpriceunitname = self._safe_str(item.get("FPRICEUNITID.FNAME") or item.get("FPRICEUNITID.FName"))
                fpriceqty = self._to_decimal_or_none(item.get("FPRICEQTY") or 0)
                fallamountfor_d = self._to_decimal_or_none(item.get("FALLAMOUNTFOR_D") or 0)
                fnotaxamountfor = self._resolve_configured_field("ap_payable", "FNOTAXAMOUNTFOR", item)
                if fnotaxamountfor is None:
                    fnotaxamountfor = item.get("FNoTaxAmountFor_D") or item.get("FNOTAXAMOUNTFOR_D") or 0
                fnotaxamountfor = self._to_decimal_or_none(fnotaxamountfor)
                fdiscountamountfor = self._to_decimal_or_none(item.get("FDISCOUNTAMOUNTFOR") or 0)
                fentrydiscountrate = self._to_decimal_or_none(item.get("FENTRYDISCOUNTRATE"))
                fentrytaxrate = self._to_decimal_or_none(item.get("FENTRYTAXRATE"))
                fmodifydate = self._parse_datetime(item.get("FModifyDate") or item.get("FMODIFYDATE"))

                if fid is None or fentryid is None or fid <= 0 or fentryid <= 0:
                    return None
                # 返回顺序: FID, FENTRYID, FSEQ, FBILLNAME, FBILLNO, FDATE, FPURCHASEORGNAME, FCUSTOMER,
                #           FSUPPLIERNAME, FSETACCOUNTTYPE, FMATERIALNUMBER, FMATERIALNAME, FPRICEUNITNAME,
                #           FPRICEQTY, FALLAMOUNTFOR_D, FNOTAXAMOUNTFOR, FDISCOUNTAMOUNTFOR, FENTRYDISCOUNTRATE, FENTRYTAXRATE, FModifyDate
                return (
                    fid,
                    fentryid,
                    fseq,
                    fbillname,
                    fbillno,
                    fdate,
                    fpurchasename,
                    fcustomer,
                    fsuppliername,
                    fsetaccounttype,
                    fmaterialnumber,
                    fmaterialname,
                    fpriceunitname,
                    fpriceqty,
                    fallamountfor_d,
                    fnotaxamountfor,
                    fdiscountamountfor,
                    fentrydiscountrate,
                    fentrytaxrate,
                    fmodifydate,
                )
            if isinstance(item, (list, tuple)) and len(item) >= 20:
                fid = self._to_int_or_none(item[0])
                fentryid = self._to_int_or_none(item[1])
                fseq = self._to_int_or_none(item[2])
                fbillname = self._safe_str(item[3])
                fbillno = self._safe_str(item[4])
                fdate = self._parse_date(item[5])
                fpurchasename = self._safe_str(item[6])
                fcustomer = self._safe_str(item[7])
                fsuppliername = self._safe_str(item[8])
                fsetaccounttype = self._safe_str(item[9])
                fmaterialnumber = self._safe_str(item[10])
                fmaterialname = self._safe_str(item[11])
                fpriceunitname = self._safe_str(item[12])
                fpriceqty = self._to_decimal_or_none(item[13]) or 0
                fallamountfor_d = self._to_decimal_or_none(item[14]) or 0
                notax_row = {
                    "FNOTAXAMOUNTFOR_D": item[15],
                    "FNOTAXAMOUNTFOR": item[20] if len(item) > 20 else None,
                }
                fnotaxamountfor = self._resolve_configured_field("ap_payable", "FNOTAXAMOUNTFOR", notax_row)
                if fnotaxamountfor is None:
                    fnotaxamountfor = item[15]
                fnotaxamountfor = self._to_decimal_or_none(fnotaxamountfor) or 0
                fdiscountamountfor = self._to_decimal_or_none(item[16]) or 0
                fentrydiscountrate = self._to_decimal_or_none(item[17])
                fentrytaxrate = self._to_decimal_or_none(item[18])
                fmodifydate = self._parse_datetime(item[19])

                if fid is None or fentryid is None or fid <= 0 or fentryid <= 0:
                    return None
                return (
                    fid,
                    fentryid,
                    fseq,
                    fbillname,
                    fbillno,
                    fdate,
                    fpurchasename,
                    fcustomer,
                    fsuppliername,
                    fsetaccounttype,
                    fmaterialnumber,
                    fmaterialname,
                    fpriceunitname,
                    fpriceqty,
                    fallamountfor_d,
                    fnotaxamountfor,
                    fdiscountamountfor,
                    fentrydiscountrate,
                    fentrytaxrate,
                    fmodifydate,
                )
            return None
        except Exception:
            return None

    # 已移除生产用料清单插入方法
    def _prepare_sales_order_data(self, item) -> tuple | None:
        """准备销售订单数据
        目标字段顺序:
        FID, FENTRYID, FSEQ, FBILLTYPENAME, FBILLNO, FDATE, FCUSTNAME,
        FSALEORONAME, FCUSTGROUP, FMATERIALID, FMATERIALNAME, FMATERIALNUMBER, FMATERIALTYPE,
        FMATERIALSORT, FDESCRIPTION, FQTY, FCloseStatus, FDeliveryDate, FModifyDate, FStockOutQty,
        FMrpCloseStatus, FDOCUMENTSTATUS, SYNC_TIME
        """
        try:
            # 检查数据类型
            if isinstance(item, dict):
                # 字典格式数据
                fid_val = self._to_int_or_none(item.get("FID") or 0)
                fentry_val = item.get("FSaleOrderEntry_FENTRYID")
                if fid_val is None or fentry_val is None:
                    logger.warning("销售订单记录缺少关键主键(FID或FENTRYID)，已跳过: %s", item)
                    return None
                fseq_val = self._to_int_or_none(item.get("FSaleOrderEntry_FSEQ") or 0) or item.get("FSEQ")
                fdescription = (
                    item.get("FDescription")
                    or item.get("FSaleOrderEntry_FDescription")
                    or item.get("FMaterialId.FDescription")
                )
                sync_time = datetime.now()
                return (
                    fid_val,
                    fentry_val,
                    fseq_val,
                    item.get("FBillTypeID.FName"),
                    item.get("FBillNo"),
                    self._parse_date(item.get("FDate")),
                    item.get("FCustId.FName"),
                    item.get("FSaleOrgId.FName"),
                    item.get("FCustId.FGROUP"),
                    (self._to_int_or_none(item.get("FMaterialId") or 0)),
                    item.get("FMaterialId.FName"),
                    item.get("FMaterialId.FNumber"),
                    item.get("FMaterialId.F_ora_Text_qtr"),
                    item.get("FMaterialId.FBarcode"),
                    fdescription,
                    item.get("FQTY"),
                    item.get("FCloseStatus"),
                    self._parse_date(item.get("FDeliveryDate")),
                    self._parse_datetime(item.get("FModifyDate")),
                    item.get("FStockOutQty"),
                    item.get("FMrpCloseStatus"),
                    item.get("FDocumentStatus"),
                    sync_time,
                )
            if isinstance(item, list) and len(item) >= 1:
                # 列表格式数据（金蝶API直接返回的数组格式），容错处理长度不足
                def get_item(i):
                    return item[i] if i < len(item) else None

                fid_val = self._to_int_or_none(get_item(0) or 0)
                fentry_val = get_item(1)
                if fid_val is None or fentry_val is None:
                    logger.warning("销售订单记录缺少关键主键(FID或FENTRYID)，已跳过: %s", item)
                    return None
                sync_time = datetime.now()
                return (
                    fid_val,
                    fentry_val,
                    (self._to_int_or_none(get_item(2) or 0)),
                    get_item(3),
                    get_item(4),
                    self._parse_date(str(get_item(5)) if get_item(5) else None),
                    get_item(6),
                    get_item(7),
                    get_item(8),
                    (self._to_int_or_none(get_item(9) or 0)),
                    get_item(10),
                    get_item(11),
                    get_item(12),
                    get_item(13),
                    get_item(14),
                    get_item(15),
                    get_item(16),
                    self._parse_date(str(get_item(17)) if get_item(17) else None),
                    self._parse_datetime(str(get_item(18)) if get_item(18) else None),
                    get_item(19),
                    get_item(20),
                    get_item(21),
                    sync_time,
                )
            logger.warning(f"不支持的数据类型或列表数据项不足: {type(item)}")
            return None
        except Exception as e:
            logger.error(f"准备销售订单数据失败: {str(e)}, 数据: {item}")
            return None

    def _ensure_additional_columns_for_saleorder(self) -> None:
        """确保 saleorder 表存在新增的字段：FMATERIALID、FDOCUMENTSTATUS。
        - SQL Server 添加：FMATERIALID INT NULL，FDOCUMENTSTATUS NVARCHAR(64) NULL
        - MySQL 添加：FMATERIALID INT NULL，FDOCUMENTSTATUS VARCHAR(64) NULL
        """
        try:
            table = "saleorder"
            is_sqlserver = getattr(self, "db_type", "mysql") == "sqlserver"
            # 读取现有列
            if is_sqlserver:
                self.cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=?", (table,))
            else:
                self.cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=%s", (table,))
            existing = {str(r[0]).strip().upper() for r in self.cursor.fetchall() if r and r[0] is not None}
            to_add = []
            if "FMATERIALID" not in existing:
                to_add.append("FMATERIALID")
            if "FDOCUMENTSTATUS" not in existing:
                to_add.append("FDOCUMENTSTATUS")
            for col in to_add:
                try:
                    if col == "FMATERIALID":
                        if is_sqlserver:
                            self.cursor.execute("ALTER TABLE saleorder ADD FMATERIALID INT NULL")
                        else:
                            self.cursor.execute("ALTER TABLE saleorder ADD COLUMN FMATERIALID INT NULL")
                    elif col == "FDOCUMENTSTATUS":
                        if is_sqlserver:
                            self.cursor.execute("ALTER TABLE saleorder ADD FDOCUMENTSTATUS NVARCHAR(64) NULL")
                        else:
                            self.cursor.execute("ALTER TABLE saleorder ADD COLUMN FDOCUMENTSTATUS VARCHAR(64) NULL")
                except Exception as e:
                    logger.warning(f"[saleorder] 添加列 {col} 失败或已存在：{e}")
            try:
                self.connection.commit()
            except Exception:
                pass
        except Exception as e:
            # 非致命：记录日志即可
            logger.debug(f"检查/添加 saleorder 列失败：{e}")

    def _ensure_additional_columns_for_customer(self) -> None:
        """确保 customer 存在当前同步依赖的扩展字段。"""
        try:
            table = "customer"
            column = "FCUSTPYPE"
            is_sqlserver = getattr(self, "db_type", "mysql") == "sqlserver"

            if is_sqlserver:
                self.cursor.execute(
                    "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=? AND COLUMN_NAME=?",
                    (table, column),
                )
            else:
                self.cursor.execute(
                    "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=%s AND COLUMN_NAME=%s",
                    (table, column),
                )

            if self.cursor.fetchone():
                return

            if is_sqlserver:
                self.cursor.execute(f"ALTER TABLE {table} ADD {column} NVARCHAR(255) NULL")
            else:
                self.cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} VARCHAR(255) NULL")

            try:
                self.connection.commit()
            except Exception:
                pass
            self._invalidate_table_metadata_cache(table)
            logger.info(f"已为 {table}.{column} 创建字段")
        except Exception as e:
            logger.debug(f"检查或新增 customer 扩展字段失败: {e}")

    def _ensure_additional_columns_for_bd_material(self) -> None:
        """确保 bd_material 存在当前同步依赖的扩展字段。"""
        try:
            table = "bd_material"
            column = "F_ORA_TEXT_9SB"
            is_sqlserver = getattr(self, "db_type", "mysql") == "sqlserver"

            if is_sqlserver:
                self.cursor.execute(
                    "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=? AND COLUMN_NAME=?",
                    (table, column),
                )
            else:
                self.cursor.execute(
                    "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=%s AND COLUMN_NAME=%s",
                    (table, column),
                )

            if self.cursor.fetchone():
                return

            if is_sqlserver:
                self.cursor.execute(f"ALTER TABLE {table} ADD {column} NVARCHAR(50) NULL")
            else:
                self.cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} VARCHAR(50) NULL")

            try:
                self.connection.commit()
            except Exception:
                pass
            self._invalidate_table_metadata_cache(table)
            logger.info(f"已为 {table}.{column} 创建字段")
        except Exception as e:
            logger.debug(f"检查或新增 bd_material 扩展字段失败: {e}")

    def _ensure_additional_columns_for_eng_bomchild(self) -> None:
        """确保 eng_bomchild 存在当前同步依赖的扩展字段。"""
        try:
            table = "eng_bomchild"
            is_sqlserver = getattr(self, "db_type", "mysql") == "sqlserver"
            for column in ("FCHILDNUMBER", "FCHILDNAME"):
                if is_sqlserver:
                    self.cursor.execute(
                        "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=? AND COLUMN_NAME=?",
                        (table, column),
                    )
                else:
                    self.cursor.execute(
                        "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=%s AND COLUMN_NAME=%s",
                        (table, column),
                    )

                if self.cursor.fetchone():
                    continue

                if is_sqlserver:
                    self.cursor.execute(f"ALTER TABLE {table} ADD {column} NVARCHAR(255) NULL")
                else:
                    self.cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} VARCHAR(255) NULL")

                try:
                    self.connection.commit()
                except Exception:
                    pass
                self._invalidate_table_metadata_cache(table)
                logger.info(f"已为 {table}.{column} 创建字段")
        except Exception as e:
            logger.error(f"检查或新增 eng_bomchild 扩展字段失败: {e}")

    def _ensure_bd_material_group_text_column(self) -> None:
        """确保 bd_material.FMATERIALGROUP 为可存中文的字符串列。"""
        try:
            table = "bd_material"
            column = "FMATERIALGROUP"
            is_sqlserver = getattr(self, "db_type", "mysql") == "sqlserver"

            if is_sqlserver:
                self.cursor.execute(
                    """
                    SELECT DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = ? AND COLUMN_NAME = ?
                    """,
                    (table, column),
                )
            else:
                self.cursor.execute(
                    """
                    SELECT DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = %s AND COLUMN_NAME = %s
                    """,
                    (table, column),
                )

            row = self.cursor.fetchone()
            if not row:
                if is_sqlserver:
                    self.cursor.execute(f"ALTER TABLE {table} ADD {column} NVARCHAR(255) NULL")
                else:
                    self.cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} VARCHAR(255) NULL")
                try:
                    self.connection.commit()
                except Exception:
                    pass
                logger.info(f"已为 {table}.{column} 创建字符串列")
                return

            if isinstance(row, dict):
                data_type = row.get("DATA_TYPE")
                char_len = row.get("CHARACTER_MAXIMUM_LENGTH")
            else:
                data_type = row[0] if len(row) > 0 else None
                char_len = row[1] if len(row) > 1 else None

            data_type = str(data_type or "").lower()
            try:
                char_len = int(char_len) if char_len is not None else None
            except Exception:
                char_len = None

            numeric_types = {
                "int",
                "bigint",
                "smallint",
                "tinyint",
                "numeric",
                "decimal",
                "float",
                "real",
                "money",
                "smallmoney",
            }
            mysql_text_types = {"varchar", "char", "text", "tinytext", "mediumtext", "longtext"}
            sqlserver_text_types = {"nvarchar", "nchar", "varchar", "char", "text", "ntext"}

            needs_alter = False
            if is_sqlserver:
                if data_type in numeric_types:
                    needs_alter = True
                elif data_type not in sqlserver_text_types:
                    needs_alter = True
                elif data_type != "nvarchar":
                    needs_alter = True
                elif char_len not in (None, -1) and char_len < 255:
                    needs_alter = True
            else:
                if data_type not in mysql_text_types:
                    needs_alter = True
                elif data_type in {"varchar", "char"} and char_len not in (None, -1) and char_len < 255:
                    needs_alter = True

            if not needs_alter:
                return

            if is_sqlserver:
                try:
                    self.cursor.execute(
                        """
                        SELECT i.name
                        FROM sys.indexes i
                        JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
                        JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
                        WHERE i.object_id = OBJECT_ID('bd_material')
                          AND c.name = ?
                          AND i.is_primary_key = 0
                          AND i.is_unique_constraint = 0
                        """,
                        (column,),
                    )
                    for idx_row in self.cursor.fetchall() or []:
                        idx_name = idx_row.get("name") if isinstance(idx_row, dict) else (idx_row[0] if idx_row else None)
                        if idx_name:
                            self.cursor.execute(f"DROP INDEX {idx_name} ON {table}")
                    try:
                        self.connection.commit()
                    except Exception:
                        pass
                except Exception as e:
                    logger.warning(f"清理 {table}.{column} 关联索引失败: {e}")

                try:
                    self.cursor.execute(
                        """
                        SELECT dc.name
                        FROM sys.default_constraints dc
                        JOIN sys.columns c
                          ON dc.parent_object_id = c.object_id
                         AND dc.parent_column_id = c.column_id
                        WHERE dc.parent_object_id = OBJECT_ID(?)
                          AND c.name = ?
                        """,
                        (table, column),
                    )
                    for dc_row in self.cursor.fetchall() or []:
                        dc_name = dc_row.get("name") if isinstance(dc_row, dict) else (dc_row[0] if dc_row else None)
                        if dc_name:
                            self.cursor.execute(f"ALTER TABLE {table} DROP CONSTRAINT {dc_name}")
                    try:
                        self.connection.commit()
                    except Exception:
                        pass
                except Exception as e:
                    logger.warning(f"清理 {table}.{column} 默认约束失败: {e}")

                self.cursor.execute(f"ALTER TABLE {table} ALTER COLUMN {column} NVARCHAR(255) NULL")
            else:
                self.cursor.execute(f"ALTER TABLE {table} MODIFY COLUMN {column} VARCHAR(255) NULL")

            try:
                self.connection.commit()
            except Exception:
                pass
            logger.info(f"已将 {table}.{column} 调整为字符串类型")
        except Exception as e:
            logger.warning(f"检查或调整 bd_material.FMATERIALGROUP 类型失败: {e}")

    def _prepare_sales_returnstock_data(self, item) -> tuple | None:
        """准备销售退货单数据
        按照数据库字段顺序: FENTRYID, FBILLNO, FDATE, FRetcustNAME, FRetcustGROUP, FSalesManNAME,
        FReturnType, FRealQty, FMaterialNAME, FMaterialFNUMBER, FMaterialTYPE,
        FMaterialSort, FDeliveryDate, FModifyDate
        """
        try:
            if isinstance(item, dict):
                return (
                    item.get("FEntity_FENTRYID"),  # FENTRYID
                    item.get("FBillNo"),  # FBILLNO
                    self._parse_date(item.get("FDATE")),  # FDATE
                    item.get("FRetcustId.FNAME"),  # FRetcustNAME
                    item.get("FRetcustId.FGROUP"),  # FRetcustGROUP
                    item.get("FSalesManId.FNAME"),  # FSalesManNAME
                    item.get("F_ora_Assistant1.FDataValue"),  # FReturnType
                    item.get("FRealQty"),  # FRealQty
                    item.get("FMaterialId.FNAME"),  # FMaterialNAME
                    item.get("FMaterialId.FNUMBER"),  # FMaterialFNUMBER
                    item.get("FMaterialId.F_ora_Text_qtr"),  # FMaterialTYPE
                    item.get("FMaterialId.FBarcode"),  # FMaterialSort
                    self._parse_date(item.get("FDeliveryDate")),  # FDeliveryDate
                    self._parse_datetime(item.get("FModifyDate")),  # FModifyDate
                )
            if isinstance(item, list) and len(item) >= 13:
                return (
                    item[0],  # FENTRYID
                    item[1],  # FBILLNO
                    self._parse_date(str(item[2]) if item[2] else None),  # FDATE
                    item[3],  # FCUSTNAME
                    item[4],  # FCUSTGROUP
                    item[5],  # FSALERNAME
                    item[6],  # FCHANGETYPE
                    item[7],  # FQTY
                    item[8],  # FMATERIALNUMBER
                    item[9],  # FMATERIALNAME
                    item[10],  # F_MaterialTYPE
                    item[11],  # FMATERIALSORT
                    self._parse_date(str(item[12]) if item[12] else None),  # FDELIVERYDATE
                    self._parse_datetime(str(item[13]) if len(item) > 13 and item[13] else None),  # FMODIFYDATE
                )
            logger.warning(f"不支持的数据类型或列表数据项不足: {type(item)}")
            return None
        except Exception as e:
            logger.warning(f"准备销售退货单数据失败: {e}")
            return None

    def _prepare_sales_outstock_data(self, item) -> tuple | None:
        """准备销售出库单数据
        按照数据库字段顺序: FENTRYID, FSEQ, FBILLTYPENAME, FBILLNO, FDATE, FCUSTNAME,
        FSALEORGNAME, FCUSTGROUP, FREALQTY, FMATERIALNAME, FMATERIALNUMBER,
        FMATERIALTYPE, FMATERIALSORT, FSRCBILLNO, FMODIFYDATE, SYNC_TIME, FDESCRIPTION
        """
        try:
            # 检查数据类型
            if isinstance(item, dict):
                # 字典格式数据
                sync_time = datetime.now()
                return (
                    item.get("FEntity_FENTRYID") or item.get("FENTRYID"),
                    (self._to_int_or_none(item.get("FEntity_FSEQ") or 0) or item.get("FSEQ")),
                    item.get("FBillTypeID.FName"),
                    item.get("FBillNO"),
                    self._parse_date(item.get("FDate")),
                    item.get("FCustomerID.FNAME"),
                    item.get("FSaleOrgId.FNAME"),
                    item.get("FCustomerID.FGROUP"),
                    item.get("FRealQty"),
                    item.get("FMaterialID.FNAME"),
                    item.get("FMaterialID.FNUMBER"),
                    item.get("FMaterialID.F_ora_Text_qtr"),
                    item.get("FMaterialID.FBarcode"),
                    item.get("FSRCBILLNO") or item.get("FSrcBillNo"),
                    self._parse_datetime(item.get("FModifyDate")),
                    sync_time,
                    item.get("FMaterialID.FDescription"),
                )
            if isinstance(item, list) and len(item) >= 15:
                # 列表格式数据（金蝶 API 直接返回的数组格式）
                # 根据 FieldKeys 的顺序映射到数据库字段
                sync_time = datetime.now()
                return (
                    item[0],
                    (self._to_int_or_none(item[1]) or 0),
                    item[2],
                    item[3],
                    self._parse_date(str(item[4]) if item[4] else None),
                    item[5],
                    item[6],
                    item[7],
                    item[8],
                    item[9],
                    item[10],
                    item[11],
                    item[12],
                    item[13],
                    self._parse_datetime(str(item[14]) if item[14] else None),
                    sync_time,
                    item[15] if len(item) > 15 else None,
                )
            logger.warning(f"不支持的数据类型或列表数据项不足: {type(item)}")
            return None
        except Exception as e:
            logger.error(f"准备销售出库单数据失败: {str(e)}, 数据: {item}")
            return None

    def _prepare_forecast_order_data(self, item) -> tuple | None:
        """准备预测订单数据
        按照数据库字段顺序: FENTRYID, FBILLNO, FFOREORGNAME, FCUSTNAME, FCUSTGROUP, FMATERIALNAME,
        FMATERIALNUMBER, FQTY, FORA_BASE_FNAME, FORA_BASEPROPERTY_CA9, FORA_BASEPROPERTY_UKY,
        FDATE, FMODIFYDATE, F_ORA_DATE, FDescription
        """
        try:
            # 检查数据类型
            if isinstance(item, dict):
                # 字典格式数据
                return (
                    item.get("FEntity_FENTRYID"),  # FENTRYID
                    item.get("FBillNo"),  # FBILLNO
                    item.get("FForeOrgId.FNAME"),  # FFORGNAME
                    item.get("FCustId.FNAME"),  # FCUSTNAME
                    item.get("FCustId.FGROUP") or item.get("FCUSTID.FGROUP"),  # FCUSTGROUP
                    item.get("FMaterialId.FNAME"),  # FMATERIALNAME
                    item.get("FMaterialId.FNUMBER"),  # FMATERIALNUMBER
                    item.get("FQty"),  # FQTY
                    item.get("F_ora_Base.FNAME"),  # FORA_BASE_FNAME
                    item.get("F_ora_BaseProperty_ca9"),  # FORA_BASEPROPERTY_CA9
                    item.get("F_ora_BaseProperty_uky"),  # FORA_BASEPROPERTY_UKY
                    self._parse_datetime(item.get("F_ora_Date")),  # FDATE
                    self._parse_datetime(item.get("FModifyDate")),  # FMODIFYDATE
                    self._parse_datetime(item.get("F_ora_Date")),  # F_ORA_DATE
                    item.get("FMaterialId.FDescription"),  # FDescription
                )
            if isinstance(item, list) and len(item) >= 13:
                # 列表格式数据（金蝶 API 直接返回的数组格式）
                # 根据 FieldKeys 的顺序映射到数据库字段
                has_cust_group = len(item) >= 14
                cust_group = item[4] if has_cust_group else None
                material_name_idx = 5 if has_cust_group else 4
                material_number_idx = 6 if has_cust_group else 5
                qty_idx = 7 if has_cust_group else 6
                base_name_idx = 8 if has_cust_group else 7
                base_ca9_idx = 9 if has_cust_group else 8
                base_uky_idx = 10 if has_cust_group else 9
                ora_date_idx = 11 if has_cust_group else 10
                modify_date_idx = 12 if has_cust_group else 11
                fdescription = item[13] if has_cust_group else (item[12] if len(item) > 12 else None)
                return (
                    item[0],  # FENTRYID
                    item[1],  # FBILLNO
                    item[2],  # FFORGNAME
                    item[3],  # FCUSTNAME
                    cust_group,  # FCUSTGROUP
                    item[material_name_idx],  # FMATERIALNAME
                    item[material_number_idx],  # FMATERIALNUMBER
                    item[qty_idx],  # FQTY
                    item[base_name_idx],  # FORA_BASE_FNAME
                    item[base_ca9_idx],  # FORA_BASEPROPERTY_CA9
                    item[base_uky_idx],  # FORA_BASEPROPERTY_UKY
                    self._parse_datetime(str(item[ora_date_idx]) if item[ora_date_idx] else None),  # FDATE
                    self._parse_datetime(str(item[modify_date_idx]) if item[modify_date_idx] else None),  # FMODIFYDATE
                    self._parse_datetime(str(item[ora_date_idx]) if item[ora_date_idx] else None),  # F_ORA_DATE
                    fdescription,  # FDescription
                )
            logger.warning(f"不支持的数据类型或列表数据项不足: {type(item)}")
            return None
        except Exception as e:
            logger.error(f"准备预测订单数据失败: {str(e)}, 数据: {item}")
            return None

    def _prepare_delivery_notice_data(self, item) -> tuple | None:
        """准备发货通知单数据
        按照数据库字段顺序: FID, FENTRYID, FSEQ, FBILLNO, FDATE, FCUSTNAME,
        FMATERIALNAME, FMATERIALNUMBER, FQTY, FSUMOUTQTY, FCLOSESTATUS_MX, FMODIFYDATE,
        FSRCBILLNO, SYNC_TIME
        """
        try:
            if isinstance(item, dict):
                fid = self._to_int_or_none(item.get("FID") or 0)
                entry_id = item.get("FEntity_FENTRYID") or item.get("FENTRYID")
                if entry_id is None:
                    logger.warning("发货通知单记录缺少关键主键(FENTRYID)，已跳过: %s", item)
                    return None
                if fid is None:
                    fid = self._to_int_or_none(entry_id) or 0
                    logger.warning("发货通知单记录缺少FID，已使用FENTRYID回填: %s", item)
                if fid is None:
                    logger.warning("发货通知单记录FID仍为空，已跳过: %s", item)
                    return None
                fseq = self._to_int_or_none(item.get("FEntity_FSEQ") or 0) or item.get("FSEQ")
                bill_no = item.get("FBillNo") or item.get("FBILLNO")
                fdate = self._parse_date(item.get("FDate") or item.get("FDATE"))
                cust_name = item.get("FCustomerID.FNAME") or item.get("FCustomerID.FName")
                mat_name = item.get("FMaterialID.FNAME") or item.get("FMaterialID.FName")
                mat_num = item.get("FMaterialID.FNUMBER") or item.get("FMaterialID.FNumber")
                qty = item.get("FQTY") if item.get("FQTY") is not None else item.get("FQty")
                sum_out_qty = item.get("FSumOutQty") or item.get("FSUMOUTQTY")
                if sum_out_qty is None:
                    sum_out_qty = 0
                close_status = item.get("FCLOSESTATUS_MX")
                modify_dt = self._parse_datetime(item.get("FModifyDate") or item.get("FMODIFYDATE"))
                src_bill_no = item.get("FSrcBillNo") or item.get("FSRCBILLNO")
                sync_time = datetime.now()
                return (
                    fid,
                    entry_id,
                    fseq,
                    bill_no,
                    fdate,
                    cust_name,
                    mat_name,
                    mat_num,
                    qty,
                    sum_out_qty,
                    close_status,
                    modify_dt,
                    src_bill_no,
                    sync_time,
                )
            if isinstance(item, list) and len(item) >= 13:
                fid = self._to_int_or_none(item[0]) or 0
                entry_id = item[1]
                if entry_id is None:
                    logger.warning("发货通知单记录缺少关键主键(FENTRYID)，已跳过: %s", item)
                    return None
                if fid is None:
                    fid = self._to_int_or_none(entry_id) or 0
                    logger.warning("发货通知单记录缺少FID，已使用FENTRYID回填: %s", item)
                if fid is None:
                    logger.warning("发货通知单记录FID仍为空，已跳过: %s", item)
                    return None
                src_bill_no = item[12]
                modify_dt = self._parse_datetime(str(item[11]) if item[11] else None)
                sync_time = datetime.now()
                sum_out_qty = item[9]
                if sum_out_qty is None:
                    sum_out_qty = 0
                return (
                    fid,
                    entry_id,
                    (self._to_int_or_none(item[2]) or 0),
                    item[3],
                    self._parse_date(str(item[4]) if item[4] else None),
                    item[5],
                    item[6],
                    item[7],
                    item[8],
                    sum_out_qty,
                    item[10],
                    modify_dt,
                    src_bill_no,
                    sync_time,
                )
            logger.warning(f"不支持的数据类型或列表数据项不足: {type(item)}")
            return None
        except Exception as e:
            logger.error(f"准备发货通知单数据失败: {str(e)}, 数据: {item}")
            return None

    def insert_customer_data(self, data: list[dict]) -> int:
        return self.execute_writer("insert_customer_data", data)

    def _prepare_customer_data(self, item) -> tuple | None:
        """准备客户资料数据
        按照数据库字段顺序: FCUSTID, FNUMBER, FNAME, FGROUP, FSELLERNAME,
        FSTAFF, FCUSTLEVEL, FCUSTPYPE, FCREATEDATE, FMODIFYDATE
        """
        try:
            # 检查数据类型
            if isinstance(item, dict):
                # 字典格式数据
                return (
                    item.get("FCUSTID"),  # FCUSTID
                    item.get("FNumber"),  # FNUMBER
                    item.get("FNAME"),  # FNAME
                    item.get("FGROUP.FNAME"),  # FGROUP
                    item.get("FSELLER.FNAME"),  # FSELLERNAME
                    item.get("F_ora_Base.FNAME"),  # FSTAFF
                    item.get("F_ora_Text_qtr"),  # FCUSTLEVEL
                    item.get("F_ora_CUSTPYPE"),  # FCUSTPYPE
                    self._format_date_only(item.get("FCreateDate")),  # FCREATEDATE
                    self._parse_datetime(item.get("FModifyDate")),  # FMODIFYDATE
                )
            if isinstance(item, list) and len(item) >= 10:
                # 列表格式数据（金蝶 API 直接返回的数组格式）
                # 根据 FieldKeys 的顺序映射到数据库字段
                return (
                    item[0],  # FCUSTID
                    item[1],  # FNUMBER
                    item[2],  # FNAME
                    item[5],  # FGROUP
                    item[6],  # FSELLERNAME
                    item[7],  # FSTAFF
                    item[8],  # FCUSTLEVEL
                    item[9],  # FCUSTPYPE
                    self._format_date_only(str(item[3]) if item[3] else None),  # FCREATEDATE
                    self._parse_datetime(str(item[4]) if item[4] else None),  # FMODIFYDATE
                )
            logger.warning(f"不支持的数据类型或列表数据项不足: {type(item)}")
            return None
        except Exception as e:
            logger.error(f"准备客户资料数据失败: {str(e)}, 数据: {item}")
            return None

    def insert_stk_inventory(self, data: list[dict]) -> int:
        return self.execute_writer("insert_stk_inventory", data)

    def _prepare_stk_inventory_data(self, item) -> tuple | None:
        """准备即时库存数据，兼容字典与列表格式（字段映射）
        动态根据当前配置的 FieldKeys 进行列表到字段名的映射，避免字段顺序或数量变化导致插入失败。
        """
        try:
            from decimal import Decimal

            def intify(v):
                try:
                    if v is None:
                        return None
                    s = str(v).strip()
                    if s == "":
                        return None
                    return int(Decimal(s))
                except Exception:
                    return None

            def decify(v):
                try:
                    if v is None:
                        return None
                    s = str(v).strip()
                    if s == "":
                        return None
                    return float(s)
                except Exception:
                    return None

            # 读取当前 FieldKeys，用于列表到字段名的映射
            fk_conf = config_manager.get_form_queries().get("即时库存", {}).get("FieldKeys", "")
            fk_list = [k.strip() for k in fk_conf.split(",") if k.strip()]
            # 仅保留基础字段名（去掉可能的嵌套如 A.B.C => C）
            fk_base = [k.split(".")[-1] for k in fk_list]

            # 将输入转换为以字段名为键的字典，便于按数据库列顺序取值
            row_map: dict[str, Any] = {}

            if isinstance(item, dict):
                # 直接使用字典（兼容金蝶返回字典格式）
                row_map = item
            elif isinstance(item, list):
                if len(fk_base) == 0:
                    logger.warning("即时库存 FieldKeys 为空，无法映射列表数据")
                    return None
                if len(item) < len(fk_base):
                    logger.warning(f"即时库存行字段数不匹配: 行len={len(item)}, FieldKeys={len(fk_base)}; item={item}")
                    # 仍尝试按可用索引进行映射（缺失字段将为 None）
                # 将列表与 FieldKeys 对齐，超出部分忽略，缺失部分置 None
                for idx, key in enumerate(fk_base):
                    row_map[key] = item[idx] if idx < len(item) else None
            else:
                logger.warning(f"不支持的数据类型或列表数据项不足: {type(item)}")
                return None

            # 生成按数据库列顺序的元组
            fid = row_map.get("FID")
            stock_org_id = intify(row_map.get("FSTOCKORGID"))
            stock_id = intify(row_map.get("FSTOCKID"))
            stock_loc_id = intify(row_map.get("FSTOCKLOCID"))
            stock_status_id = intify(row_map.get("FSTOCKSTATUSID"))
            base_unit_id = intify(row_map.get("FBASEUNITID"))
            base_qty = decify(row_map.get("FBASEQTY"))
            material_id = intify(row_map.get("FMATERIALID"))
            # 新增：API FUPDATETIME → 数据库 FMODIFYDATE
            try:
                modify_time = self._parse_datetime(row_map.get("FUPDATETIME") or row_map.get("FMODIFYDATE"))
            except Exception:
                modify_time = None

            # 基本必填校验：FID 与 FMATERIALID 缺失时视为异常数据
            if fid is None or material_id is None:
                logger.warning(
                    f"即时库存数据缺失关键字段(FID/ FMATERIALID): FID={fid}, FMATERIALID={material_id}, 原始={item}"
                )
                return None

            return (
                fid,
                stock_org_id,
                stock_id,
                stock_loc_id,
                stock_status_id,
                base_unit_id,
                base_qty,
                material_id,
                modify_time,
            )
        except Exception as e:
            logger.error(f"准备即时库存数据失败: {str(e)}, 数据: {item}")
            return None

    # 物料主数据插入与映射
    def insert_bd_material(self, data: list[dict]) -> int:
        return self.execute_writer("insert_bd_material", data)

    # 仓库主数据插入与映射
    def insert_bd_stock(self, data: list[dict]) -> int:
        return self.execute_writer("insert_bd_stock", data)

    def _prepare_bd_stock_data(self, item) -> tuple | None:
        """准备仓库主数据，兼容字典与列表格式"""
        try:
            if isinstance(item, dict):

                def _s(key, default=""):
                    return item.get(key, default)

                def _dt(key):
                    return self._parse_datetime(item.get(key))

                return (
                    (self._to_int_or_none(item.get("FSTOCKID") or 0)),  # 0 FSTOCKID
                    (self._to_int_or_none(item.get("FMASTERID") or 0)),  # 1 FMASTERID
                    _s("FNUMBER"),  # 2 FNUMBER
                    (self._to_int_or_none(item.get("FUSEORGID") or 0)),  # 3 FUSEORGID
                    _dt("FMODIFYDATE"),  # 4 FMODIFYDATE
                    _s("FDOCUMENTSTATUS"),  # 5 FDOCUMENTSTATUS
                    _s("FFORBIDSTATUS"),  # 6 FFORBIDSTATUS
                    _s("FNAME"),  # 7 FNAME
                )
            if isinstance(item, list):
                def get_item(i, default=""):
                    return item[i] if i < len(item) and item[i] is not None else default

                return (
                    (self._to_int_or_none(get_item(0) or 0)),  # FSTOCKID
                    (self._to_int_or_none(get_item(1) or 0)),  # FMASTERID
                    get_item(2),  # FNUMBER
                    (self._to_int_or_none(get_item(3) or 0)),  # FUSEORGID
                    self._parse_datetime(get_item(4, None)),  # FMODIFYDATE
                    get_item(5),  # FDOCUMENTSTATUS
                    get_item(6),  # FFORBIDSTATUS
                    get_item(7),  # FNAME
                )
            logger.warning(f"不支持的数据类型: {type(item)}")
            return None
        except Exception as e:
            logger.error(f"准备仓库数据失败: {str(e)}")
            return None

    def _prepare_bd_material_data(self, item) -> tuple | None:
        """准备物料主数据，兼容字典与列表格式"""
        try:
            if isinstance(item, dict):
                # 统一提供默认值与类型转换
                def _s(key, default=""):
                    return item.get(key, default)

                def _first(keys, default=""):
                    for key in keys:
                        value = item.get(key)
                        if value is not None and value != "":
                            return value
                    return default

                def _dt(key):
                    return self._parse_datetime(item.get(key))

                def _dec(*keys):
                    for k in keys:
                        v = item.get(k)
                        if v is not None:
                            return self._to_decimal_or_none(v) or 0.0
                    return None

                return (
                    _s("FMATERIALID", None),  # 0 FMATERIALID
                    _s("FNUMBER"),  # 1 FNUMBER
                    _s("FMASTERID", None),  # 2 FMASTERID
                    _first(("FMATERIALGROUP.fname", "FMATERIALGROUP.FNAME", "FMATERIALGROUP"), None),  # 3 FMATERIALGROUP
                    _s("FCREATEORGID", None),  # 4 FCREATEORGID
                    _s("FUSEORGID", None),  # 5 FUSEORGID
                    _dt("FCREATEDATE"),  # 6 FCREATEDATE
                    _dt("FMODIFYDATE"),  # 7 FMODIFYDATE
                    _s("FDOCUMENTSTATUS"),  # 8 FDOCUMENTSTATUS
                    _s("FFORBIDSTATUS"),  # 9 FFORBIDSTATUS
                    _dt("FAPPROVEDATE"),  # 10 FAPPROVEDATE
                    _s("FREFSTATUS"),  # 12 FREFSTATUS
                    _s("F_TMHE_TEXT"),  # 13 F_TMHE_TEXT
                    _s("F_JY_TEXT"),  # 14 F_JY_TEXT
                    _s("F_JY_TEXT1"),  # 15 F_JY_TEXT1
                    _s("F_JY_TEXT2"),  # 16 F_JY_TEXT2
                    _s("F_JYX_TEXT1"),  # 17 F_JYX_TEXT1
                    _s("F_JYX_TEXT2"),  # 18 F_JYX_TEXT2
                    _s("F_JYX_TEXT4"),  # 19 F_JYX_TEXT4
                    _s("F_JYX_TEXT3"),  # 20 F_JYX_TEXT3
                    _s("F_JYX_ASSISTANT"),  # 21 F_JYX_ASSISTANT
                    _s("F_JYX_ASSISTANT1"),  # 22 F_JYX_ASSISTANT1
                    _s("F_JYX_ASSISTANT2"),  # 23 F_JYX_ASSISTANT2
                    _dec("F_JY_QTY", "F_F_JY_QTY"),  # 24 F_JY_QTY
                    _dec("F_JY_QTY1"),  # 25 F_JY_QTY1
                    _s("F_KDKF_HJFS"),  # 25 F_KDKF_HJFS
                    (_s("F_ORA_TEXT_9SB") or _s("F_ora_Text_9sb")),  # 26 F_ORA_TEXT_9SB
                    (_s("F_ORA_TEXT_QTR") or _s("F_ora_TEXT_qtr") or _s("F_ora_Text_qtr")),  # 27 F_ORA_TEXT_QTR
                    _s("F_ORA_TEXT_QTR1"),  # 28 F_ORA_TEXT_QTR1
                    _s("FERPCLSID"),  # 29 FERPCLSID
                    _s("FCATEGORYID", None),  # 30 FCATEGORYID
                    _s("FTYPEID", None),  # 31 FTYPEID
                    (_s("FBARCODE") or _s("FBarcode")),  # 32 FBARCODE
                    _s("FNAME"),  # 33 FNAME
                    _s("FSPECIFICATION"),  # 34 FSPECIFICATION
                )
            if isinstance(item, list):
                def get_item(i, default=""):
                    return item[i] if i < len(item) and item[i] is not None else default

                return (
                    get_item(0, None),  # FMATERIALID
                    get_item(1),  # FNUMBER
                    get_item(2, None),  # FMASTERID
                    get_item(3, None),  # FMATERIALGROUP
                    get_item(4, None),  # FCREATEORGID
                    get_item(5, None),  # FUSEORGID
                    self._parse_datetime(get_item(6, None)),  # FCREATEDATE
                    self._parse_datetime(get_item(7, None)),  # FMODIFYDATE
                    get_item(8),  # FDOCUMENTSTATUS
                    get_item(9),  # FFORBIDSTATUS
                    self._parse_datetime(get_item(10, None)),  # FAPPROVEDATE
                    get_item(11),  # FREFSTATUS
                    get_item(12),  # F_TMHE_TEXT
                    get_item(13),  # F_JY_TEXT
                    get_item(14),  # F_JY_TEXT1
                    get_item(15),  # F_JY_TEXT2
                    get_item(16),  # F_JYX_TEXT1
                    get_item(17),  # F_JYX_TEXT2
                    get_item(18),  # F_JYX_TEXT4
                    get_item(19),  # F_JYX_TEXT3
                    get_item(20),  # F_JYX_ASSISTANT
                    get_item(21),  # F_JYX_ASSISTANT1
                    get_item(22),  # F_JYX_ASSISTANT2
                    (self._to_decimal_or_none(get_item(23, None) or 0.0)),  # F_JY_QTY
                    (self._to_decimal_or_none(get_item(24, None) or 0.0)),  # F_JY_QTY1
                    get_item(25),  # F_KDKF_HJFS
                    get_item(26),  # F_ORA_TEXT_9SB
                    get_item(27),  # F_ORA_TEXT_QTR
                    get_item(28),  # F_ORA_TEXT_QTR1
                    get_item(29),  # FERPCLSID
                    get_item(30, None),  # FCATEGORYID
                    get_item(31, None),  # FTYPEID
                    get_item(32),  # FBARCODE
                    get_item(33),  # FNAME
                    get_item(34),  # FSPECIFICATION
                )
            logger.warning(f"不支持的数据类型: {type(item)}")
            return None
        except Exception as e:
            logger.error(f"准备物料数据失败: {str(e)}")
            return None

    # 辅助资料明细插入与映射
    def insert_bos_assistantdata_detail(self, data: list[dict]) -> int:
        return self.execute_writer("insert_bos_assistantdata_detail", data)

    def _prepare_bos_assistantdata_detail_data(self, item) -> tuple | None:
        """准备辅助资料明细数据，兼容字典与列表格式"""
        try:
            if isinstance(item, dict):
                return (
                    item.get("FId") or item.get("FID"),
                    item.get("FNumber"),
                    item.get("FDataValue"),
                    self._parse_datetime(item.get("FModifyDate") or item.get("FMODIFYDATE")),
                )
            if isinstance(item, list) and len(item) >= 5:
                return (
                    item[0],  # FId/FID
                    item[1],  # FNumber
                    item[2],  # FDataValue
                    self._parse_datetime(item[3]),  # FModifyDate
                )
            logger.warning(f"不支持的数据类型或列表数据项不足: {type(item)}")
            return None
        except Exception as e:
            logger.error(f"准备辅助资料明细数据失败: {str(e)}")
            return None

    # 辅助资料插入与映射（ASSISTANTDATA）
    def insert_assistantdata(self, data: list[dict]) -> int:
        return self.execute_writer("insert_assistantdata", data)

    def _prepare_assistantdata_data(self, item) -> tuple | None:
        """准备辅助资料数据，兼容字典与列表格式"""
        try:
            if isinstance(item, dict):
                return (
                    item.get("FId") or item.get("FID"),
                    item.get("FNumber"),
                    item.get("FDataValue"),
                    self._parse_datetime(item.get("FModifyDate") or item.get("FMODIFYDATE")),
                )
            if isinstance(item, list) and len(item) >= 5:
                return (
                    item[0],  # FId/FID
                    item[1],  # FNumber
                    item[2],  # FDataValue
                    self._parse_datetime(item[3]),  # FModifyDate
                )
            logger.warning(f"不支持的数据类型或列表数据项不足: {type(item)}")
            return None
        except Exception as e:
            logger.error(f"准备辅助资料数据失败: {str(e)}")
            return None

    # 物料清单插入与映射（ENG_BOM）
    def insert_eng_bom(self, data: list[dict]) -> int:
        return self.execute_writer("insert_eng_bom", data)

    # 物料清单子项插入与映射（eng_bomchild）
    def insert_eng_bom_child(self, data: list[dict]) -> int:
        return self.execute_writer("insert_eng_bom_child", data)

    def _diagnose_data_type_error(self, table, columns, batch):
        """诊断数据类型错误，找出导致 8114 的罪魁祸首"""
        try:
            logger.warning(f"正在对表 {table} 进行字段级数据诊断 (共 {len(batch)} 条记录)...")
            # 仅检查前 100 条和后 100 条，避免日志爆炸
            check_rows = batch[:100]
            if len(batch) > 100:
                check_rows.extend(batch[-100:])

            suspects = []
            for row_idx, row in enumerate(check_rows):
                # 假设 row 与 columns 一一对应
                if len(row) != len(columns):
                    continue

                for col_idx, val in enumerate(row):
                    col_name = columns[col_idx]
                    # 简单启发式检查
                    # 如果列名包含 ID, QTY, PRICE, RATE, NUM, SEQ 等，通常期望是数字
                    is_numeric_col = any(
                        k in col_name.upper()
                        for k in ["QTY", "PRICE", "RATE", "NUM", "SEQ", "ID", "ORG", "GROUP", "STATUS"]
                    )
                    # 排除一些明显是字符串的 ID
                    if col_name.upper() in [
                        "FNUMBER",
                        "FBILLNO",
                        "FMATERIALID",
                        "FENTRYROWID",
                        "FISSUETYPE",
                        "FBACKFLUSHTYPE",
                        "FMATERIALTYPE",
                    ]:
                        # 注意：FMATERIALID 在某些表是 int，某些是 string。
                        # eng_bomchild 的 FMATERIALID 是 string，但 eng_bom 是 int。
                        # 这里不做硬性判断，仅记录明显的异常
                        is_numeric_col = False

                    if is_numeric_col:
                        if isinstance(val, str):
                            # 如果是字符串，尝试解析
                            try:
                                float(val)
                            except ValueError:
                                suspects.append(
                                    f"行 {row_idx}, 列 {col_name} ({col_idx}): 期望数值，实际为非数字字符串 '{val}'"
                                )
                        elif val is None:
                            pass  # NULL 通常可以接受
                        elif not isinstance(val, (int, float)):
                            suspects.append(
                                f"行 {row_idx}, 列 {col_name} ({col_idx}): 期望数值，实际类型 {type(val)} 值 '{val}'"
                            )

            if suspects:
                logger.error(f"诊断发现 {len(suspects)} 个潜在类型问题 (展示前 10 个):")
                for s in suspects[:10]:
                    logger.error(s)
            else:
                logger.warning("诊断未发现明显的类型不匹配（可能是隐式转换问题或 Schema 定义与代码假设不一致）。")
                # 打印第一行数据的类型概览
                if batch:
                    row0 = batch[0]
                    type_sig = [f"{columns[i]}:{type(v).__name__}" for i, v in enumerate(row0)]
                    logger.info(f"第一行数据类型签名: {', '.join(type_sig)}")

        except Exception as e:
            logger.error(f"诊断过程本身出错: {e}")

    def _diagnose_string_truncation(self, table, columns, batch):
        """Diagnose SQL Server string truncation by comparing value size with column width."""
        try:
            logger.warning(f"正在对表 {table} 进行字符串截断诊断 (共 {len(batch)} 条记录)...")
            if getattr(self, "db_type", "mysql") != "sqlserver" or not self.cursor:
                return

            base_name = str(table).split(".")[-1].replace("[", "").replace("]", "").strip()
            self.cursor.execute(
                """
                SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = ?
                """,
                (base_name,),
            )
            rows = self.cursor.fetchall() or []
            length_map = {}
            for row in rows:
                if isinstance(row, dict):
                    col_name = row.get("COLUMN_NAME")
                    data_type = row.get("DATA_TYPE")
                    max_len = row.get("CHARACTER_MAXIMUM_LENGTH")
                else:
                    col_name = row[0] if len(row) > 0 else None
                    data_type = row[1] if len(row) > 1 else None
                    max_len = row[2] if len(row) > 2 else None
                if col_name:
                    length_map[str(col_name).upper()] = (str(data_type or "").lower(), max_len)

            suspects = []
            check_rows = batch[:20]
            if len(batch) > 20:
                check_rows.extend(batch[-20:])

            for _row_idx, row in enumerate(check_rows):
                if len(row) != len(columns):
                    continue
                for col_idx, value in enumerate(row):
                    if value is None:
                        continue
                    column_name = str(columns[col_idx]).strip()
                    data_type, max_len = length_map.get(column_name.upper(), ("", None))
                    if data_type not in {"nvarchar", "varchar", "nchar", "char"}:
                        continue
                    if max_len in (None, -1):
                        continue
                    text_value = str(value)
                    char_len = len(text_value)
                    storage_len = char_len * 2 if data_type.startswith("n") else char_len
                    if storage_len > int(max_len):
                        suspects.append((column_name, char_len, storage_len, int(max_len), text_value[:120]))

            if suspects:
                for column_name, char_len, storage_len, allowed_len, preview in suspects[:10]:
                    logger.error(
                        "[TRUNCATION] 表 %s 列 %s 超长: chars=%s bytes=%s allowed_bytes=%s preview=%r",
                        table,
                        column_name,
                        char_len,
                        storage_len,
                        allowed_len,
                        preview,
                    )
            else:
                logger.warning("字符串截断诊断未发现明确超长列，可能是驱动编码或隐式转换问题。")
        except Exception as e:
            logger.error(f"字符串截断诊断本身失败: {e}")

    def _prepare_eng_bom_data(self, item) -> tuple | None:
        """准备物料清单数据（32 字段），兼容字典与列表格式"""
        try:
            if isinstance(item, dict):
                billtype_name = item.get("FBILLTYPE.FNAME") or item.get("FBILLTYPE_FNAME") or item.get("FBILLTYPE")
                return (
                    item.get("FID") or item.get("FId"),  # FID
                    item.get("FMASTERID"),  # FMASTERID
                    item.get("FNUMBER"),  # FNUMBER
                    billtype_name,  # FBILLTYPE（取 FNAME）
                    item.get("FDOCUMENTSTATUS"),  # FDOCUMENTSTATUS
                    (self._to_int_or_none(item.get("FMATERIALID") or 0)),  # FMATERIALID
                    item.get("FFORBIDSTATUS"),  # FFORBIDSTATUS
                    (self._to_int_or_none(item.get("FUSEORGID") or 0)),  # FUSEORGID
                    self._parse_datetime(item.get("FMODIFYDATE") or item.get("FModifyDate")),  # FMODIFYDATE
                    (self._to_int_or_none(item.get("FBASEUNITID") or 0)),  # FBASEUNITID
                    (self._to_decimal_or_none(item.get("FQTY") or 0.0)),  # FQTY
                    (self._to_int_or_none(item.get("FBOMUSE") or 0)),  # FBOMUSE
                )
            if isinstance(item, list) and len(item) >= 12:
                return (
                    item[0],  # FID
                    item[1],  # FMASTERID
                    item[2],  # FNUMBER
                    item[3],  # FBILLTYPE.FNAME -> FBILLTYPE
                    item[4],  # FDOCUMENTSTATUS
                    (self._to_int_or_none(item[5]) or 0),  # FMATERIALID
                    item[6],  # FFORBIDSTATUS
                    (self._to_int_or_none(item[7]) or 0),  # FUSEORGID
                    self._parse_datetime(item[8]),  # FMODIFYDATE
                    (self._to_int_or_none(item[9]) or 0),  # FBASEUNITID
                    (self._to_decimal_or_none(item[10]) or 0.0),  # FQTY
                    (self._to_int_or_none(item[11]) or 0),  # FBOMUSE
                )
            logger.warning(f"不支持的数据类型或列表数据项不足: {type(item)}")
            return None
        except Exception as e:
            logger.error(f"准备物料清单数据失败: {str(e)}")
            return None

    def _prepare_eng_bom_child_data(self, item) -> tuple | None:
        # ENG_BOM 子项当前按 19 个字段准备数据，FieldKeys 中包含
        # FMATERIALIDCHILD.FNUMBER、FMATERIALIDCHILD.FNAME 和 FMODIFYDATE，
        # 并分别映射到写入列 FCHILDNUMBER、FCHILDNAME、FMODIFYDATE。
        """准备物料清单子项数据�?6字段），兼容字典与列表格�?        FieldKeys 顺序(来源�?API):
        FID, FTreeEntity_FENTRYID, FTreeEntity_FSEQ, FMATERIALID, FMATERIALIDCHILD.FNUMBER, FMATERIALIDCHILD.FNAME, FNUMERATOR, FDENOMINATOR,
        FISSUETYPE, FBACKFLUSHTYPE, FSUPPLYORG, FSTOCKID, FENTRYROWID, FREPLACEGROUP, FQTY, FACTUALQTY, FMASTERID, FMATERIALTYPE
        直接映射�?MySQL/SQL Server 列（不再使用 FMATERIALIDCHILD �?FQTY2�?"""
        try:
            if isinstance(item, dict):
                child_row = dict(item)
                child_row.setdefault(
                    "FCHILDNUMBER",
                    item.get("FMATERIALIDCHILD.FNUMBER") or item.get("FMATERIALIDCHILD.FNumber"),
                )
                child_row.setdefault("FCHILDNAME", item.get("FMATERIALIDCHILD.FNAME") or item.get("FMATERIALIDCHILD.FName"))
                child_number = self._resolve_configured_field("eng_bomchild", "FCHILDNUMBER", child_row)
                if child_number is None:
                    child_number = (
                        item.get("FMATERIALIDCHILD.FNUMBER")
                        or item.get("FMATERIALIDCHILD.FNumber")
                        or item.get("FCHILDNUMBER")
                    )
                child_name = self._resolve_configured_field("eng_bomchild", "FCHILDNAME", child_row)
                if child_name is None:
                    child_name = item.get("FMATERIALIDCHILD.FNAME") or item.get("FMATERIALIDCHILD.FName") or item.get(
                        "FCHILDNAME"
                    )
                return (
                    (self._to_int_or_none(item.get("FID") or 0) or item.get("FId")),  # FID
                    (self._to_int_or_none(item.get("FTreeEntity_FENTRYID") or 0) or item.get("FENTRYID")),  # FENTRYID
                    (self._to_int_or_none(item.get("FTreeEntity_FSEQ") or 0) or item.get("FSEQ")),  # FSEQ
                    self._safe_str(item.get("FMATERIALID") or item.get("FTreeEntity_FMATERIALID")),  # FMATERIALID
                    self._safe_str(child_number),  # FCHILDNUMBER
                    self._safe_str(child_name),  # FCHILDNAME
                    (self._to_decimal_or_none(item.get("FNUMERATOR") or 0.0)),  # FNUMERATOR
                    (self._to_decimal_or_none(item.get("FDENOMINATOR") or 0.0)),  # FDENOMINATOR
                    self._safe_str(item.get("FISSUETYPE")),  # FISSUETYPE
                    self._safe_str(item.get("FBACKFLUSHTYPE")),  # FBACKFLUSHTYPE
                    self._to_int_or_none(item.get("FSUPPLYORG")) or 0,  # FSUPPLYORG
                    self._to_int_or_none(item.get("FSTOCKID") or item.get("FStockId")) or 0,  # FSTOCKID
                    self._safe_str(item.get("FENTRYROWID")),  # FENTRYROWID
                    (self._to_int_or_none(item.get("FREPLACEGROUP") or 0)),  # FREPLACEGROUP
                    (self._to_decimal_or_none(item.get("FQTY") or 0.0) or item.get("FTreeEntity_FQTY")),  # FQTY
                    (self._to_decimal_or_none(item.get("FACTUALQTY") or 0.0)),  # FACTUALQTY
                    (self._to_int_or_none(item.get("FMASTERID") or 0)),  # FMASTERID
                    self._safe_str(item.get("FMATERIALTYPE") or item.get("FTreeEntity_FMATERIALTYPE")),  # FMATERIALTYPE
                    self._parse_datetime(item.get("FMODIFYDATE") or item.get("FModifyDate")),  # FMODIFYDATE
                )
            if isinstance(item, list) and len(item) >= 18:
                # 列表模式下，尝试兼容可能存在的第19个字段（FMODIFYDATE），若无则为None
                fmodifydate = self._parse_datetime(item[18]) if len(item) > 18 else None
                child_row = {
                    "FID": item[0],
                    "FTreeEntity_FENTRYID": item[1],
                    "FTreeEntity_FSEQ": item[2],
                    "FMATERIALID": item[3],
                    "FMATERIALIDCHILD.FNUMBER": item[4],
                    "FMATERIALIDCHILD.FNAME": item[5],
                    "FNUMERATOR": item[6],
                    "FDENOMINATOR": item[7],
                    "FISSUETYPE": item[8],
                    "FBACKFLUSHTYPE": item[9],
                    "FSUPPLYORG": item[10],
                    "FSTOCKID": item[11],
                    "FENTRYROWID": item[12],
                    "FREPLACEGROUP": item[13],
                    "FQTY": item[14],
                    "FACTUALQTY": item[15],
                    "FMASTERID": item[16],
                    "FMATERIALTYPE": item[17],
                }
                if len(item) > 18:
                    child_row["FMODIFYDATE"] = item[18]
                child_number = self._resolve_configured_field("eng_bomchild", "FCHILDNUMBER", child_row)
                if child_number is None:
                    child_number = item[4]
                child_name = self._resolve_configured_field("eng_bomchild", "FCHILDNAME", child_row)
                if child_name is None:
                    child_name = item[5]
                return (
                    (self._to_int_or_none(item[0]) or 0),  # FID
                    (self._to_int_or_none(item[1]) or 0),  # FENTRYID
                    (self._to_int_or_none(item[2]) or 0),  # FSEQ
                    self._safe_str(item[3]),  # FMATERIALID
                    self._safe_str(child_number),  # FCHILDNUMBER
                    self._safe_str(child_name),  # FCHILDNAME
                    (self._to_decimal_or_none(item[6]) or 0.0),  # FNUMERATOR
                    (self._to_decimal_or_none(item[7]) or 0.0),  # FDENOMINATOR
                    self._safe_str(item[8]),  # FISSUETYPE
                    self._safe_str(item[9]),  # FBACKFLUSHTYPE
                    self._to_int_or_none(item[10]) or 0,  # FSUPPLYORG
                    self._to_int_or_none(item[11]) or 0,  # FSTOCKID
                    self._safe_str(item[12]),  # FENTRYROWID
                    (self._to_int_or_none(item[13]) or 0),  # FREPLACEGROUP
                    (self._to_decimal_or_none(item[14]) or 0.0),  # FQTY
                    (self._to_decimal_or_none(item[15]) or 0.0),  # FACTUALQTY
                    (self._to_int_or_none(item[16]) or 0),  # FMASTERID
                    self._safe_str(item[17]),  # FMATERIALTYPE
                    fmodifydate,  # FMODIFYDATE
                )
            logger.warning(f"不支持的数据类型或列表数据项不足: {type(item)}")
            return None
        except Exception as e:
            logger.error(f"准备物料清单子项数据失败: {str(e)}")
            return None

    def _safe_str(self, val):
        """安全转换为字符串，空字符串转为 None"""
        try:
            val = self._extract_scalar(val)
            if val is None:
                return None
            s = str(val).strip()
            return s if s else None
        except Exception:
            return None

    def _safe_int(self, val):
        try:
            return int(val) if val is not None and val != "" else None
        except Exception:
            return None


# 全局MySQL管理器实例
mysql_manager = MySQLManager()
