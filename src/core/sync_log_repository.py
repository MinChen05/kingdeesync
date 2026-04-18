"""Repository for sync_logs write responsibilities."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.core.mysql_manager import MySQLManager


class SyncLogRepository:
    """Owns sync log persistence."""

    def __init__(self, manager: "MySQLManager", *, logger: logging.Logger | None = None) -> None:
        self.manager = manager
        self.logger = logger or logging.getLogger(__name__)

    def _ensure_connection(self) -> bool:
        if self.manager.connection and self.manager.cursor:
            return True

        self.logger.debug("数据库连接检查：连接丢失，尝试重新连接...")
        if self.manager.connect():
            return True

        self.logger.error("重新连接数据库失败，无法记录同步日志")
        return False

    def _probe_error_type_column(self) -> None:
        try:
            if self.manager.db_type == "sqlserver":
                self.manager.cursor.execute(
                    "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='sync_logs' AND COLUMN_NAME='error_type'"
                )
            else:
                self.manager.cursor.execute("SHOW COLUMNS FROM sync_logs LIKE 'error_type'")

            if self.manager.cursor.fetchone() is None:
                self.logger.debug("sync_logs.error_type 列不存在，跳过结构更新")
        except Exception as exc:
            self.logger.debug("检查 error_type 列存在性失败: %s", exc)

    def log_operation(
        self,
        sync_type: str,
        table_name: str,
        operation: str,
        record_count: int,
        status: str,
        message: str,
        start_time: datetime,
        end_time: datetime,
        error_type: str | None = None,
    ) -> bool:
        """Insert a sync_logs row using the current live schema."""
        try:
            if not self._ensure_connection():
                return False

            duration_seconds = (end_time - start_time).total_seconds()
            self._probe_error_type_column()
            params: tuple[Any, ...]

            if self.manager.db_type == "sqlserver":
                if error_type:
                    sql = (
                        "INSERT INTO sync_logs "
                        "(sync_type, table_name, operation, record_count, status, message, error_type, "
                        "start_time, end_time, duration_seconds) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                    )
                    params = (
                        sync_type,
                        table_name,
                        operation,
                        record_count,
                        status,
                        message,
                        error_type,
                        start_time,
                        end_time,
                        duration_seconds,
                    )
                else:
                    sql = (
                        "INSERT INTO sync_logs "
                        "(sync_type, table_name, operation, record_count, status, message, "
                        "start_time, end_time, duration_seconds) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
                    )
                    params = (
                        sync_type,
                        table_name,
                        operation,
                        record_count,
                        status,
                        message,
                        start_time,
                        end_time,
                        duration_seconds,
                    )
                self.manager.cursor.execute(sql, params)
            else:
                if error_type:
                    sql = """
                        INSERT INTO sync_logs
                        (sync_type, table_name, operation, record_count, status, message, error_type,
                         start_time, end_time, duration_seconds)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    params = (
                        sync_type,
                        table_name,
                        operation,
                        record_count,
                        status,
                        message,
                        error_type,
                        start_time,
                        end_time,
                        duration_seconds,
                    )
                else:
                    sql = """
                        INSERT INTO sync_logs
                        (sync_type, table_name, operation, record_count, status, message,
                         start_time, end_time, duration_seconds)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    params = (
                        sync_type,
                        table_name,
                        operation,
                        record_count,
                        status,
                        message,
                        start_time,
                        end_time,
                        duration_seconds,
                    )
                self.manager.cursor.execute(sql, params)

            self.logger.debug("已记录同步操作 %s %s %s", table_name, operation, status)
            return True
        except Exception as exc:
            self.logger.error("记录同步日志失败: %s", exc)
            return False
