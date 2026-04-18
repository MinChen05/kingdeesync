import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List

from src.core.mysql_manager import mysql_manager
from src.utils.logger import get_debug_log_path

logger = logging.getLogger(__name__)


def _log_debug(msg: str):
    try:
        debug_path = get_debug_log_path("debug_reporting.txt")
        with open(debug_path, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now()}] {msg}\\n")
    except Exception:
        pass


def _ensure_pool() -> bool:
    if getattr(mysql_manager, "pool", None):
        return True
    try:
        mysql_manager.connect()
    except Exception as e:
        _log_debug(f"_ensure_pool connect failed: {e}")
    return bool(getattr(mysql_manager, "pool", None))


def _safe_scalar(row: Any, index: int = 0, default: Any = 0) -> Any:
    if row is None:
        return default
    if isinstance(row, dict):
        values = list(row.values())
        if index < len(values):
            return values[index]
        return default
    try:
        return row[index]
    except Exception:
        return default


def _safe_close(cur, conn):
    try:
        if cur:
            cur.close()
    except Exception:
        pass
    try:
        if conn:
            conn.close()
    except Exception:
        pass


def get_dashboard_today_stats() -> Dict[str, Any]:
    """Get today's dashboard stats with yesterday comparison."""
    _log_debug("get_dashboard_today_stats start")
    if not _ensure_pool():
        return {
            "sync_count": 0,
            "sync_records": 0,
            "success_rate": 0.0,
            "yday_count": 0,
            "yday_records": 0,
            "yday_rate": 0.0,
        }

    is_sqlserver = getattr(mysql_manager, "db_type", "mysql") == "sqlserver"
    use_sync_runs = mysql_manager.table_exists("sync_runs")
    base_table = "sync_runs" if use_sync_runs else "sync_logs"
    count_field = "total_records" if use_sync_runs else "record_count"

    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    if is_sqlserver:
        clause_today = "CAST(start_time AS date) = CAST(? AS date)"
        clause_yday = "CAST(start_time AS date) = CAST(? AS date)"
        params_today = (today,)
        params_yday = (yesterday,)
    else:
        clause_today = "DATE(start_time) = %s"
        clause_yday = "DATE(start_time) = %s"
        params_today = (today,)
        params_yday = (yesterday,)

    conn = None
    cur = None
    try:
        conn = mysql_manager.pool.connection()
        cur = conn.cursor()

        sql_count = f"SELECT COUNT(*) FROM {base_table} WHERE {{clause}}"
        sql_sum = f"SELECT COALESCE(SUM({count_field}), 0) FROM {base_table} WHERE {{clause}}"
        sql_rate = (
            f"SELECT SUM(CASE WHEN status='success' THEN 1 ELSE 0 END), COUNT(*) "
            f"FROM {base_table} WHERE {{clause}}"
        )

        cur.execute(sql_count.format(clause=clause_today), params_today)
        sync_count = int(_safe_scalar(cur.fetchone(), 0, 0) or 0)

        cur.execute(sql_sum.format(clause=clause_today), params_today)
        sync_records = int(_safe_scalar(cur.fetchone(), 0, 0) or 0)

        cur.execute(sql_rate.format(clause=clause_today), params_today)
        row = cur.fetchone()
        succ_cnt = int(_safe_scalar(row, 0, 0) or 0)
        total_cnt = int(_safe_scalar(row, 1, 0) or 0)
        success_rate = round((succ_cnt / total_cnt) * 100, 1) if total_cnt > 0 else 0.0

        cur.execute(sql_count.format(clause=clause_yday), params_yday)
        yday_count = int(_safe_scalar(cur.fetchone(), 0, 0) or 0)

        cur.execute(sql_sum.format(clause=clause_yday), params_yday)
        yday_records = int(_safe_scalar(cur.fetchone(), 0, 0) or 0)

        cur.execute(sql_rate.format(clause=clause_yday), params_yday)
        yday_row = cur.fetchone()
        yday_succ = int(_safe_scalar(yday_row, 0, 0) or 0)
        yday_total = int(_safe_scalar(yday_row, 1, 0) or 0)
        yday_rate = round((yday_succ / yday_total) * 100, 1) if yday_total > 0 else 0.0

        return {
            "sync_count": sync_count,
            "sync_records": sync_records,
            "success_rate": success_rate,
            "yday_count": yday_count,
            "yday_records": yday_records,
            "yday_rate": yday_rate,
        }
    except Exception as e:
        _log_debug(f"get_dashboard_today_stats error: {e}")
        logger.error(f"Failed to load dashboard stats: {e}")
        return {
            "sync_count": 0,
            "sync_records": 0,
            "success_rate": 0.0,
            "yday_count": 0,
            "yday_records": 0,
            "yday_rate": 0.0,
        }
    finally:
        _safe_close(cur, conn)


