"""Repository for sync_runs read/write responsibilities."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from src.core.mysql_manager import MySQLManager


class SyncRunRepository:
    """Owns task-level sync run persistence."""

    def __init__(self, manager: "MySQLManager", *, logger: logging.Logger | None = None) -> None:
        self.manager = manager
        self.logger = logger or logging.getLogger(__name__)
        self._table_ready = False

    def reset(self) -> None:
        self._table_ready = False

    @staticmethod
    def format_forms_summary(forms: Optional[List[str]]) -> str:
        """Format form names into a searchable, display-friendly summary."""
        if not forms:
            return "同步全部表单"
        normalized = [str(form).strip() for form in forms if str(form).strip()]
        return ", ".join(normalized) if normalized else "同步全部表单"

    def ensure_table(self) -> bool:
        """Ensure sync_runs exists before reading/writing run history."""
        if self._table_ready and self.manager.table_exists("sync_runs"):
            return True

        try:
            if not self.manager.connection or not self.manager.cursor:
                if not self.manager.connect():
                    return False

            if self.manager.table_exists("sync_runs"):
                self._table_ready = True
                return True

            if self.manager.db_type == "sqlserver":
                create_sql = """
                    CREATE TABLE sync_runs (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        run_id NVARCHAR(64) NOT NULL UNIQUE,
                        sync_type NVARCHAR(32) NULL,
                        forms_summary NVARCHAR(MAX) NULL,
                        form_count INT NOT NULL DEFAULT 0,
                        total_records INT NOT NULL DEFAULT 0,
                        success_count INT NOT NULL DEFAULT 0,
                        failure_count INT NOT NULL DEFAULT 0,
                        status NVARCHAR(32) NOT NULL,
                        message NVARCHAR(MAX) NULL,
                        failed_forms NVARCHAR(MAX) NULL,
                        details_json NVARCHAR(MAX) NULL,
                        start_time DATETIME2 NOT NULL,
                        end_time DATETIME2 NULL,
                        duration_seconds FLOAT NULL
                    )
                """
                self.manager.cursor.execute(create_sql)
                index_defs = [
                    ("IX_sync_runs_start_time", "CREATE INDEX IX_sync_runs_start_time ON sync_runs(start_time)"),
                    ("IX_sync_runs_status", "CREATE INDEX IX_sync_runs_status ON sync_runs(status)"),
                    ("IX_sync_runs_sync_type", "CREATE INDEX IX_sync_runs_sync_type ON sync_runs(sync_type)"),
                ]
                for index_name, index_sql in index_defs:
                    self.manager.cursor.execute(
                        "SELECT 1 FROM sys.indexes WHERE name = ? AND object_id = OBJECT_ID('sync_runs')",
                        (index_name,),
                    )
                    if self.manager.cursor.fetchone() is None:
                        self.manager.cursor.execute(index_sql)
            else:
                create_sql = """
                    CREATE TABLE IF NOT EXISTS sync_runs (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        run_id VARCHAR(64) NOT NULL UNIQUE,
                        sync_type VARCHAR(32) NULL,
                        forms_summary TEXT NULL,
                        form_count INT NOT NULL DEFAULT 0,
                        total_records INT NOT NULL DEFAULT 0,
                        success_count INT NOT NULL DEFAULT 0,
                        failure_count INT NOT NULL DEFAULT 0,
                        status VARCHAR(32) NOT NULL,
                        message TEXT NULL,
                        failed_forms TEXT NULL,
                        details_json LONGTEXT NULL,
                        start_time DATETIME NOT NULL,
                        end_time DATETIME NULL,
                        duration_seconds DOUBLE NULL,
                        KEY idx_sync_runs_start_time (start_time),
                        KEY idx_sync_runs_status (status),
                        KEY idx_sync_runs_sync_type (sync_type)
                    )
                """
                self.manager.cursor.execute(create_sql)

            self._table_ready = self.manager.table_exists("sync_runs")
            if self._table_ready:
                self.logger.info("任务级历史表 sync_runs 已就绪")
            return self._table_ready
        except Exception as exc:
            self.logger.warning("准备 sync_runs 表失败: %s", exc)
            return False

    def recover_running_runs(self, reason: str | None = None) -> int:
        """Mark leftover running runs as failed after abnormal exit or restart."""
        try:
            if not self.ensure_table():
                return 0

            if self.manager.db_type == "sqlserver":
                select_sql = """
                    SELECT run_id, start_time
                    FROM sync_runs
                    WHERE status = ? AND end_time IS NULL
                """
                select_params = ("running",)
            else:
                select_sql = """
                    SELECT run_id, start_time
                    FROM sync_runs
                    WHERE status = %s AND end_time IS NULL
                """
                select_params = ("running",)

            self.manager.cursor.execute(select_sql, select_params)
            rows = self.manager.cursor.fetchall() or []
            if not rows:
                return 0

            now = datetime.now()
            message_text = reason or "Recovered stale running task after previous abnormal exit"
            recovered = 0

            for row in rows:
                if isinstance(row, dict):
                    run_id = row.get("run_id")
                    start_time = row.get("start_time")
                else:
                    run_id = row[0] if len(row) > 0 else None
                    start_time = row[1] if len(row) > 1 else None

                if not run_id:
                    continue

                duration_seconds = 0.0
                if isinstance(start_time, datetime):
                    duration_seconds = max(0.0, (now - start_time).total_seconds())

                if self.manager.db_type == "sqlserver":
                    update_sql = """
                        UPDATE sync_runs
                        SET status = ?, message = ?, end_time = ?, duration_seconds = ?
                        WHERE run_id = ? AND status = ? AND end_time IS NULL
                    """
                    update_params = (
                        "failed",
                        message_text,
                        now,
                        duration_seconds,
                        run_id,
                        "running",
                    )
                else:
                    update_sql = """
                        UPDATE sync_runs
                        SET status = %s, message = %s, end_time = %s, duration_seconds = %s
                        WHERE run_id = %s AND status = %s AND end_time IS NULL
                    """
                    update_params = (
                        "failed",
                        message_text,
                        now,
                        duration_seconds,
                        run_id,
                        "running",
                    )

                self.manager.cursor.execute(update_sql, update_params)
                if getattr(self.manager.cursor, "rowcount", 0) > 0:
                    recovered += 1

            if recovered:
                self.logger.warning("Recovered %s stale running sync run(s)", recovered)
            return recovered
        except Exception as exc:
            self.logger.warning("Failed to recover stale running sync runs: %s", exc)
            return 0

    def start_run(
        self,
        run_id: str,
        sync_type: str,
        forms: Optional[List[str]],
        start_time: datetime,
    ) -> bool:
        """Insert the initial sync run record."""
        try:
            if not self.ensure_table():
                return False

            forms_summary = self.format_forms_summary(forms)
            form_count = len(forms or [])

            if self.manager.db_type == "sqlserver":
                sql = """
                    INSERT INTO sync_runs (
                        run_id, sync_type, forms_summary, form_count,
                        total_records, success_count, failure_count,
                        status, message, start_time
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                params = (
                    run_id,
                    sync_type,
                    forms_summary,
                    form_count,
                    0,
                    0,
                    0,
                    "running",
                    "任务开始",
                    start_time,
                )
            else:
                sql = """
                    INSERT INTO sync_runs (
                        run_id, sync_type, forms_summary, form_count,
                        total_records, success_count, failure_count,
                        status, message, start_time
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                params = (
                    run_id,
                    sync_type,
                    forms_summary,
                    form_count,
                    0,
                    0,
                    0,
                    "running",
                    "任务开始",
                    start_time,
                )

            self.manager.cursor.execute(sql, params)
            return True
        except Exception as exc:
            self.logger.warning("记录任务开始失败: %s", exc)
            return False

    def finish_run(
        self,
        run_id: str,
        sync_type: str,
        forms: Optional[List[str]],
        total_records: int,
        success_count: int,
        failure_count: int,
        status: str,
        message: str,
        start_time: datetime,
        end_time: datetime,
        failed_forms: Optional[List[str]] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update the sync run or insert the final snapshot when missing."""
        try:
            if not self.ensure_table():
                return False

            forms_summary = self.format_forms_summary(forms)
            form_count = len(forms or [])
            failed_forms_text = self.format_forms_summary(failed_forms) if failed_forms else None
            details_json = json.dumps(details or {}, ensure_ascii=False)
            duration_seconds = (end_time - start_time).total_seconds()

            if self.manager.db_type == "sqlserver":
                update_sql = """
                    UPDATE sync_runs
                    SET sync_type = ?, forms_summary = ?, form_count = ?, total_records = ?,
                        success_count = ?, failure_count = ?, status = ?, message = ?,
                        failed_forms = ?, details_json = ?, start_time = ?, end_time = ?, duration_seconds = ?
                    WHERE run_id = ?
                """
                update_params = (
                    sync_type,
                    forms_summary,
                    form_count,
                    total_records,
                    success_count,
                    failure_count,
                    status,
                    message,
                    failed_forms_text,
                    details_json,
                    start_time,
                    end_time,
                    duration_seconds,
                    run_id,
                )
                insert_sql = """
                    INSERT INTO sync_runs (
                        run_id, sync_type, forms_summary, form_count, total_records,
                        success_count, failure_count, status, message, failed_forms,
                        details_json, start_time, end_time, duration_seconds
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
            else:
                update_sql = """
                    UPDATE sync_runs
                    SET sync_type = %s, forms_summary = %s, form_count = %s, total_records = %s,
                        success_count = %s, failure_count = %s, status = %s, message = %s,
                        failed_forms = %s, details_json = %s, start_time = %s, end_time = %s, duration_seconds = %s
                    WHERE run_id = %s
                """
                update_params = (
                    sync_type,
                    forms_summary,
                    form_count,
                    total_records,
                    success_count,
                    failure_count,
                    status,
                    message,
                    failed_forms_text,
                    details_json,
                    start_time,
                    end_time,
                    duration_seconds,
                    run_id,
                )
                insert_sql = """
                    INSERT INTO sync_runs (
                        run_id, sync_type, forms_summary, form_count, total_records,
                        success_count, failure_count, status, message, failed_forms,
                        details_json, start_time, end_time, duration_seconds
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """

            self.manager.cursor.execute(update_sql, update_params)
            if getattr(self.manager.cursor, "rowcount", 0) == 0:
                insert_params = (
                    run_id,
                    sync_type,
                    forms_summary,
                    form_count,
                    total_records,
                    success_count,
                    failure_count,
                    status,
                    message,
                    failed_forms_text,
                    details_json,
                    start_time,
                    end_time,
                    duration_seconds,
                )
                self.manager.cursor.execute(insert_sql, insert_params)
            return True
        except Exception as exc:
            self.logger.warning("记录任务结束失败: %s", exc)
            return False
