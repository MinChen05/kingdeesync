"""Single-form sync execution helpers for DataSyncManager."""

from __future__ import annotations

import logging
import queue
import threading
import time
import traceback
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import requests  # type: ignore[import-untyped]

from src.config.config_manager import config_manager
from src.core.audit_logging import emit_audit_log
from src.core.filter_builder import FilterBuilder
from src.core.kingdee_api import kingdee_client
from src.core.mysql_manager import MySQLManager, mysql_manager
from src.core.retry_manager import SyncCheckpoint
from src.core.sync_log_repository import SyncLogRepository
from src.core.sync_run_repository import SyncRunRepository
from src.core.upsert_engine_mysql import UpsertEngineMySQL
from src.core.upsert_engine_sqlserver import UpsertEngineSqlServer
from src.core.writers_registry import WriterRegistry

if TYPE_CHECKING:
    from src.core.data_sync import DataSyncManager

logger = logging.getLogger(__name__)

SUCCESS_STATUS = "success"
FAILED_STATUS = "failed"
PARTIAL_STATUS = "partial"


def create_shared_db_manager(base_manager: MySQLManager) -> MySQLManager:
    """Create a lightweight manager instance that shares the base pool."""
    local_db = MySQLManager.__new__(MySQLManager)
    local_db.pool = None
    local_db.connection = None
    local_db.cursor = None
    local_db._pool_init_failed = False
    local_db.db_type = getattr(base_manager, "db_type", "mysql")
    local_db.config = getattr(base_manager, "config", {})
    local_db.sync_run_repository = SyncRunRepository(local_db, logger=logger)
    local_db.sync_log_repository = SyncLogRepository(local_db, logger=logger)
    local_db.mysql_upsert_engine = UpsertEngineMySQL(local_db, logger=logger)
    local_db.sqlserver_upsert_engine = UpsertEngineSqlServer(local_db, logger=logger)
    local_db.writer_registry = WriterRegistry(logger=logger)

    if getattr(base_manager, "pool", None):
        local_db.pool = base_manager.pool
        local_db.connect()

    return local_db