def get_trend_days(days: int = 7) -> List[Dict[str, Any]]:
    """Get trend data in the last N days."""
    days = max(int(days or 0), 1)
    if not _ensure_pool():
        return []

    is_sqlserver = getattr(mysql_manager, "db_type", "mysql") == "sqlserver"
    use_sync_runs = mysql_manager.table_exists("sync_runs")
    base_table = "sync_runs" if use_sync_runs else "sync_logs"
    count_field = "total_records" if use_sync_runs else "record_count"

    start_date = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d") + " 00:00:00"

    if is_sqlserver:
        sql = (
            "SELECT CONVERT(date, start_time) AS day, "
            f"COUNT(*) AS cnt, COALESCE(SUM({count_field}),0) AS vol, "
            "SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS succ, COUNT(*) AS total "
            f"FROM {base_table} "
            "WHERE start_time >= ? "
            "GROUP BY CONVERT(date, start_time) ORDER BY day"
        )
        params = (start_date,)
    else:
        sql = (
            "SELECT DATE(start_time) AS day, "
            f"COUNT(*) AS cnt, COALESCE(SUM({count_field}),0) AS vol, "
            "SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS succ, COUNT(*) AS total "
            f"FROM {base_table} "
            "WHERE start_time >= %s "
            "GROUP BY DATE(start_time) ORDER BY day"
        )
        params = (start_date,)

    conn = None
    cur = None
    try:
        conn = mysql_manager.pool.connection()
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall() or []

        day_map: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            if isinstance(row, dict):
                day = row.get("day")
                cnt = row.get("cnt")
                vol = row.get("vol")
                succ = row.get("succ")
                total = row.get("total")
            else:
                day, cnt, vol, succ, total = row
            day_key = str(day).split(" ")[0]
            total_val = float(total or 0)
            rate = round((float(succ or 0) / total_val) * 100, 1) if total_val > 0 else 0.0
            day_map[day_key] = {
                "day": day_key,
                "count": int(cnt or 0),
                "volume": int(vol or 0),
                "rate": rate,
            }

        result: List[Dict[str, Any]] = []
        start_dt = (datetime.now() - timedelta(days=days - 1)).date()
        for offset in range(days):
            cur_day = (start_dt + timedelta(days=offset)).isoformat()
            result.append(day_map.get(cur_day, {"day": cur_day, "count": 0, "volume": 0, "rate": 0.0}))
        return result
    except Exception as e:
        logger.error(f"Failed to load trend data ({days}d): {e}")
        return []
    finally:
        _safe_close(cur, conn)


def get_trend_7d() -> List[Dict[str, Any]]:
    """Backward-compatible API for 7-day trend."""
    return get_trend_days(7)


def get_top_forms_days(limit: int = 5, days: int = 7) -> List[Dict[str, Any]]:
    """Get top forms in the last N days."""
    limit = max(int(limit or 0), 1)
    days = max(int(days or 0), 1)
    if not _ensure_pool():
        return []
    if not mysql_manager.table_exists("sync_logs"):
        return []

    is_sqlserver = getattr(mysql_manager, "db_type", "mysql") == "sqlserver"
    start_date = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d") + " 00:00:00"

    conn = None
    cur = None
    try:
        conn = mysql_manager.pool.connection()
        cur = conn.cursor()

        if is_sqlserver:
            sql = (
                "SELECT table_name, COUNT(*) AS cnt, "
                "SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS succ, "
                "COUNT(*) AS total "
                "FROM sync_logs "
                "WHERE start_time >= ? "
                "GROUP BY table_name ORDER BY cnt DESC "
                "OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY"
            )
            cur.execute(sql, (start_date, limit))
        else:
            sql = (
                "SELECT table_name, COUNT(*) AS cnt, "
                "SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS succ, "
                "COUNT(*) AS total "
                "FROM sync_logs "
                "WHERE start_time >= %s "
                "GROUP BY table_name ORDER BY cnt DESC LIMIT %s"
            )
            cur.execute(sql, (start_date, limit))

        rows = cur.fetchall() or []
        result: List[Dict[str, Any]] = []
        for row in rows:
            if isinstance(row, dict):
                name = row.get("table_name")
                cnt = row.get("cnt")
                succ = row.get("succ")
                total = row.get("total")
            else:
                name, cnt, succ, total = row
            total_val = float(total or 0)
            rate = round((float(succ or 0) / total_val) * 100, 1) if total_val > 0 else 0.0
            result.append({
                "name": str(name),
                "count": int(cnt or 0),
                "rate": rate,
            })
        return result
    except Exception as e:
        logger.error(f"Failed to load top forms ({days}d): {e}")
        return []
    finally:
        _safe_close(cur, conn)


