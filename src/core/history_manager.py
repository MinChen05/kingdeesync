import logging
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.core.data_sync import sync_manager
from src.core.mysql_manager import mysql_manager

logger = logging.getLogger(__name__)


class HistoryManager:
    """同步历史记录管理器。"""

    def __init__(self):
        self.table_to_form = {v: k for k, v in sync_manager.table_mapping.items()}

    def _ensure_connection(self) -> bool:
        if getattr(mysql_manager, "connection", None) and getattr(mysql_manager, "cursor", None):
            return True
        return mysql_manager.connect()

    @staticmethod
    def _row_to_dict(row: Any, columns: Sequence[str]) -> Dict[str, Any]:
        if isinstance(row, dict):
            return dict(row)
        return {columns[idx]: row[idx] for idx in range(len(columns))}

    @staticmethod
    def _scalar_value(row: Any, default: int = 0) -> Any:
        if row is None:
            return default
        if isinstance(row, dict):
            values = list(row.values())
            return values[0] if values else default
        try:
            return row[0]
        except Exception:
            return default

    @staticmethod
    def _build_equal_condition(
        conditions: List[str],
        params: List[Any],
        field_name: str,
        value: Any,
    ):
        if value in (None, "", "全部"):
            return
        if isinstance(value, (list, tuple, set)):
            normalized = [item for item in value if item not in (None, "", "全部")]
            if not normalized:
                return
            placeholders = ", ".join(["%s"] * len(normalized))
            conditions.append(f"{field_name} IN ({placeholders})")
            params.extend(normalized)
            return
        conditions.append(f"{field_name} = %s")
        params.append(value)

    def _replace_placeholders(self, sql: str) -> str:
        if getattr(mysql_manager, "db_type", "mysql") == "sqlserver":
            return sql.replace("%s", "?")
        return sql

    def _query_sync_runs(
        self,
        page: int,
        page_size: int,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        status: Optional[str],
        sync_type: Optional[str],
        form_name: Optional[str],
    ) -> Tuple[List[Dict], int]:
        conditions: List[str] = []
        params: List[Any] = []

        if start_date:
            conditions.append("start_time >= %s")
            params.append(start_date)
        if end_date:
            conditions.append("start_time <= %s")
            params.append(end_date)
        self._build_equal_condition(conditions, params, "status", status)
        self._build_equal_condition(conditions, params, "sync_type", sync_type)
        if form_name:
            conditions.append("(forms_summary LIKE %s OR failed_forms LIKE %s OR message LIKE %s)")
            params.extend([f"%{form_name}%"] * 3)

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        count_sql = self._replace_placeholders(f"SELECT COUNT(*) FROM sync_runs {where_clause}")
        mysql_manager.cursor.execute(count_sql, tuple(params))
        total_count = int(self._scalar_value(mysql_manager.cursor.fetchone(), 0) or 0)
        if total_count == 0:
            return [], 0

        offset = (page - 1) * page_size
        if getattr(mysql_manager, "db_type", "mysql") == "sqlserver":
            select_sql = self._replace_placeholders(
                f"""
                    SELECT id, run_id, sync_type, forms_summary, form_count, total_records,
                           success_count, failure_count, status, message, failed_forms,
                           start_time, end_time, duration_seconds
                    FROM sync_runs
                    {where_clause}
                    ORDER BY start_time DESC
                    OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY
                """
            )
        else:
            select_sql = self._replace_placeholders(
                f"""
                    SELECT id, run_id, sync_type, forms_summary, form_count, total_records,
                           success_count, failure_count, status, message, failed_forms,
                           start_time, end_time, duration_seconds
                    FROM sync_runs
                    {where_clause}
                    ORDER BY start_time DESC
                    LIMIT {page_size} OFFSET {offset}
                """
            )

        mysql_manager.cursor.execute(select_sql, tuple(params))
        columns = [col[0] for col in mysql_manager.cursor.description]
        rows = mysql_manager.cursor.fetchall() or []

        result: List[Dict[str, Any]] = []
        for row in rows:
            record = self._row_to_dict(row, columns)
            record["form_name"] = record.get("forms_summary") or "同步全部表单"
            record["table_name"] = record["form_name"]
            record["record_count"] = int(record.get("total_records", 0) or 0)
            record["operation"] = "sync_run"
            if record.get("start_time"):
                record["start_time_str"] = str(record["start_time"]).split(".")[0]
            result.append(record)
        return result, total_count

    def _query_sync_logs(
        self,
        page: int,
        page_size: int,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        status: Optional[str],
        sync_type: Optional[str],
        form_name: Optional[str],
    ) -> Tuple[List[Dict], int]:
        conditions: List[str] = []
        params: List[Any] = []

        if start_date:
            conditions.append("start_time >= %s")
            params.append(start_date)
        if end_date:
            conditions.append("start_time <= %s")
            params.append(end_date)
        self._build_equal_condition(conditions, params, "status", status)
        self._build_equal_condition(conditions, params, "sync_type", sync_type)
        if form_name:
            conditions.append("(table_name LIKE %s OR message LIKE %s)")
            params.extend([f"%{form_name}%", f"%{form_name}%"])

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        count_sql = self._replace_placeholders(f"SELECT COUNT(*) FROM sync_logs {where_clause}")
        mysql_manager.cursor.execute(count_sql, tuple(params))
        total_count = int(self._scalar_value(mysql_manager.cursor.fetchone(), 0) or 0)
        if total_count == 0:
            return [], 0

        offset = (page - 1) * page_size
        if getattr(mysql_manager, "db_type", "mysql") == "sqlserver":
            select_sql = self._replace_placeholders(
                f"""
                    SELECT id, sync_type, table_name, operation, record_count, status, message,
                           error_type, start_time, end_time, duration_seconds
                    FROM sync_logs
                    {where_clause}
                    ORDER BY start_time DESC
                    OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY
                """
            )
        else:
            select_sql = self._replace_placeholders(
                f"""
                    SELECT id, sync_type, table_name, operation, record_count, status, message,
                           error_type, start_time, end_time, duration_seconds
                    FROM sync_logs
                    {where_clause}
                    ORDER BY start_time DESC
                    LIMIT {page_size} OFFSET {offset}
                """
            )

        mysql_manager.cursor.execute(select_sql, tuple(params))
        columns = [col[0] for col in mysql_manager.cursor.description]
        rows = mysql_manager.cursor.fetchall() or []

        result: List[Dict[str, Any]] = []
        for row in rows:
            record = self._row_to_dict(row, columns)
            table_name = record.get("table_name")
            record["form_name"] = self.table_to_form.get(table_name, table_name)
            if record.get("start_time"):
                record["start_time_str"] = str(record["start_time"]).split(".")[0]
            result.append(record)
        return result, total_count

    def get_history(
        self,
        page: int = 1,
        page_size: int = 20,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        status: Optional[str] = None,
        sync_type: Optional[str] = None,
        form_name: Optional[str] = None,
    ) -> Tuple[List[Dict], int]:
        """获取同步历史记录。"""
        try:
            if not self._ensure_connection():
                logger.error("数据库连接不可用")
                return [], 0

            if mysql_manager.table_exists("sync_runs"):
                run_records, run_total = self._query_sync_runs(
                    page=page,
                    page_size=page_size,
                    start_date=start_date,
                    end_date=end_date,
                    status=status,
                    sync_type=sync_type,
                    form_name=form_name,
                )
                if run_total > 0:
                    return run_records, run_total

            return self._query_sync_logs(
                page=page,
                page_size=page_size,
                start_date=start_date,
                end_date=end_date,
                status=status,
                sync_type=sync_type,
                form_name=form_name,
            )
        except Exception as e:
            logger.error(f"查询历史记录失败: {e}")
            return [], 0

    def get_stats(self) -> Dict[str, Any]:
        """获取历史页统计数据。"""
        stats = {
            "today_success_rate": "0%",
            "avg_duration": "0s",
            "top_failures": [],
        }

        try:
            if not self._ensure_connection():
                return stats

            is_sqlserver = getattr(mysql_manager, "db_type", "mysql") == "sqlserver"
            today_start = datetime.now().strftime("%Y-%m-%d") + " 00:00:00"
            use_sync_runs = mysql_manager.table_exists("sync_runs")
            base_table = "sync_runs" if use_sync_runs else "sync_logs"

            sql_rate = self._replace_placeholders(
                f"SELECT status, COUNT(*) FROM {base_table} WHERE start_time >= %s GROUP BY status"
            )
            mysql_manager.cursor.execute(sql_rate, (today_start,))
            rows = mysql_manager.cursor.fetchall() or []

            total = 0
            success = 0
            for row in rows:
                if isinstance(row, dict):
                    row_status = row.get("status")
                    row_count = int(row.get("COUNT(*)", row.get("count", 0)) or 0)
                else:
                    row_status, row_count = row[0], row[1]
                total += row_count
                if row_status == "success":
                    success += row_count

            if total > 0:
                stats["today_success_rate"] = f"{int(success / total * 100)}%"

            sql_dur = self._replace_placeholders(
                f"SELECT AVG(duration_seconds) FROM {base_table} WHERE start_time >= %s AND status='success'"
            )
            mysql_manager.cursor.execute(sql_dur, (today_start,))
            avg_dur = self._scalar_value(mysql_manager.cursor.fetchone(), 0)
            if avg_dur:
                stats["avg_duration"] = f"{int(float(avg_dur))}s"

            if use_sync_runs:
                if is_sqlserver:
                    sql_top = """
                        SELECT failed_forms
                        FROM sync_runs
                        WHERE status IN (?, ?, ?)
                          AND start_time >= DATEADD(day, -30, GETDATE())
                    """
                    mysql_manager.cursor.execute(sql_top, ("failed", "partial", "failed_abnormal_exit"))
                else:
                    sql_top = """
                        SELECT failed_forms
                        FROM sync_runs
                        WHERE status IN (%s, %s, %s)
                          AND start_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                    """
                    mysql_manager.cursor.execute(sql_top, ("failed", "partial", "failed_abnormal_exit"))

                counter: Counter[str] = Counter()
                for row in mysql_manager.cursor.fetchall() or []:
                    failed_forms = row.get("failed_forms") if isinstance(row, dict) else row[0]
                    if not failed_forms:
                        continue
                    for name in str(failed_forms).split(","):
                        normalized = name.strip()
                        if normalized:
                            counter[normalized] += 1
                stats["top_failures"] = [name for name, _ in counter.most_common(3)]
            else:
                sql_top = """
                    SELECT table_name, COUNT(*) as fail_cnt
                    FROM sync_logs
                    WHERE status='failed'
                    GROUP BY table_name
                    ORDER BY fail_cnt DESC
                """
                if not is_sqlserver:
                    sql_top += " LIMIT 3"
                else:
                    sql_top = sql_top.replace("SELECT", "SELECT TOP 3", 1)
                mysql_manager.cursor.execute(sql_top)
                fail_rows = mysql_manager.cursor.fetchall() or []
                top_fails = []
                for row in fail_rows:
                    table_name = row.get("table_name") if isinstance(row, dict) else row[0]
                    top_fails.append(self.table_to_form.get(table_name, table_name))
                stats["top_failures"] = top_fails

        except Exception as e:
            logger.error(f"获取统计数据失败: {e}")

        return stats


history_manager = HistoryManager()