class FormSyncRunner:
    """Runs the detailed workflow for syncing a single form."""

    def __init__(
        self,
        owner: "DataSyncManager",
        filter_builder: FilterBuilder,
        *,
        logger_: logging.Logger | None = None,
    ) -> None:
        self.owner = owner
        self.filter_builder = filter_builder
        self.logger = logger_ or logger

    @staticmethod
    def _sync_type_value(sync_type) -> str:
        return str(getattr(sync_type, "value", sync_type or "")).lower()

    def _is_incremental(self, sync_type) -> bool:
        return self._sync_type_value(sync_type) == "incremental"

    def _is_full_or_complete(self, sync_type) -> bool:
        return self._sync_type_value(sync_type) in {"full", "complete"}

    def sync_single_form(self, form_name: str, sync_type) -> Dict[str, Any]:
        """Run one form end-to-end while DataSyncManager orchestrates scheduling."""
        if form_name == "科目余额表":
            return self.owner._sync_account_balance_form(form_name, sync_type)

        start_time = datetime.now()
        perf_start = time.perf_counter()
        local_db = create_shared_db_manager(mysql_manager)
        table_name = self.owner.table_mapping.get(form_name)
        sync_type_value = self._sync_type_value(sync_type)

        emit_audit_log(
            self.logger,
            "sync_form",
            "start",
            form_name=form_name,
            table_name=table_name,
            sync_type=sync_type_value,
            start_time=start_time,
        )

        try:
            if not table_name:
                error_msg = f"未找到表单 {form_name} 的映射表"
                self.logger.error(error_msg)
                self.owner._notify_progress(f"[{form_name}] {error_msg}", 100)
                emit_audit_log(
                    self.logger,
                    "sync_form",
                    "failure",
                    level="error",
                    form_name=form_name,
                    table_name=table_name,
                    sync_type=sync_type_value,
                    reason=error_msg,
                    error_type="mapping_error",
                )
                return {
                    "status": FAILED_STATUS,
                    "message": error_msg,
                    "record_count": 0,
                    "inserted": 0,
                    "updated": 0,
                    "error_type": "mapping_error",
                }

            self.logger.info("开始同步 %s 数据 (类型: %s)", form_name, self._sync_type_value(sync_type))
            if self._sync_type_value(sync_type) == "complete":
                if not self.truncate_table_for_complete(table_name, local_db):
                    error_msg = f"清空表 {table_name} 失败，终止完全同步"
                    self.owner._notify_progress(f"[{form_name}] {error_msg}", 100)
                    emit_audit_log(
                        self.logger,
                        "sync_form",
                        "failure",
                        level="error",
                        form_name=form_name,
                        table_name=table_name,
                        sync_type=sync_type_value,
                        reason=error_msg,
                        error_type="truncate_error",
                    )
                    return {
                        "status": FAILED_STATUS,
                        "message": error_msg,
                        "record_count": 0,
                        "inserted": 0,
                        "updated": 0,
                        "error_type": "truncate_error",
                    }

            self.owner._notify_progress(f"[{form_name}] 正在构建查询条件...", 10)
            filter_string = self.filter_builder.build_filter_string(
                form_name,
                sync_type,
                table_name,
                db_manager=local_db,
            )
            perf_after_filter = time.perf_counter()
            filter_duration = perf_after_filter - perf_start
            self.logger.info("[%s] 查询条件构建耗时 %.2f 秒", form_name, filter_duration)
            self.logger.debug("[%s] 查询条件: %s", form_name, filter_string if filter_string else "无")

            try:
                query_config = config_manager.get_form_queries().get(form_name, {})
                keys = [k.strip() for k in query_config.get("FieldKeys", "").split(",") if k.strip()]
                candidates = [
                    "FModifyDate",
                    "FMODIFYDATE",
                    "FLastUpdateTime",
                    "FLASTUPDATETIME",
                    "FLastUpdateDate",
                    "FLASTUPDATEDATE",
                    "FInventoryDate",
                    "FINVENTORYDATE",
                    "FInventoryTime",
                    "FINVENTORYTIME",
                    "FUpdateTime",
                    "FUPDATE_TIME",
                    "FUpdateDate",
                    "FUPDATEDATE",
                ]
                chosen = next((k.split(".")[-1] for k in keys if k.split(".")[-1] in candidates), None)
                self.logger.info("[%s] 增量时间字段推断: %s", form_name, chosen or "FModifyDate")
            except Exception:
                pass
            self.owner._notify_progress(f"[{form_name}] 查询条件构建完成", 20)

            self.owner._notify_progress(f"[{form_name}] 正在查询金蝶数据...", 30)
            self.logger.info("查询金蝶 %s 数据...", form_name)

            checkpoint = self.owner._checkpoint_manager.load_checkpoint(form_name, table_name, self._sync_type_value(sync_type))
            resume_start_row = 0
            if checkpoint and checkpoint.status == "pending" and self._is_incremental(sync_type):
                resume_start_row = checkpoint.start_row
                total_inserted_ref_init = checkpoint.total_inserted
                self.logger.info("[%s] 检测到断点，从 StartRow=%s 继续同步", form_name, resume_start_row)
            else:
                total_inserted_ref_init = 0

            max_retries = 3
            retry_count = 0
            total_inserted_ref = [total_inserted_ref_init]
            total_fetched_ref = [0]

            queue_size = 50 if self._is_full_or_complete(sync_type) else 10
            data_queue: "queue.Queue[Optional[List[Dict[str, Any]]]]" = queue.Queue(maxsize=queue_size)
            insert_errors: List[Exception] = []
            use_bulk_buffer = self._is_full_or_complete(sync_type)
            all_rows_buffer: List[Dict[str, Any]] = []

            def insert_worker() -> None:
                while True:
                    page_data = data_queue.get()
                    if page_data is None:
                        data_queue.task_done()
                        break
                    try:
                        count = self.insert_database_data(form_name, page_data, db_manager=local_db)
                        total_inserted_ref[0] += count
                        total_fetched_ref[0] += len(page_data)
                        self.owner._notify_progress(f"[{form_name}] 已同步 {total_inserted_ref[0]} 条数据...", 60)
                    except Exception as exc:
                        self.logger.error("[%s] 异步插入数据库失败: %s", form_name, exc)
                        insert_errors.append(exc)
                    finally:
                        data_queue.task_done()

            if not use_bulk_buffer:
                worker_thread = threading.Thread(target=insert_worker, name=f"InsertWorker-{form_name}")
                worker_thread.start()
            else:
                worker_thread = None

            def handle_page_data(page_data: List[Dict[str, Any]]) -> None:
                if not page_data:
                    return
                if use_bulk_buffer:
                    all_rows_buffer.extend(page_data)
                    total_fetched_ref[0] += len(page_data)
                    self.owner._notify_progress(f"[{form_name}] 已加载 {total_fetched_ref[0]} 条数据...", 50)
                    return

                if insert_errors:
                    raise Exception(f"插入线程出错: {insert_errors[0]}")
                data_queue.put(page_data)

            data = None
            while retry_count < max_retries:
                try:
                    data = self.query_kingdee_data(
                        form_name,
                        filter_string,
                        page_callback=handle_page_data,
                        start_row=resume_start_row,
                        sync_type=sync_type,
                    )
                    if data is not None:
                        self.owner._checkpoint_manager.clear_checkpoint(
                            form_name,
                            table_name,
                            self._sync_type_value(sync_type),
                        )
                        break

                    retry_count += 1
                    if retry_count < max_retries:
                        self.logger.warning("[%s] 查询失败，%s/%s 次重试...", form_name, retry_count, max_retries)
                        self.owner._notify_progress(
                            f"[{form_name}] 查询失败，正在重试 ({retry_count}/{max_retries})...",
                            35,
                        )
                        time.sleep(2)
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as query_error:
                    if insert_errors:
                        self.logger.error("[%s] 发生数据库插入致命错误，停止重试: %s", form_name, insert_errors[0])
                        if worker_thread is not None:
                            data_queue.put(None)
                            worker_thread.join()
                        raise insert_errors[0]

                    retry_count += 1
                    self.logger.error("[%s] 网络请求异常 (%s): %s", form_name, type(query_error).__name__, query_error)
                    if retry_count < max_retries:
                        self.owner._checkpoint_manager.save_checkpoint(
                            SyncCheckpoint(
                                form_name=form_name,
                                table_name=table_name,
                                sync_type=self._sync_type_value(sync_type),
                                start_row=resume_start_row,
                                total_inserted=total_inserted_ref[0],
                                total_fetched=total_fetched_ref[0],
                                filter_string=filter_string or "",
                                status="pending",
                            )
                        )
                        self.owner._notify_progress(
                            f"[{form_name}] 查询异常，正在重试 ({retry_count}/{max_retries})...",
                            35,
                        )
                        time.sleep(2)
                    else:
                        if worker_thread is not None:
                            data_queue.put(None)
                            worker_thread.join()
                        raise
                except Exception as query_error:
                    if insert_errors:
                        self.logger.error("[%s] 发生数据库插入致命错误，停止重试: %s", form_name, insert_errors[0])
                        if worker_thread is not None:
                            data_queue.put(None)
                            worker_thread.join()
                        raise insert_errors[0]

                    self.logger.error(
                        "[%s] 查询发生非网络异常 (%s)，不重试: %s",
                        form_name,
                        type(query_error).__name__,
                        query_error,
                    )
                    if worker_thread is not None:
                        data_queue.put(None)
                        worker_thread.join()
                    raise

            if not use_bulk_buffer:
                data_queue.put(None)
                if worker_thread is not None:
                    worker_thread.join()
                if insert_errors:
                    raise insert_errors[0]
            elif all_rows_buffer:
                count = self.insert_database_data(form_name, all_rows_buffer, db_manager=local_db)
                total_inserted_ref[0] = count
                self.owner._notify_progress(f"[{form_name}] 批量写入完成，共 {count} 条", 75)

            perf_after_query = time.perf_counter()
            query_duration = perf_after_query - perf_after_filter
            self.logger.info("[%s] 查询与插入耗时 %.2f 秒", form_name, query_duration)

            if data is None:
                error_msg = f"查询金蝶数据失败，已重试{max_retries}次"
                self.logger.error("[%s] %s", form_name, error_msg)
                self.owner._notify_progress(f"[{form_name}] {error_msg}", 100)
                end_time = datetime.now()
                local_db.log_sync_operation(
                    sync_type_value,
                    table_name,
                    "sync",
                    0,
                    FAILED_STATUS,
                    error_msg,
                    start_time,
                    end_time,
                    error_type="query_error",
                )
                emit_audit_log(
                    self.logger,
                    "sync_form",
                    "failure",
                    level="error",
                    form_name=form_name,
                    table_name=table_name,
                    sync_type=sync_type_value,
                    reason=error_msg,
                    error_type="query_error",
                )
                return {
                    "status": FAILED_STATUS,
                    "message": error_msg,
                    "record_count": 0,
                    "inserted": 0,
                    "updated": 0,
                    "error_type": "query_error",
                }

            record_count = total_fetched_ref[0]
            inserted_count = total_inserted_ref[0]
            self.owner._notify_progress(f"[{form_name}] 最终共获取 {record_count} 条，插入 {inserted_count} 条数据", 80)
            self.logger.info("[%s] 获取 %s 条，插入 %s 条数据", form_name, record_count, inserted_count)

            insert_duration = 0.0
            if record_count > 0:
                success_rate = (inserted_count / record_count) * 100 if record_count > 0 else 0
                self.owner._notify_progress(
                    f"[{form_name}] 成功插入 {inserted_count}/{record_count} 条数据 (成功率 {success_rate:.1f}%)",
                    90,
                )

                skipped = record_count - inserted_count
                if skipped > 0:
                    if form_name.strip() in self.owner.DEDUPLICATION_FORMS and inserted_count > 0:
                        self.logger.info(
                            "[%s] 已去重跳过 %s 条重复记录，非插入失败 (实际有效数据: %s)",
                            form_name,
                            skipped,
                            inserted_count,
                        )
                        effective_total = record_count - skipped
                        effective_rate = (inserted_count / effective_total * 100) if effective_total > 0 else 100.0
                        self.owner._notify_progress(
                            f"[{form_name}] 去重整合完成，有效数据 {inserted_count} 条 (API返回 {record_count} 条，有效成功率 {effective_rate:.1f}%)",
                            90,
                        )
                    else:
                        self.logger.warning("[%s] 部分数据插入失败: %s 条记录未能插入", form_name, skipped)
            else:
                self.logger.info("[%s] 没有新数据需要同步", form_name)
                self.owner._notify_progress(f"[{form_name}] 没有新数据需要同步", 90)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            local_db.log_sync_operation(
                sync_type_value,
                table_name,
                "sync",
                inserted_count,
                SUCCESS_STATUS,
                f"成功同步 {inserted_count} 条记录，耗时 {duration:.2f} 秒",
                start_time,
                end_time,
            )

            self.logger.info("[%s] 同步完成，耗时 %.2f 秒", form_name, duration)
            self.owner._notify_progress(f"[{form_name}] 同步完成", 100)
            emit_audit_log(
                self.logger,
                "sync_form",
                "finish",
                form_name=form_name,
                table_name=table_name,
                sync_type=sync_type_value,
                status=SUCCESS_STATUS,
                fetched=record_count,
                inserted=inserted_count,
                duration_seconds=duration,
            )
            return {
                "status": SUCCESS_STATUS,
                "message": f"成功同步 {inserted_count} 条记录",
                "record_count": inserted_count,
                "inserted": inserted_count,
                "updated": 0,
                "duration": duration,
                "timing": {
                    "filter": round(filter_duration, 3),
                    "query": round(query_duration, 3),
                    "insert": round(insert_duration, 3),
                },
            }

        except Exception as exc:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            error_type = type(exc).__name__
            error_msg = f"同步失败 ({error_type}): {str(exc)}"
            error_trace = traceback.format_exc()
            self.logger.error("[%s] %s", form_name, error_msg)
            self.logger.debug("错误详情: %s", error_trace)
            self.owner._notify_progress(f"[{form_name}] {error_msg}", 100)

            try:
                local_db.log_sync_operation(
                    sync_type_value,
                    table_name,
                    "sync",
                    0,
                    FAILED_STATUS,
                    error_msg,
                    start_time,
                    end_time,
                    error_type=error_type,
                )
            except Exception:
                pass

            emit_audit_log(
                self.logger,
                "sync_form",
                "failure",
                level="error",
                form_name=form_name,
                table_name=table_name,
                sync_type=sync_type_value,
                reason=error_msg,
                error_type=error_type,
                duration_seconds=duration,
            )

            return {
                "status": FAILED_STATUS,
                "message": error_msg,
                "record_count": 0,
                "inserted": 0,
                "updated": 0,
                "error_type": error_type,
                "duration": duration,
            }
        finally:
            try:
                local_db.disconnect()
            except Exception:
                pass

    def query_kingdee_data(
        self,
        form_name: str,
        filter_string: str | None = None,
        page_callback=None,
        start_row: int = 0,
        sync_type=None,
    ) -> Optional[List[Dict]]:
        """Query Kingdee with the assembled form query parameters."""
        try:
            form_queries = config_manager.get_form_queries()
            query_params = form_queries.get(form_name, {}).copy()

            if filter_string:
                query_params["FilterString"] = filter_string
            if start_row > 0:
                query_params["StartRow"] = start_row
            if self._is_full_or_complete(sync_type):
                query_params["__preferred_page_size__"] = 50000

            return kingdee_client.query_data(form_name, query_params, page_callback=page_callback)
        except Exception as exc:
            self.logger.error("查询金蝶 %s 数据失败: %s", form_name, exc)
            return None

    def insert_database_data(self, form_name: str, data: List[Dict], db_manager=None) -> int:
        """Insert queried form data using writer mappings."""
        manager = db_manager or mysql_manager
        method_name = self.owner.INSERT_METHOD_MAP.get(form_name)
        if method_name:
            try:
                return manager.execute_writer(method_name, data)
            except KeyError as exc:
                self.logger.error("Writer 映射无效: form=%s, method=%s, error=%s", form_name, method_name, exc)
                return 0

        if form_name == "科目余额表":
            return manager.insert_generic_data("GL_RPT_AccountBalance", data)

        self.logger.error("未知的表单类型或未配置插入方法: %s", form_name)
        return 0

    def truncate_table_for_complete(self, table_name: str, manager: MySQLManager) -> bool:
        """Truncate a target table before complete sync."""
        try:
            if not getattr(manager, "cursor", None):
                manager.connect()
            manager.cursor.execute(f"TRUNCATE TABLE {table_name}")
            self.logger.info("已清空表 %s", table_name)
            return True
        except Exception as exc:
            self.logger.error("清空表 %s 失败: %s", table_name, exc)
            return False
