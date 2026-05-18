"""
数据同步逻辑模块
实现增量、全量、完全同步功能
"""

import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import requests

from src.config.config_manager import config_manager
from src.core.account_balance_sync import account_balance_sync_manager
from src.core.audit_logging import emit_audit_log
from src.core.circuit_breaker import LocalCircuitBreaker
from src.core.filter_builder import FilterBuilder
from src.core.form_sync_runner import FormSyncRunner, create_shared_db_manager
from src.core.kingdee_api import kingdee_client
from src.core.metrics import metrics_collector
from src.core.mysql_manager import MySQLManager, mysql_manager
from src.core.retry_manager import CheckpointManager, SyncCheckpoint

# 配置日志
logger = logging.getLogger(__name__)


class SyncType(Enum):
    """同步类型枚举"""

    INCREMENTAL = "incremental"  # 增量同步
    FULL = "full"  # 全量同步
    COMPLETE = "complete"  # 完全同步

    @classmethod
    def from_string(cls, value: str) -> "SyncType":
        """从字符串转换，支持 'reset' 作为 'complete' 的别名"""
        if value == "reset":
            return cls.COMPLETE
        return cls(value)


class SyncStatus(Enum):
    """同步状态枚举"""

    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    FAILED_ABNORMAL_EXIT = "failed_abnormal_exit"


