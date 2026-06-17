"""Single-form sync execution helpers for DataSyncManager."""

from __future__ import annotations

import logging
import queue
import threading
import time
import traceback
from dataclasses import asdict
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from src.config.config_manager import config_manager
from src.core.audit_logging import emit_audit_log
from src.core.filter_builder import FilterBuilder
from src.core.kingdee_api import kingdee_client
from src.core.metrics import metrics_collector
from src.core.mysql_manager import MySQLManager, mysql_manager
from src.core.retry_manager import SyncCheckpoint
from src.core.sync_failure_telemetry import (
    WriteFailureDetail,
    build_record_keys,
    classify_failure,
    summarize_failure_details,
)
from src.core.sync_log_repository import SyncLogRepository
from src.core.sync_run_repository import SyncRunRepository
from src.core.upsert_engine_mysql import UpsertEngineMySQL
from src.core.upsert_engine_sqlserver import UpsertEngineSqlServer
from src.core.write_outcome import WriteOutcome
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
    local_db.field_mapping_resolver = getattr(base_manager, "field_mapping_resolver", None)
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
        owner: DataSyncManager,
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

    def sync_single_form(self, form_name: str, sync_type, run_id: str | None = None) -> dict[str, Any]:
        """Run one form end-to-end while DataSyncManager orchestrates scheduling."""
        if form_name == "科目余额表":
            return self.owner._sync_account_balance_form(form_name, sync_type)

        start_time = datetime.now()
        perf_start = time.perf_counter()
        local_db = create_shared_db_manager(mysql_manager)
        table_name = self.owner.table_mapping.get(form_name)
        sync_type_value = self._sync_type_value(sync_type)
        metrics_run_id = str(run_id or "")
        metrics_collector.start_sync(metrics_run_id, form_name)
        metrics_success = False

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
                metrics_collector.record_error(metrics_run_id, form_name)
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
                    "failure_categories": {},
                    "failure_details": [],
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
                        "failure_categories": {},
                        "failure_details": [],
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
                resume_start_row = checkpoint.next_start_row or checkpoint.start_row
                total_inserted_ref_init = checkpoint.total_inserted
                total_fetched_ref_init = checkpoint.total_fetched
                self.logger.info("[%s] 检测到断点，从 StartRow=%s 继续同步", form_name, resume_start_row)
            else:
                total_inserted_ref_init = 0
                total_fetched_ref_init = 0

            max_retries = 3
            retry_count = 0
            total_inserted_ref = [total_inserted_ref_init]
            total_fetched_ref = [total_fetched_ref_init]
            total_invalid_ref = [0]
            total_deduped_ref = [0]
            failure_details_ref: list[WriteFailureDetail] = []
            insert_duration_ref = [0.0]
            fetched_next_start_row_ref = [resume_start_row]
            durable_next_start_row_ref = [resume_start_row]
            last_written_record_keys_ref = [list(getattr(checkpoint, "last_written_record_keys", [])) if checkpoint else []]
            last_error_category_ref = [str(getattr(checkpoint, "last_error_category", "")) if checkpoint else ""]

            queue_size = 50 if self._is_full_or_complete(sync_type) else 10
            data_queue: queue.Queue[tuple[int, list[dict[str, Any]]] | None] = queue.Queue(maxsize=queue_size)
            insert_errors: list[Exception] = []
            use_bulk_buffer = self._is_full_or_complete(sync_type)
            all_rows_buffer: list[dict[str, Any]] = []

            def is_durable_page(outcome: WriteOutcome, page_data: list[dict[str, Any]]) -> bool:
                return (
                    outcome.inserted == len(page_data)
                    and outcome.invalid == 0
                    and outcome.deduped == 0
                    and outcome.failed == 0
                )

            def save_pending_checkpoint(error_category: str) -> None:
                if not self._is_incremental(sync_type):
                    return
                last_error_category_ref[0] = error_category
                self.owner._checkpoint_manager.save_checkpoint(
                    SyncCheckpoint(
                        form_name=form_name,
                        table_name=table_name,
                        sync_type=self._sync_type_value(sync_type),
                        start_row=durable_next_start_row_ref[0],
                        next_start_row=durable_next_start_row_ref[0],
                        total_inserted=total_inserted_ref[0],
                        total_fetched=total_fetched_ref[0],
                        filter_string=filter_string or "",
                        status="pending",
                        last_written_record_keys=last_written_record_keys_ref[0],
                        last_error_category=last_error_category_ref[0],
                    )
                )

            def insert_worker() -> None:
                while True:
                    queue_item = data_queue.get()
                    if queue_item is None:
                        data_queue.task_done()
                        break
                    page_start_row, page_data = queue_item
                    try:
                        insert_start = time.perf_counter()
                        raw_outcome = self.insert_database_data(form_name, page_data, db_manager=local_db)
                        outcome = self._normalize_write_outcome(form_name, table_name, page_data, raw_outcome)
                        insert_duration = time.perf_counter() - insert_start
                        insert_duration_ref[0] += insert_duration
                        metrics_collector.record_write_outcome(metrics_run_id, form_name, outcome, insert_duration)
                        total_inserted_ref[0] += outcome.inserted
                        total_invalid_ref[0] += outcome.invalid
                        total_deduped_ref[0] += outcome.deduped
                        total_fetched_ref[0] += len(page_data)
                        failure_details_ref.extend(outcome.failure_details)
                        if self._is_incremental(sync_type) and is_durable_page(outcome, page_data):
                            next_start_row = page_start_row + len(page_data)
                            durable_next_start_row_ref[0] = next_start_row
                            last_written_record_keys_ref[0] = build_record_keys(page_data)
                            last_error_category_ref[0] = ""
                            self.owner._checkpoint_manager.save_checkpoint(
                                SyncCheckpoint(
                                    form_name=form_name,
                                    table_name=table_name,
                                    sync_type=self._sync_type_value(sync_type),
                                    start_row=next_start_row,
                                    next_start_row=next_start_row,
                                    total_inserted=total_inserted_ref[0],
                                    total_fetched=total_fetched_ref[0],
                                    filter_string=filter_string or "",
                                    status="pending",
                                    last_written_record_keys=last_written_record_keys_ref[0],
                                    last_error_category=last_error_category_ref[0],
                                )
                            )
                        self.owner._notify_progress(f"[{form_name}] 已同步 {total_inserted_ref[0]} 条数据...", 60)
                    except Exception as exc:
                        self.logger.error("[%s] 异步插入数据库失败: %s", form_name, exc)
                        metrics_collector.record_error(metrics_run_id, form_name)
                        insert_errors.append(exc)
                    finally:
                        data_queue.task_done()

            if not use_bulk_buffer:
                worker_thread = threading.Thread(target=insert_worker, name=f"InsertWorker-{form_name}")
                worker_thread.start()
            else:
                worker_thread = None

            def handle_page_data(page_data: list[dict[str, Any]]) -> None:
                if not page_data:
                    return
                if use_bulk_buffer:
                    all_rows_buffer.extend(page_data)
                    total_fetched_ref[0] += len(page_data)
                    self.owner._notify_progress(f"[{form_name}] 已加载 {total_fetched_ref[0]} 条数据...", 50)
                    return

                if insert_errors:
                    raise Exception(f"插入线程出错: {insert_errors[0]}")
                page_start_row = fetched_next_start_row_ref[0]
                fetched_next_start_row_ref[0] += len(page_data)
                data_queue.put((page_start_row, page_data))

            data = None
            while retry_count < max_retries:
                try:
                    data = self.query_kingdee_data(
                        form_name,
                        filter_string,
                        page_callback=handle_page_data,
                        start_row=durable_next_start_row_ref[0],
                        sync_type=sync_type,
                    )
                    if data is not None:
                        break

                    retry_count += 1
                    if retry_count < max_retries:
                        save_pending_checkpoint("query_error")
                        self.logger.warning("[%s] 查询失败，%s/%s 次重试...", form_name, retry_count, max_retries)
                        self.owner._notify_progress(
                            f"[{form_name}] 查询失败，正在重试 ({retry_count}/{max_retries})...",
                            35,
                        )
                        delay = min(1.0 * (2 ** (retry_count - 1)), 60.0)
                        self.logger.info("[%s] 将在 %.1f秒 后重试...", form_name, delay)
                        time.sleep(delay)
                except Exception as query_error:
                    if insert_errors:
                        self.logger.error("[%s] 发生数据库插入致命错误，停止重试: %s", form_name, insert_errors[0])
                        if worker_thread is not None:
                            data_queue.put(None)
                            worker_thread.join()
                        raise insert_errors[0] from query_error

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
                insert_start = time.perf_counter()
                raw_outcome = self.insert_database_data(form_name, all_rows_buffer, db_manager=local_db)
                outcome = self._normalize_write_outcome(form_name, table_name, all_rows_buffer, raw_outcome)
                insert_duration_ref[0] = time.perf_counter() - insert_start
                metrics_collector.record_write_outcome(metrics_run_id, form_name, outcome, insert_duration_ref[0])
                total_inserted_ref[0] = outcome.inserted
                total_invalid_ref[0] = outcome.invalid
                total_deduped_ref[0] = outcome.deduped
                failure_details_ref.extend(outcome.failure_details)
                self.owner._notify_progress(f"[{form_name}] 批量写入完成，共 {outcome.inserted} 条", 75)

            perf_after_query = time.perf_counter()
            query_duration = perf_after_query - perf_after_filter
            self.logger.info("[%s] 查询与插入耗时 %.2f 秒", form_name, query_duration)
            failure_categories = summarize_failure_details(failure_details_ref)

            if data is None:
                error_msg = f"查询金蝶数据失败，已重试{max_retries}次"
                self.logger.error("[%s] %s", form_name, error_msg)
                self.owner._notify_progress(f"[{form_name}] {error_msg}", 100)
                metrics_collector.record_error(metrics_run_id, form_name)
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
                    "failure_categories": failure_categories,
                    "failure_details": [asdict(detail) for detail in failure_details_ref],
                }

            record_count = total_fetched_ref[0]
            inserted_count = total_inserted_ref[0]
            self.owner._notify_progress(f"[{form_name}] 最终共获取 {record_count} 条，插入 {inserted_count} 条数据", 80)
            self.logger.info("[%s] 获取 %s 条，插入 %s 条数据", form_name, record_count, inserted_count)

            insert_duration = insert_duration_ref[0]
            summary = self._build_write_summary(
                form_name,
                fetched=record_count,
                outcome=WriteOutcome(
                    inserted=inserted_count,
                    invalid=total_invalid_ref[0],
                    deduped=total_deduped_ref[0],
                    failed=max(0, record_count - total_invalid_ref[0] - total_deduped_ref[0] - inserted_count),
                    failure_details=failure_details_ref,
                ),
            )
            if record_count > 0:
                success_rate = (inserted_count / record_count) * 100 if record_count > 0 else 0
                self.owner._notify_progress(
                    f"[{form_name}] 成功插入 {inserted_count}/{record_count} 条数据 (成功率 {success_rate:.1f}%)",
                    90,
                )
                if summary["invalid"] > 0:
                    self.logger.warning("[%s] 无效记录跳过: %s 条", form_name, summary["invalid"])
                if summary["deduped"] > 0:
                    self.logger.info("[%s] 去重跳过: %s 条", form_name, summary["deduped"])
                if summary["failed"] > 0:
                    deduped = summary.get("deduped", 0)
                    real_failures = summary["failed"] - deduped
                    if deduped > 0 and real_failures <= 0:
                        self.logger.info(
                            "[%s] 写入完成: 插入 %s 条，去重过滤 %s 条",
                            form_name,
                            inserted_count,
                            deduped,
                        )
                    else:
                        self.logger.warning(
                            "[%s] 写库失败: %s 条 (去重 %s 条, SQL错误 %s 条)",
                            form_name,
                            summary["failed"],
                            deduped,
                            real_failures,
                        )
                        metrics_collector.record_error(metrics_run_id, form_name)
                    metrics_collector.record_error(metrics_run_id, form_name)
                for detail in failure_details_ref:
                    emit_audit_log(
                        self.logger,
                        "sync_form",
                        "write_failure_detail",
                        form_name=form_name,
                        table_name=table_name,
                        sync_type=sync_type_value,
                        category=detail.category,
                        error_type=detail.error_type,
                        failed_count=detail.failed_count,
                        retryable=detail.retryable,
                        record_keys=detail.record_keys,
                        message=detail.message,
                    )
            else:
                self.logger.info("[%s] 没有新数据需要同步", form_name)
                self.owner._notify_progress(f"[{form_name}] 没有新数据需要同步", 90)

            result_status = self._resolve_result_status(inserted_count, summary["failed"])
            result_message = self._build_result_message(result_status, inserted_count, summary["failed"])

            if data is not None and result_status == SUCCESS_STATUS:
                self.owner._checkpoint_manager.clear_checkpoint(
                    form_name,
                    table_name,
                    self._sync_type_value(sync_type),
                )

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            local_db.log_sync_operation(
                sync_type_value,
                table_name,
                "sync",
                inserted_count,
                result_status,
                f"{result_message}，耗时 {duration:.2f} 秒",
                start_time,
                end_time,
            )

            self.logger.info("[%s] 同步完成，耗时 %.2f 秒", form_name, duration)
            metrics_success = result_status != FAILED_STATUS
            if result_status == SUCCESS_STATUS:
                self.owner._notify_progress(f"[{form_name}] 同步完成", 100)
            elif result_status == PARTIAL_STATUS:
                self.owner._notify_progress(f"[{form_name}] 同步部分完成", 100)
            else:
                self.owner._notify_progress(f"[{form_name}] 同步失败", 100)
            emit_audit_log(
                self.logger,
                "sync_form",
                "finish",
                form_name=form_name,
                table_name=table_name,
                sync_type=sync_type_value,
                status=result_status,
                fetched=record_count,
                inserted=inserted_count,
                duration_seconds=duration,
            )
            return {
                "status": result_status,
                "message": result_message,
                "record_count": inserted_count,
                "fetched": summary["fetched"],
                "invalid": summary["invalid"],
                "deduped": summary["deduped"],
                "failed": summary["failed"],
                "failure_categories": failure_categories,
                "failure_details": [asdict(detail) for detail in failure_details_ref],
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
            metrics_collector.record_error(metrics_run_id, form_name)

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
                "failure_categories": {},
                "failure_details": [],
            }
        finally:
            metrics_collector.end_sync(metrics_run_id, form_name, success=metrics_success)
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
    ) -> list[dict] | None:
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

    def _build_write_summary(self, form_name: str, fetched: int, outcome: WriteOutcome) -> dict[str, int]:
        is_dedup_table = form_name.strip() in self.owner.DEDUPLICATION_FORMS
        deduped = outcome.deduped if is_dedup_table else 0
        invalid = outcome.invalid
        raw_failed = max(0, fetched - invalid - deduped - outcome.inserted)
        return {
            "fetched": fetched,
            "inserted": outcome.inserted,
            "invalid": invalid,
            "deduped": deduped,
            "failed": raw_failed,
        }

    @staticmethod
    def _resolve_result_status(inserted: int, failed: int) -> str:
        if failed <= 0:
            return SUCCESS_STATUS
        if inserted > 0:
            return PARTIAL_STATUS
        return FAILED_STATUS

    @staticmethod
    def _build_result_message(status: str, inserted: int, failed: int) -> str:
        if status == SUCCESS_STATUS:
            return f"成功同步 {inserted} 条记录"
        if status == PARTIAL_STATUS:
            return f"部分同步成功，成功 {inserted} 条，写库失败 {failed} 条"
        return f"同步失败，写库失败 {failed} 条"

    def _resolve_failure_details(
        self,
        form_name: str,
        table_name: str | None,
        failed_rows: list[dict[str, Any]],
        outcome: WriteOutcome,
    ) -> list[WriteFailureDetail]:
        details = list(outcome.failure_details or [])
        if details or outcome.failed <= 0:
            return details
        fallback_detail = classify_failure(
            form_name=form_name,
            table_name=table_name or "",
            error_type="WriteFailure",
            message="write failed without detail",
            failed_rows=failed_rows[: outcome.failed],
        )
        fallback_detail.failed_count = max(1, outcome.failed)
        return [fallback_detail]

    def _normalize_write_outcome(
        self,
        form_name: str,
        table_name: str | None,
        rows: list[dict[str, Any]],
        outcome: WriteOutcome,
    ) -> WriteOutcome:
        summary = self._build_write_summary(form_name, fetched=len(rows), outcome=outcome)
        normalized = WriteOutcome(
            inserted=summary["inserted"],
            invalid=summary["invalid"],
            deduped=summary["deduped"],
            failed=summary["failed"],
            failure_details=list(outcome.failure_details or []),
        )
        normalized.failure_details = self._resolve_failure_details(form_name, table_name, rows, normalized)
        return normalized

    def insert_database_data(self, form_name: str, data: list[dict], db_manager=None) -> WriteOutcome:
        """Insert queried form data using writer mappings."""
        manager = db_manager or mysql_manager
        method_name = self.owner.INSERT_METHOD_MAP.get(form_name)
        if method_name:
            try:
                return manager.execute_writer_with_outcome(method_name, data)
            except KeyError as exc:
                self.logger.error("Writer 映射无效: form=%s, method=%s, error=%s", form_name, method_name, exc)
                return WriteOutcome(failed=len(data))

        if form_name == "科目余额表":
            inserted = manager.insert_generic_data("GL_RPT_AccountBalance", data)
            return WriteOutcome.from_insert_count(inserted)

        self.logger.error("未知的表单类型或未配置插入方法: %s", form_name)
        return WriteOutcome(failed=len(data))

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