def get_top_forms_7d(limit: int = 5) -> List[Dict[str, Any]]:
    """Backward-compatible API for 7-day top forms."""
    return get_top_forms_days(limit=limit, days=7)


def ensure_sync_logs_indexes() -> bool:
    """Ensure common indexes on sync_logs for dashboard/history queries."""
    try:
        if not getattr(mysql_manager, "cursor", None):
            mysql_manager.connect()
        if not getattr(mysql_manager, "cursor", None):
            return False

        is_sqlserver = getattr(mysql_manager, "db_type", "mysql") == "sqlserver"
        if is_sqlserver:
            stmts = [
                ("IX_sync_logs_log_time", "CREATE INDEX IX_sync_logs_log_time ON sync_logs(start_time)"),
                ("IX_sync_logs_table_name", "CREATE INDEX IX_sync_logs_table_name ON sync_logs(table_name)"),
                ("IX_sync_logs_status", "CREATE INDEX IX_sync_logs_status ON sync_logs(status)"),
            ]
            for idx_name, create_sql in stmts:
                check_sql = "SELECT name FROM sys.indexes WHERE name = ? AND object_id = OBJECT_ID('sync_logs')"
                mysql_manager.cursor.execute(check_sql, (idx_name,))
                exists = mysql_manager.cursor.fetchone() is not None
                if not exists:
                    mysql_manager.cursor.execute(create_sql)
        else:
            checks = [
                ("idx_sync_logs_log_time", "CREATE INDEX idx_sync_logs_log_time ON sync_logs(start_time)"),
                ("idx_sync_logs_table_name", "CREATE INDEX idx_sync_logs_table_name ON sync_logs(table_name)"),
                ("idx_sync_logs_status", "CREATE INDEX idx_sync_logs_status ON sync_logs(status)"),
            ]
            for idx_name, create_sql in checks:
                mysql_manager.cursor.execute(
                    "SELECT COUNT(1) FROM information_schema.statistics "
                    "WHERE table_schema = DATABASE() AND table_name = 'sync_logs' AND index_name = %s",
                    (idx_name,),
                )
                row = mysql_manager.cursor.fetchone()
                exists = bool(_safe_scalar(row, 0, 0))
                if not exists:
                    mysql_manager.cursor.execute(create_sql)
        return True
    except Exception as e:
        logger.warning(f"Failed to ensure sync_logs indexes: {e}")
        return False


def archive_sync_logs(days_to_keep: int = 180) -> bool:
    """Archive old rows from sync_logs to sync_logs_archive."""
    days_to_keep = max(int(days_to_keep or 0), 1)
    try:
        if not getattr(mysql_manager, "cursor", None):
            mysql_manager.connect()
        if not getattr(mysql_manager, "cursor", None):
            return False

        is_sqlserver = getattr(mysql_manager, "db_type", "mysql") == "sqlserver"
        if is_sqlserver:
            try:
                mysql_manager.cursor.execute(
                    "IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'sync_logs_archive') "
                    "AND type in (N'U')) BEGIN SELECT TOP 0 * INTO sync_logs_archive FROM sync_logs END"
                )
            except Exception:
                pass
            mysql_manager.cursor.execute(
                "INSERT INTO sync_logs_archive SELECT * FROM sync_logs "
                "WHERE start_time < DATEADD(day, -?, GETDATE())",
                (days_to_keep,),
            )
            mysql_manager.cursor.execute(
                "DELETE FROM sync_logs WHERE start_time < DATEADD(day, -?, GETDATE())",
                (days_to_keep,),
            )
        else:
            mysql_manager.cursor.execute("CREATE TABLE IF NOT EXISTS sync_logs_archive LIKE sync_logs")
            mysql_manager.cursor.execute(
                "INSERT INTO sync_logs_archive SELECT * FROM sync_logs "
                "WHERE start_time < DATE_SUB(CURDATE(), INTERVAL %s DAY)",
                (days_to_keep,),
            )
            mysql_manager.cursor.execute(
                "DELETE FROM sync_logs WHERE start_time < DATE_SUB(CURDATE(), INTERVAL %s DAY)",
                (days_to_keep,),
            )

        try:
            if getattr(mysql_manager, "connection", None):
                mysql_manager.connection.commit()
        except Exception:
            pass
        return True
    except Exception as e:
        logger.warning(f"Failed to archive sync_logs: {e}")
        return False