class DataSyncManager:
    """数据同步管理器"""

    PRIORITY_MAP = {
        # Group 0 (priority 0): 小表 — 极快完成，为后续组释放 API 带宽
        "仓库": 0,
        "物料": 0,
        "客户资料": 0,
        "即时库存": 0,
        "物料清单": 0,
        "物料清单子项": 0,
        "预测订单": 0,
        # Group 1 (priority 1): 中表 — 正常数据量
        "销售订单": 1,
        "采购订单": 1,
        "应付单": 1,
        "销售出库单": 1,
        "销售退货单": 1,
        "发货通知单": 1,
        "委外订单": 1,
        "科目余额表": 1,
        "生产订单明细": 1,
        "生产入库单": 1,
        # Group 2 (priority 2): 大表 — 独占所有 worker 和 API 带宽
        "生产订单主表": 2,
        "生产用料清单主表": 2,
        "生产用料清单明细表": 2,
    }

    DEDUPLICATION_FORMS = {"物料", "生产订单主表", "生产用料清单主表", "生产订单明细", "生产用料清单", "即时库存"}
    ISOLATED_COMPLETE_FORMS = set()
    # INSERT_METHOD_MAP is now loaded from tables.json via config_manager.get_insert_method_map()

    def __init__(self):
        # 从配置管理器加载表映射
        self.table_mapping = config_manager.get_table_mapping()
        # 从 tables.json 加载 insert 方法映射（覆盖硬编码的类变量占位）
        self.INSERT_METHOD_MAP = config_manager.get_insert_method_map()
        self.sync_callbacks = []  # 同步进度回调
        self._checkpoint_manager = CheckpointManager()
        self.filter_builder = FilterBuilder(logger_=logger)
        self.form_sync_runner = FormSyncRunner(self, self.filter_builder, logger_=logger)
        self._active_run_id: str | None = None
        self._active_run_message = ""
        self._shutdown_requested = threading.Event()
        self._shutdown_reason = ""
        self.circuit_breaker = LocalCircuitBreaker(
            enabled=True,
            threshold=3,
            cooldown_seconds=30,
        )
        self._refresh_circuit_breaker_config()

    def add_sync_callback(self, callback):
        """添加同步进度回调函数"""
        self.sync_callbacks.append(callback)

    def remove_sync_callback(self, callback):
        """移除同步进度回调函数"""
        try:
            self.sync_callbacks.remove(callback)
        except ValueError:
            # 如果回调不在列表中，忽略
            pass

    def _notify_progress(self, message: str, progress: int = 0):
        """通知同步进度"""
        if self._active_run_id:
            self._active_run_message = str(message)
        for callback in self.sync_callbacks:
            try:
                callback(message, progress)
            except Exception as e:
                logger.error(f"回调函数执行失败: {str(e)}")

    def request_shutdown(self, reason: str = "application_exit") -> None:
        self._shutdown_reason = reason
        self._shutdown_requested.set()

    def clear_shutdown(self) -> None:
        self._shutdown_reason = ""
        self._shutdown_requested.clear()

    def is_shutdown_requested(self) -> bool:
        return self._shutdown_requested.is_set()

    def _refresh_circuit_breaker_config(self) -> None:
        sync_config = config_manager.get_sync_config()
        self.circuit_breaker.reconfigure(
            enabled=bool(sync_config.get("circuit_breaker_enabled", True)),
            threshold=max(1, int(sync_config.get("circuit_breaker_threshold", 3) or 3)),
            cooldown_seconds=max(
                0,
                int(sync_config.get("circuit_breaker_cooldown_secs", 30) or 30),
            ),
        )

    def _run_heartbeat_loop(self, run_id: str, heartbeat_stop: threading.Event, heartbeat_interval: int) -> None:
        """心跳线程逻辑"""
        while not heartbeat_stop.wait(heartbeat_interval):
            try:
                mysql_manager.heartbeat_sync_run(run_id, self._active_run_message or "任务运行中", datetime.now())
            except Exception as exc:
                logger.debug("更新同步任务心跳失败: %s", exc)

    def _finalize_run(
        self,
        run_id: str,
        sync_type: SyncType,
        requested_forms: list[str],
        results: dict[str, dict[str, Any]],
        total_records: int,
        failed_tables: list[str],
        run_status: SyncStatus,
        message: str,
        start_time: datetime,
        end_time: datetime | None = None,
    ) -> None:
        """记录同步任务完成状态"""
        final_dt = end_time or datetime.now()
        try:
            success_count = sum(
                1
                for result in results.values()
                if isinstance(result, dict) and result.get("status") == SyncStatus.SUCCESS.value
            )
            failure_count = max(0, len(requested_forms) - success_count)
            details = {
                "results": results,
                "metrics": metrics_collector.export_run_snapshot(run_id, list(results.keys())),
                "failed_forms": list(failed_tables),
            }
            mysql_manager.finish_sync_run(
                run_id=run_id,
                sync_type=sync_type.value,
                forms=requested_forms,
                total_records=total_records,
                success_count=success_count,
                failure_count=failure_count,
                status=run_status.value,
                message=message,
                start_time=start_time,
                end_time=final_dt,
                failed_forms=failed_tables,
                details=details,
            )
        except Exception as exc:
            logger.debug("记录任务级历史失败: %s", exc)

        try:
            duration_seconds = (final_dt - start_time).total_seconds()
        except Exception:
            duration_seconds = 0.0
        self._record_run_stats(
            run_id=run_id,
            sync_type=sync_type,
            run_status=run_status,
            total_records=total_records,
            duration_seconds=duration_seconds,
            failed_forms=failed_tables,
            results=results,
        )

    def _record_run_stats(
        self,
        run_id: str,
        sync_type: SyncType,
        run_status: SyncStatus,
        total_records: int,
        duration_seconds: float,
        failed_forms: list[str],
        results: dict[str, dict[str, Any]],
    ) -> None:
        """将每轮同步结果（轮次级 + 表单级）记录到本地 SQLite"""
        import os
        import sqlite3
        from datetime import datetime

        db_path = os.path.join("logs", "sync_stats.db")
        try:
            conn = sqlite3.connect(db_path, timeout=2)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS run_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    sync_type TEXT,
                    status TEXT,
                    total_records INTEGER,
                    duration_seconds REAL,
                    failed_forms TEXT,
                    finished_at TEXT
                )
            """)
            conn.execute(
                "INSERT INTO run_stats VALUES (NULL,?,?,?,?,?,?,datetime('now','localtime'))",
                (
                    run_id,
                    sync_type.value,
                    run_status.value,
                    total_records or 0,
                    duration_seconds,
                    ",".join(failed_forms or []),
                ),
            )

            conn.execute("""
                CREATE TABLE IF NOT EXISTS form_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    form_name TEXT,
                    table_name TEXT,
                    fetched INTEGER,
                    inserted INTEGER,
                    status TEXT,
                    duration_seconds REAL,
                    finished_at TEXT
                )
            """)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for form_name, res in results.items():
                if not isinstance(res, dict):
                    continue
                conn.execute(
                    "INSERT INTO form_stats "
                    "(run_id, form_name, table_name, fetched, inserted, "
                    " status, duration_seconds, finished_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (
                        run_id,
                        str(form_name),
                        str(res.get("table_name", "")),
                        int(res.get("fetched", 0)),
                        int(res.get("inserted", 0)),
                        str(res.get("status", "unknown")),
                        float(res.get("duration_seconds", 0)),
                        now_str,
                    ),
                )

            conn.commit()
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _determine_final_status(
        self, failed_tables: list[str], total_tables: int, total_records: int
    ) -> tuple[SyncStatus, str]:
        """判定最终同步状态"""
        if not failed_tables:
            return SyncStatus.SUCCESS, f"所有表同步成功，共同步 {total_records} 条记录"
        if len(failed_tables) == total_tables:
            return SyncStatus.FAILED, "所有表同步失败"
        return SyncStatus.PARTIAL, f"部分表同步成功，失败的表: {', '.join(failed_tables)}"

    def sync_data(self, form_names: list[str], sync_type: SyncType = SyncType.INCREMENTAL) -> dict[str, Any]:
        """同步数据主方法。"""
        start_time = datetime.now()
        self._refresh_circuit_breaker_config()
        if self.is_shutdown_requested():
            message = f"同步任务拒绝启动: {self._shutdown_reason or 'shutdown requested'}"
            return self._create_sync_result(SyncStatus.FAILED_ABNORMAL_EXIT, message, start_time)
        self._notify_progress("开始数据同步...", 0)

        if form_names is None:
            form_names = list(self.table_mapping.keys())

        requested_forms = list(form_names)
        run_id = uuid.uuid4().hex
        results: dict[str, dict[str, Any]] = {}
        total_records = 0
        failed_tables: list[str] = []
        final_status = SyncStatus.FAILED
        final_message = "同步任务未正常完成"
        final_end_time = start_time
        final_result: dict[str, Any] | None = None
        run_started = False
        sync_config = config_manager.get_sync_config()
        heartbeat_interval = int(sync_config.get("run_heartbeat_interval_secs", 15) or 15)
        heartbeat_timeout = int(sync_config.get("run_heartbeat_timeout_secs", 120) or 120)
        heartbeat_stop = threading.Event()
        heartbeat_thread: threading.Thread | None = None

        self._active_run_id = run_id
        self._active_run_message = "开始数据同步..."

        emit_audit_log(
            logger,
            "sync_run",
            "start",
            run_id=run_id,
            sync_type=sync_type.value,
            form_count=len(requested_forms),
            forms=requested_forms,
            heartbeat_interval=heartbeat_interval,
            heartbeat_timeout=heartbeat_timeout,
            start_time=start_time,
        )

        total_tables = len(requested_forms)
        completed_tables = 0

        def calc_progress() -> int:
            if total_tables <= 0:
                return 80
            return 20 + (completed_tables * 60 // total_tables)

        def collect_result(form_name: str, result: dict[str, Any]):
            nonlocal total_records, completed_tables
            results[form_name] = result
            if result["status"] in (SyncStatus.SUCCESS.value, SyncStatus.PARTIAL.value):
                total_records += int(result.get("record_count", 0) or 0)
            if result["status"] != SyncStatus.SUCCESS.value:
                failed_tables.append(form_name)
            completed_tables += 1
            self._notify_progress(
                f"已完成 {form_name} 同步 ({completed_tables}/{total_tables})",
                calc_progress(),
            )

        try:
            if not self._check_connections():
                final_status = SyncStatus.FAILED
                final_message = "连接检查失败"
                final_end_time = datetime.now()
                final_result = self._create_sync_result(final_status, final_message, start_time)
                final_result["run_id"] = run_id
                emit_audit_log(
                    logger,
                    "sync_run",
                    "failure",
                    level="error",
                    run_id=run_id,
                    sync_type=sync_type.value,
                    reason=final_message,
                    error_type="connection_check_failed",
                )
                return final_result

            self._notify_progress("连接检查完成，开始同步数据...", 10)
            try:
                run_started = bool(mysql_manager.start_sync_run(run_id, sync_type.value, requested_forms, start_time))
            except Exception as exc:
                logger.debug("记录任务开始失败: %s", exc)
                run_started = False

            if run_started:
                mysql_manager.heartbeat_sync_run(run_id, "连接检查完成，准备执行同步", start_time)
                heartbeat_thread = threading.Thread(
                    target=lambda: self._run_heartbeat_loop(run_id, heartbeat_stop, heartbeat_interval),
                    name=f"SyncHeartbeat-{run_id[:8]}",
                    daemon=True,
                )
                heartbeat_thread.start()

            isolated_complete_forms: list[str] = []
            if sync_type == SyncType.COMPLETE:
                isolated_complete_forms = [
                    form_name for form_name in requested_forms if form_name in self.ISOLATED_COMPLETE_FORMS
                ]
                if isolated_complete_forms:
                    form_names = [
                        form_name for form_name in requested_forms if form_name not in self.ISOLATED_COMPLETE_FORMS
                    ]
                    logger.info("检测到需要单独执行完全同步的表单: %s", ", ".join(isolated_complete_forms))
                    self._notify_progress(
                        f"检测到 {', '.join(isolated_complete_forms)}，将单独执行完全同步...",
                        15,
                    )

            table_concurrency = sync_config.get("table_concurrency", sync_config.get("fetch_concurrency", 1))
            try:
                table_concurrency = max(1, int(table_concurrency))
            except Exception:
                table_concurrency = 1
            if sync_type in (SyncType.FULL, SyncType.COMPLETE):
                table_concurrency = min(8, max(table_concurrency, 8))

            priority_map = self.PRIORITY_MAP
            grouped_forms: dict[int, list[str]] = {}
            for form_name in form_names:
                priority = priority_map.get(form_name, 1)
                grouped_forms.setdefault(priority, []).append(form_name)

            for _, group in sorted(grouped_forms.items(), key=lambda item: item[0]):
                if self.is_shutdown_requested():
                    final_status = SyncStatus.FAILED_ABNORMAL_EXIT
                    final_message = (
                        f"同步在关闭过程中停止调度新任务: {self._shutdown_reason or 'shutdown requested'}"
                    )
                    break
                if table_concurrency <= 1 or len(group) <= 1:
                    for form_name in group:
                        self._notify_progress(f"正在同步 {form_name}...", calc_progress())
                        result = self._sync_single_form(form_name, sync_type, run_id=run_id)
                        collect_result(form_name, result)
                else:
                    self._notify_progress(f"开始并发同步 {len(group)} 个表...", calc_progress())
                    with ThreadPoolExecutor(max_workers=table_concurrency) as executor:
                        future_map = {
                            executor.submit(self._sync_single_form, form_name, sync_type, run_id): form_name
                            for form_name in group
                        }
                        for future in as_completed(future_map):
                            form_name = future_map[future]
                            try:
                                result = future.result()
                            except Exception as exc:
                                logger.error("同步 %s 失败: %s", form_name, exc)
                                result = {
                                    "status": SyncStatus.FAILED.value,
                                    "message": f"同步失败 ({type(exc).__name__}): {str(exc)}",
                                    "record_count": 0,
                                    "error_type": type(exc).__name__,
                                }
                            collect_result(form_name, result)

            for form_name in isolated_complete_forms:
                self._notify_progress(f"正在单独完全同步 {form_name}...", calc_progress())
                result = self._sync_single_form(form_name, SyncType.COMPLETE, run_id=run_id)
                collect_result(form_name, result)

            final_end_time = datetime.now()
            config_manager.update_config("SYNC", "last_sync_time", final_end_time.strftime("%Y-%m-%d %H:%M:%S"))

            final_status, final_message = self._determine_final_status(failed_tables, total_tables, total_records)

            if final_status == SyncStatus.SUCCESS:
                self._notify_progress("数据同步完成", 100)
            elif final_status == SyncStatus.FAILED:
                self._notify_progress("数据同步失败", 100)
            else:
                self._notify_progress("数据同步部分完成", 100)

            final_result = {
                "run_id": run_id,
                "status": final_status.value,
                "message": final_message,
                "total_records": total_records,
                "start_time": start_time,
                "end_time": final_end_time,
                "duration": (final_end_time - start_time).total_seconds(),
                "details": results,
            }
            return final_result
        except Exception as exc:
            final_status = SyncStatus.FAILED
            final_message = f"同步过程中发生错误 ({type(exc).__name__}): {str(exc)}"
            final_end_time = datetime.now()
            logger.error("数据同步过程中发生错误: %s", exc, exc_info=True)
            emit_audit_log(
                logger,
                "sync_run",
                "failure",
                level="error",
                run_id=run_id,
                sync_type=sync_type.value,
                reason=final_message,
                error_type=type(exc).__name__,
                failed_forms=failed_tables,
                total_records=total_records,
            )
            final_result = {
                "run_id": run_id,
                "status": final_status.value,
                "message": final_message,
                "total_records": total_records,
                "start_time": start_time,
                "end_time": final_end_time,
                "duration": (final_end_time - start_time).total_seconds(),
                "details": results,
            }
            return final_result
        finally:
            heartbeat_stop.set()
            if heartbeat_thread is not None and heartbeat_thread.is_alive():
                heartbeat_thread.join(timeout=2)

            try:
                mysql_manager.heartbeat_sync_run(
                    run_id,
                    final_message or self._active_run_message or "任务结束",
                    final_end_time or datetime.now(),
                )
            except Exception:
                pass

            self._finalize_run(
                run_id,
                sync_type,
                requested_forms,
                results,
                total_records,
                failed_tables,
                final_status,
                final_message,
                start_time,
                final_end_time,
            )
            emit_audit_log(
                logger,
                "sync_run",
                "finish",
                run_id=run_id,
                sync_type=sync_type.value,
                status=final_status.value,
                message=final_message,
                total_records=total_records,
                failed_forms=failed_tables,
                duration_seconds=(final_end_time - start_time).total_seconds(),
            )

            try:
                if not config_manager.get_kingdee_config().get("keep_session_alive", False):
                    kingdee_client.logout(force=True)
            except Exception:
                pass

            self._active_run_id = None
            self._active_run_message = ""

    def _sync_single_form(self, form_name: str, sync_type: SyncType, run_id: str | None = None) -> dict[str, Any]:
        """Delegate single-form execution to the dedicated form sync runner."""
        self._refresh_circuit_breaker_config()
        if not self.circuit_breaker.allow(form_name):
            return self._create_circuit_open_result(form_name)

        try:
            result = self.form_sync_runner.sync_single_form(form_name, sync_type, run_id=run_id)
        except Exception as exc:
            self.circuit_breaker.record_failure(form_name, type(exc).__name__)
            raise

        self._record_circuit_breaker_result(form_name, result)
        return result

    def _create_circuit_open_result(self, form_name: str) -> dict[str, Any]:
        return {
            "status": "circuit_open",
            "message": f"[{form_name}] 熔断器开启，暂时跳过同步",
            "record_count": 0,
            "inserted": 0,
            "updated": 0,
            "error_type": "circuit_open",
            "failure_categories": {"circuit_open": 1},
            "failure_details": [],
            "duration": 0.0,
        }

    def _record_circuit_breaker_result(self, form_name: str, result: dict[str, Any]) -> None:
        status = str(result.get("status", "")).lower()
        if status == SyncStatus.SUCCESS.value:
            self.circuit_breaker.record_success(form_name)
            return

        if status not in (SyncStatus.FAILED.value, SyncStatus.PARTIAL.value):
            return

        category = self._select_circuit_breaker_failure_category(result)
        if category:
            self.circuit_breaker.record_failure(form_name, category)

    def _select_circuit_breaker_failure_category(self, result: dict[str, Any]) -> str:
        failure_categories = result.get("failure_categories")
        if isinstance(failure_categories, dict) and failure_categories:
            valid_categories: list[tuple[str, int]] = []
            for category, count in failure_categories.items():
                try:
                    normalized_count = int(count or 0)
                except Exception:
                    normalized_count = 0
                valid_categories.append((str(category), normalized_count))

            positive_categories = [item for item in valid_categories if item[1] > 0]
            ranked_categories = positive_categories or valid_categories
            if ranked_categories:
                ranked_categories.sort(key=lambda item: item[1], reverse=True)
                return ranked_categories[0][0]

        return str(result.get("error_type", "")).strip()

    def _truncate_table_for_complete(self, table_name: str, manager: MySQLManager) -> bool:
        """Delegate pre-complete truncation to FormSyncRunner."""
        return self.form_sync_runner.truncate_table_for_complete(table_name, manager)

    def _get_account_balance_period_range(self) -> tuple[int, int, int, int]:
        """从配置中解析科目余额表起始期间，结束期间固定取当前时间的上月。"""
        query_config = config_manager.get_form_queries().get("科目余额表", {})
        model = query_config.get("Model", {}) if isinstance(query_config, dict) else {}
        now = datetime.now()

        def _parse_year(value, default):
            try:
                return int(str(value).strip())
            except Exception:
                return default

        def _parse_period(value, default):
            try:
                period = int(str(value).strip())
            except Exception:
                period = default
            return max(1, min(period, 12))

        start_year = _parse_year(model.get("FSTARTYEAR"), now.year)
        start_month = _parse_period(model.get("FSTARTPERIOD"), 1)

        # 结束期间按当前时间自动取上月，避免受配置中的静态 FENDYEAR/FENDPERIOD 限制。
        if now.month == 1:
            end_year = now.year - 1
            end_month = 12
        else:
            end_year = now.year
            end_month = now.month - 1

        if (end_year, end_month) < (start_year, start_month):
            raise ValueError(
                f"科目余额表配置的结束期间早于开始期间: {start_year}-{start_month:02d} -> {end_year}-{end_month:02d}"
            )

        return start_year, start_month, end_year, end_month

    def _sync_account_balance_form(self, form_name: str, sync_type: SyncType) -> dict[str, Any]:
        """使用专用按月同步器同步科目余额表。"""
        effective_sync_type = SyncType.COMPLETE
        if sync_type != SyncType.COMPLETE:
            logger.info(
                f"[{form_name}] 检测到特殊规则：强制将同步类型从 {sync_type.value} 转换为 complete (完全同步)"
            )

        start_time = datetime.now()
        table_name = self.table_mapping.get(form_name, "GL_RPT_AccountBalance")

        local_db = create_shared_db_manager(mysql_manager)

        try:
            start_year, start_month, end_year, end_month = self._get_account_balance_period_range()
            self._notify_progress(
                f"[{form_name}] 将按期间 {start_year}年{start_month:02d}月 - {end_year}年{end_month:02d}月 逐月同步",
                5,
            )

            result = account_balance_sync_manager.sync_by_month(
                start_year=start_year,
                start_month=start_month,
                end_year=end_year,
                end_month=end_month,
                truncate_before_sync=True,
                progress_callback=lambda msg, progress: self._notify_progress(f"[{form_name}] {msg}", progress),
                db_manager=local_db,
            )

            end_time = result.get("end_time") or datetime.now()
            status_value = str(result.get("status", SyncStatus.FAILED.value))
            message = str(result.get("message", "科目余额表同步结束"))
            total_records = int(result.get("total_records", 0) or 0)
            duration = float(result.get("duration", (end_time - start_time).total_seconds()) or 0.0)

            try:
                local_db.log_sync_operation(
                    effective_sync_type.value,
                    table_name,
                    "sync",
                    total_records,
                    status_value,
                    message,
                    start_time,
                    end_time,
                )
            except Exception:
                pass

            return {
                "status": status_value,
                "message": message,
                "record_count": total_records,
                "inserted": total_records,
                "updated": 0,
                "duration": duration,
                "success_periods": result.get("success_periods", []),
                "failed_periods": result.get("failed_periods", []),
            }
        except Exception as e:
            error_msg = f"同步失败 ({type(e).__name__}): {str(e)}"
            end_time = datetime.now()
            logger.error(f"[{form_name}] {error_msg}")
            self._notify_progress(f"[{form_name}] {error_msg}", 100)
            try:
                local_db.log_sync_operation(
                    effective_sync_type.value,
                    table_name,
                    "sync",
                    0,
                    SyncStatus.FAILED.value,
                    error_msg,
                    start_time,
                    end_time,
                    error_type=type(e).__name__,
                )
            except Exception:
                pass
            return {
                "status": SyncStatus.FAILED.value,
                "message": error_msg,
                "record_count": 0,
                "inserted": 0,
                "updated": 0,
                "error_type": type(e).__name__,
                "duration": (end_time - start_time).total_seconds(),
            }
        finally:
            try:
                local_db.disconnect()
            except Exception:
                pass

    def _build_filter_string(
        self, form_name: str, sync_type: SyncType, table_name: str, db_manager=None
    ) -> str | None:
        """Delegate filter construction to FilterBuilder."""
        return self.filter_builder.build_filter_string(
            form_name,
            sync_type,
            table_name,
            db_manager=db_manager,
        )

    def _query_kingdee_data(
        self,
        form_name: str,
        filter_string: str = None,
        page_callback=None,
        start_row: int = 0,
        sync_type: SyncType | None = None,
    ) -> list[dict] | None:
        """Delegate Kingdee querying to FormSyncRunner."""
        return self.form_sync_runner.query_kingdee_data(
            form_name,
            filter_string=filter_string,
            page_callback=page_callback,
            start_row=start_row,
            sync_type=sync_type,
        )

    def _insert_database_data(self, form_name: str, data: list[dict], db_manager=None) -> int:
        """Delegate database writes to FormSyncRunner."""
        return self.form_sync_runner.insert_database_data(form_name, data, db_manager=db_manager)

    def _check_connections(self) -> bool:
        """检查金蝶和数据库连接"""
        logger.info("开始同步前连接预检")
        # 检查金蝶连接
        if not kingdee_client.test_connection():
            logger.error("金蝶API连接失败")
            return False
        logger.info("金蝶会话预检通过")

        # 检查数据库连接
        if not mysql_manager.test_connection():
            logger.error("MySQL数据库连接失败")
            return False
        logger.info("数据库连接预检通过")

        return True

    def _create_sync_result(self, status: SyncStatus, message: str, start_time: datetime) -> dict[str, Any]:
        """创建同步结果"""
        end_time = datetime.now()
        return {
            "status": status.value,
            "message": message,
            "total_records": 0,
            "start_time": start_time,
            "end_time": end_time,
            "duration": (end_time - start_time).total_seconds(),
            "details": {},
        }

    def get_sync_history(self, limit: int = 50) -> list[dict]:
        """获取同步历史记录"""
        try:
            # 连接健壮性：确保有可用的连接与游标
            if not getattr(mysql_manager, "connection", None) or not getattr(mysql_manager, "cursor", None):
                if not mysql_manager.connect():
                    logger.error("数据库连接不可用，无法获取同步历史")
                    return []
            # 根据数据库类型构建合适的分页语句与占位符
            if getattr(mysql_manager, "db_type", "").lower() == "sqlserver":
                # SQL Server 使用 OFFSET/FETCH 进行分页；为避免占位符不兼容，直接嵌入整数
                safe_limit = int(limit) if isinstance(limit, int) else 50
                sql = f"""
                SELECT sync_type, table_name, operation, record_count, status, message,
                       start_time, end_time, duration_seconds
                FROM sync_logs
                ORDER BY start_time DESC
                OFFSET 0 ROWS FETCH NEXT {safe_limit} ROWS ONLY
                """
                mysql_manager.cursor.execute(sql)
            else:
                # MySQL 使用 LIMIT 参数占位符
                sql = """
                SELECT sync_type, table_name, operation, record_count, status, message,
                       start_time, end_time, duration_seconds
                FROM sync_logs 
                ORDER BY start_time DESC 
                LIMIT %s
                """
                mysql_manager.cursor.execute(sql, (limit,))

            rows = mysql_manager.cursor.fetchall()

            # 统一返回为字典列表，兼容不同驱动返回格式
            if not rows:
                return []
            if isinstance(rows[0], dict):
                return rows
            # 通过 cursor.description 获取列名，将元组转换为字典
            columns = [desc[0] for desc in getattr(mysql_manager.cursor, "description", [])]
            if not columns:
                return []
            result = []
            for row in rows:
                try:
                    result.append({columns[i]: row[i] for i in range(len(columns))})
                except Exception:
                    # 回退：若行不可索引或长度不匹配，跳过该行
                    continue
            return result
        except Exception as e:
            logger.error(f"获取同步历史失败: {str(e)}")
            return []

    def validate_data_integrity(self, form_names: list[str]) -> dict[str, Any]:
        """验证数据完整性（用于完全同步后的验证）"""
        results = {}

        for form_name in form_names:
            if form_name == "辅助资料" or form_name == "辅助资料明细":
                logger.info(f"跳过已废弃的表单: {form_name}")
                continue

            try:
                # 查询金蝶数据总数
                count_ref = [0]

                def _count_cb(page, count_ref=count_ref):
                    count_ref[0] += len(page)

                self._query_kingdee_data(form_name, page_callback=_count_cb)
                kingdee_count = count_ref[0]

                # 查询数据库数据总数
                table_name = self.table_mapping.get(form_name)
                if table_name:
                    mysql_manager.cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
                    db_result = mysql_manager.cursor.fetchone()
                    db_count = db_result["count"] if db_result else 0
                else:
                    db_count = 0

                results[form_name] = {
                    "kingdee_count": kingdee_count,
                    "database_count": db_count,
                    "match": kingdee_count == db_count,
                    "difference": abs(kingdee_count - db_count),
                }

            except Exception as e:
                logger.error(f"验证 {form_name} 数据完整性失败: {str(e)}")
                results[form_name] = {"error": str(e)}

        return results


# 全局数据同步管理器实例
sync_manager = DataSyncManager()
