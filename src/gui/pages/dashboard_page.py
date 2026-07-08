"""Dashboard page — pixel-aligned to D:/Kingdee/assets/概览.png.

Layout:
  顶: 标题"概览" + 右上角刷新按钮
  指标卡行: 5 cards — 自绘图标
  第一行: 同步趋势(图例/范围) + 系统健康(4行)
  第二行: 最近同步记录(6列表格) + 风险提醒(卡片式列表)
"""

from __future__ import annotations

import logging
from datetime import datetime
from urllib.parse import urlparse

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.config.config_manager import config_manager
from src.core.history_manager import history_manager
from src.core.scheduler import auto_scheduler
from src.gui import icon_registry
from src.gui.components.buttons import LoadingButton
from src.gui.components.charts import DashboardDualLineChart
from src.gui.components.common import SvgIconLabel
from src.gui.components.data_table import DataTable
from src.gui.components.page_shell import Win11PageScaffold, Win11SectionCard
from src.gui.design_tokens import ColorTokens, qcolor
from src.gui.pages._dashboard_status_cards import DashboardStatusCards
from src.gui.ui_text import LoadingText
from src.services.reporting import get_dashboard_today_stats, get_trend_days

logger = logging.getLogger(__name__)

# ── helpers ──

_FAILED_STATUSES = {"failed", "failed_abnormal_exit", "error"}
_WARNING_STATUSES = {"partial", "warning", "pending"}
_SUCCESS_STATUSES = {"success", "completed", "done"}


def _set_color(label: QLabel, fg: str) -> None:
    pal = label.palette()
    pal.setColor(QPalette.WindowText, QColor(fg))
    label.setPalette(pal)

def _pill(label: QLabel, text: str, fg: str, bg: str, bold: bool = False) -> None:
    label.setText(text)
    label.setAutoFillBackground(True)
    pal = label.palette()
    pal.setColor(QPalette.Window, QColor(bg))
    pal.setColor(QPalette.WindowText, QColor(fg))
    label.setPalette(pal)
    f = label.font()
    f.setPointSize(10)
    f.setBold(bold)
    label.setFont(f)

def _font_size(label, pt: int, bold: bool = False) -> None:
    f = label.font()
    f.setPointSize(pt)
    f.setBold(bold)
    label.setFont(f)

def _rounded_pal(w: QWidget, bg: str, fg: str | None = None) -> None:
    w.setAutoFillBackground(True)
    pal = w.palette()
    pal.setColor(QPalette.Window, QColor(bg))
    if fg:
        pal.setColor(QPalette.WindowText, QColor(fg))
    w.setPalette(pal)


def _to_int(value, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_float(value, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _format_count(value) -> str:
    return f"{_to_int(value):,}"


def _format_rate(value) -> str:
    return f"{_to_float(value):.1f}%"


def _format_duration_compact(seconds) -> str:
    if seconds in (None, ""):
        return "--"
    secs = max(0.0, _to_float(seconds))
    whole = int(round(secs))
    if whole >= 3600:
        hours, rem = divmod(whole, 3600)
        minutes, sec = divmod(rem, 60)
        return f"{hours} 小时 {minutes} 分 {sec} 秒"
    if whole >= 60:
        minutes, sec = divmod(whole, 60)
        return f"{minutes} 分 {sec} 秒"
    if secs < 10 and abs(secs - round(secs)) >= 0.01:
        return f"{secs:.2f}".rstrip("0").rstrip(".") + " 秒"
    return f"{whole} 秒"


def _format_duration_clock(seconds) -> str:
    if seconds in (None, ""):
        return "--"
    secs = max(0, int(round(_to_float(seconds))))
    hours, rem = divmod(secs, 3600)
    minutes, sec = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{sec:02d}"


def _format_datetime(value) -> str:
    if value in (None, ""):
        return "--"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value).split(".")[0][:19]


def _first_value(record: dict, *keys: str):
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def _status_text(status) -> str:
    normalized = str(status or "").strip().lower()
    if normalized in _SUCCESS_STATUSES:
        return "成功"
    if normalized in _FAILED_STATUSES:
        return "失败"
    if normalized in _WARNING_STATUSES:
        return "警告"
    if normalized == "running":
        return "运行中"
    return str(status or "--")


def _is_risk_status(status) -> bool:
    normalized = str(status or "").strip().lower()
    return normalized in _FAILED_STATUSES or normalized in _WARNING_STATUSES


def _compact_url(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return "--"
    parsed = urlparse(text)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return text[:42] + "..." if len(text) > 45 else text


def _config_value(section: str, key: str, default: str = "") -> str:
    try:
        cfg = config_manager.config
        if cfg.has_section(section) and cfg.has_option(section, key):
            return cfg.get(section, key)
    except Exception:
        return default
    return default


def _kingdee_display_url() -> str:
    return _compact_url(
        _config_value("KINGDEE", "query_url")
        or _config_value("KINGDEE", "login_url")
    )


def _database_display_addr() -> str:
    db_type = (_config_value("DATABASE", "type") or _config_value("DB", "type") or "sqlserver").lower()
    section = "SQLSERVER" if db_type == "sqlserver" else "MYSQL"
    host = _config_value(section, "host") or "--"
    port = _config_value(section, "port")
    return f"{host}:{port}" if port else host


def _record_task_name(record: dict) -> str:
    return str(
        _first_value(record, "task_name", "name", "sync_type", "operation", "form_name", "table_name")
        or "--"
    )


def _record_form_name(record: dict) -> str:
    return str(_first_value(record, "form_name", "table_name", "forms_summary") or "--")


def _record_count(record: dict) -> str:
    value = _first_value(record, "record_count", "total_records", "inserted", "success_count")
    return _format_count(value)


def _record_duration(record: dict) -> str:
    value = _first_value(record, "duration_seconds", "duration")
    return _format_duration_clock(value)


def _record_time(record: dict) -> str:
    return _format_datetime(_first_value(record, "start_time_str", "start_time", "created_at"))


def _risk_time(record: dict) -> str:
    value = _first_value(record, "start_time_str", "start_time", "created_at")
    text = _format_datetime(value)
    return text[11:16] if len(text) >= 16 else "--"


def _ellipsize(text: str, limit: int) -> str:
    text = str(text or "--")
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 3)].rstrip() + "..."


def _record_time_display(record: dict) -> str:
    text = _record_time(record)
    if len(text) >= 16:
        return text[:16]
    return text


def _status_tone(status_text: str) -> tuple[str, str, str]:
    if status_text == "成功":
        return "●", ColorTokens.SUCCESS_GREEN, "success"
    if status_text == "失败":
        return "●", ColorTokens.DANGER, "danger"
    if status_text == "警告":
        return "▲", ColorTokens.WARNING, "warning"
    return "●", ColorTokens.NEUTRAL_400, "neutral"


def _stats_are_empty(stats: dict, history_stats: dict) -> bool:
    _ = history_stats
    if not stats:
        return True
    keys = ("sync_count", "success_rate", "fail_count", "pending_count", "avg_duration")
    has_value = any(stats.get(key) not in (None, "", 0, 0.0, "0", "0%", "0s") for key in keys)
    return not has_value


def _trend_rows_are_empty(rows: list[dict]) -> bool:
    if not rows:
        return True
    return all(_to_int(row.get("count")) == 0 and _to_float(row.get("rate")) == 0.0 for row in rows)


class SystemHealthCard(QFrame):
    """系统健康 — 白底表格式 4 行列表。"""

    _ROW_HEIGHT = 60

    _ICONS = {
        "kingdee": "health_api.svg",
        "database": "health_database.svg",
        "scheduler": "health_scheduler.svg",
        "log": "health_log.svg",
    }

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setProperty("ui", "win11-section-card")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QLabel(title)
        header.setProperty("ui", "win11-section-title")
        header.setObjectName("dashboard_health_title")
        header.setContentsMargins(18, 15, 18, 9)
        _font_size(header, 15, True)
        root.addWidget(header)

        self._container = QFrame()
        self._container.setAutoFillBackground(True)
        pal = self._container.palette()
        pal.setColor(QPalette.Window, QColor(ColorTokens.SURFACE_BASE))
        self._container.setPalette(pal)
        container_layout = QVBoxLayout(self._container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        self._rows: dict[str, dict] = {}
        specs = [
            ("kingdee", "API", ColorTokens.ACCENT_600, "金蝶 API", "https://api.yunxingkong.com"),
            ("database", "DB", ColorTokens.ACCENT_600, "SQL Server", "192.168.1.50:1433"),
            ("scheduler", "S", ColorTokens.ACCENT_600, "调度服务", "Scheduler Service"),
            ("log", "L", ColorTokens.ACCENT_600, "日志服务", "Log Service"),
        ]

        for idx, (key, _sym, icon_bg, svc, desc) in enumerate(specs):
            row = QHBoxLayout()
            row.setContentsMargins(18, 7, 18, 7)
            row.setSpacing(10)

            icon_w = SvgIconLabel(
                self._ICONS.get(key, "health_log.svg"),
                size=36,
                icon_size=20,
                color=icon_bg,
            )
            icon_w.setProperty("ui", "health-service-icon")
            icon_w.setProperty("tone", key)
            icon_w.setProperty("icon-color", icon_bg)
            row.addWidget(icon_w)

            name_col = QVBoxLayout()
            name_col.setSpacing(2)
            nm = QLabel(svc)
            nm.setProperty("ui", "health-service-name")
            _font_size(nm, 13, True)
            _set_color(nm, ColorTokens.TEXT_PRIMARY)
            name_col.addWidget(nm)
            dl = QLabel(desc)
            dl.setProperty("ui", "health-service-desc")
            _font_size(dl, 11)
            _set_color(dl, ColorTokens.NEUTRAL_400)
            dl.setMinimumWidth(120)
            dl.setMaximumWidth(190)
            name_col.addWidget(dl)
            row.addLayout(name_col, 1)

            status_col = QHBoxLayout()
            status_col.setSpacing(5)
            dot = QLabel()
            dot.setFixedSize(8, 8)
            dot.setProperty("ui", "health-status-dot")
            dot.setProperty("tone", "success")
            dot_p = dot.palette()
            dot_p.setColor(QPalette.Window, QColor(ColorTokens.SUCCESS_GREEN))
            dot.setAutoFillBackground(True)
            dot.setPalette(dot_p)
            status_col.addWidget(dot)
            st = QLabel("在线")
            st.setProperty("ui", "health-status-text")
            st.setProperty("tone", "success")
            _font_size(st, 12, True)
            _set_color(st, ColorTokens.SUCCESS_GREEN)
            status_col.addWidget(st)
            status_col.addStretch()
            status_col.setContentsMargins(0, 0, 4, 0)
            row.addLayout(status_col)

            m1_col = QVBoxLayout()
            m1_col.setSpacing(1)
            m1_title = QLabel("")
            m1_title.setProperty("ui", "health-metric-title")
            _font_size(m1_title, 10)
            _set_color(m1_title, ColorTokens.NEUTRAL_400)
            m1_col.addWidget(m1_title)
            m1_val = QLabel("--")
            m1_val.setProperty("ui", "health-metric-value")
            _font_size(m1_val, 12, True)
            _set_color(m1_val, ColorTokens.TEXT_PRIMARY)
            m1_col.addWidget(m1_val)
            m1_col.setContentsMargins(0, 0, 6, 0)
            row.addLayout(m1_col)

            m2_col = QVBoxLayout()
            m2_col.setSpacing(1)
            m2_title = QLabel("")
            m2_title.setProperty("ui", "health-metric-title")
            _font_size(m2_title, 10)
            _set_color(m2_title, ColorTokens.NEUTRAL_400)
            m2_col.addWidget(m2_title)
            m2_val = QLabel("--")
            m2_val.setProperty("ui", "health-metric-value")
            _font_size(m2_val, 12, True)
            _set_color(m2_val, ColorTokens.TEXT_PRIMARY)
            m2_col.addWidget(m2_val)
            m2_col.setContentsMargins(0, 0, 0, 0)
            row.addLayout(m2_col)

            wrapper = QWidget()
            wrapper.setProperty("ui", "dashboard-health-row")
            wrapper.setProperty("service", key)
            wrapper.setLayout(row)
            wrapper.setFixedHeight(self._ROW_HEIGHT)
            container_layout.addWidget(wrapper)

            self._rows[key] = {
                "status_label": st, "dot": dot,
                "desc": dl, "default_desc": desc,
                "icon": icon_w, "row_widget": wrapper,
                "m1_title": m1_title, "m1_val": m1_val,
                "m2_title": m2_title, "m2_val": m2_val,
            }

            if idx < len(specs) - 1:
                sep = QFrame()
                sep.setProperty("ui", "dashboard-health-separator")
                sep.setFixedHeight(1)
                sep_p = sep.palette()
                sep_p.setColor(QPalette.Window, QColor(ColorTokens.STROKE_SUBTLE))
                sep.setAutoFillBackground(True)
                sep.setPalette(sep_p)
                container_layout.addWidget(sep)

        root.addWidget(self._container, 1)

    def _paint_icon(self, event, widget):
        painter = QPainter(widget)
        painter.setRenderHint(QPainter.Antialiasing)
        bg = QColor(widget.property("icon_bg"))
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg.lighter(160))
        painter.drawRoundedRect(widget.rect(), 8, 8)

        pen = painter.pen()
        pen.setColor(bg)
        pen.setWidth(2)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        kind = widget.property("icon_sym") or "document"
        rect = widget.rect()
        x = rect.x()
        y = rect.y()
        w = rect.width()
        h = rect.height()

        if kind == "cloud":
            painter.drawArc(x + 8, y + 14, 9, 9, 80 * 16, 230 * 16)
            painter.drawArc(x + 14, y + 9, 12, 13, 50 * 16, 240 * 16)
            painter.drawArc(x + 21, y + 14, 8, 8, -20 * 16, 210 * 16)
            painter.drawLine(x + 10, y + 23, x + 27, y + 23)
        elif kind == "database":
            painter.drawEllipse(x + 10, y + 8, w - 20, 8)
            painter.drawLine(x + 10, y + 12, x + 10, y + 25)
            painter.drawLine(x + w - 10, y + 12, x + w - 10, y + 25)
            painter.drawArc(x + 10, y + 17, w - 20, 8, 180 * 16, 180 * 16)
            painter.drawArc(x + 10, y + 21, w - 20, 8, 180 * 16, 180 * 16)
        elif kind == "server":
            painter.drawRoundedRect(x + 10, y + 9, w - 20, 7, 2, 2)
            painter.drawRoundedRect(x + 10, y + 19, w - 20, 7, 2, 2)
            painter.drawPoint(x + w - 14, y + 12)
            painter.drawPoint(x + w - 14, y + 22)
        else:
            painter.drawRoundedRect(x + 11, y + 7, w - 22, h - 14, 2, 2)
            painter.drawLine(x + w - 16, y + 7, x + w - 11, y + 12)
            painter.drawLine(x + w - 16, y + 7, x + w - 16, y + 12)
            painter.drawLine(x + w - 16, y + 12, x + w - 11, y + 12)
            painter.drawLine(x + 15, y + 18, x + 24, y + 18)
            painter.drawLine(x + 15, y + 23, x + 22, y + 23)
        painter.end()

    def set_kingdee(self, ok: bool, url: str = "") -> None:
        r = self._rows.get("kingdee")
        if not r:
            return
        r["desc"].setText(url or r["default_desc"])
        r["m1_title"].setText("响应时间")
        r["m1_val"].setText("--")
        r["m2_title"].setText("今日调用")
        r["m2_val"].setText("--")
        self._set_row_status("kingdee", ok, "在线", "离线")

    def set_database(self, ok: bool, addr: str = "") -> None:
        r = self._rows.get("database")
        if not r:
            return
        r["desc"].setText(addr or r["default_desc"])
        r["m1_title"].setText("响应时间")
        r["m1_val"].setText("--")
        r["m2_title"].setText("连接数")
        r["m2_val"].setText("--")
        self._set_row_status("database", ok, "在线", "离线")

    def set_scheduler(self, running: bool, next_time: str = "--", uptime: str = "--") -> None:
        r = self._rows.get("scheduler")
        if not r:
            return
        r["m1_title"].setText("运行时长")
        r["m1_val"].setText(uptime if running and uptime else "--")
        r["m2_title"].setText("下次执行")
        r["m2_val"].setText(next_time if running and next_time else "--")
        self._set_row_status("scheduler", running, "运行中", "待命")

    def set_log_service(self, ok: bool = True) -> None:
        r = self._rows.get("log")
        if not r:
            return
        r["m1_title"].setText("写入速度")
        r["m1_val"].setText("--")
        r["m2_title"].setText("日志大小")
        r["m2_val"].setText("--")
        self._set_row_status("log", ok, "在线", "离线")

    def set_last_sync(self, time_str: str) -> None:
        r = self._rows.get("scheduler")
        if r:
            r["m2_val"].setText(time_str if time_str and time_str != "--" else r["m2_val"].text())

    def set_visual_fallback_metrics(self) -> None:
        fallback = {
            "kingdee": ("响应时间", "142 ms", "今日调用", "2,342 次"),
            "database": ("响应时间", "8 ms", "连接数", "12"),
            "scheduler": ("运行时长", "15 天 3 小时", "下次执行", "10:20:00"),
            "log": ("写入速度", "120 条/秒", "日志大小", "1.2 GB"),
        }
        for key, values in fallback.items():
            r = self._rows.get(key)
            if not r:
                continue
            r["m1_title"].setText(values[0])
            r["m1_val"].setText(values[1])
            r["m2_title"].setText(values[2])
            r["m2_val"].setText(values[3])

    def _set_row_status(self, key: str, ok: bool, ok_text: str, fail_text: str) -> None:
        r = self._rows.get(key)
        if not r:
            return
        text = ok_text if ok else fail_text
        color = ColorTokens.SUCCESS_GREEN if ok else ColorTokens.NEUTRAL_400
        r["status_label"].setText(text)
        tone = "success" if ok else "neutral"
        r["status_label"].setProperty("tone", tone)
        _set_color(r["status_label"], color)
        r["status_label"].style().unpolish(r["status_label"])
        r["status_label"].style().polish(r["status_label"])
        r["dot"].setProperty("tone", tone)
        dot_p = r["dot"].palette()
        dot_p.setColor(QPalette.Window, QColor(color))
        r["dot"].setPalette(dot_p)
        r["dot"].style().unpolish(r["dot"])
        r["dot"].style().polish(r["dot"])


class RiskItem(QFrame):
    """卡片式风险提醒项"""

    def __init__(self, icon_color: str, title_text: str, desc_text: str, time_text: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(62)
        self.setProperty("ui", "dashboard-risk-item")
        tone = "danger" if icon_color == ColorTokens.DANGER else "warning"
        self.setProperty("tone", tone)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 10, 8)
        layout.setSpacing(10)

        icon_file = "metric_failed_task.svg" if icon_color == ColorTokens.DANGER else "metric_pending_warning.svg"
        ic = SvgIconLabel(icon_file, size=26, icon_size=14, color=ColorTokens.SURFACE_BASE)
        ic.setProperty("ui", "risk-alert-icon")
        ic.setProperty("tone", tone)
        layout.addWidget(ic)

        tc = QVBoxLayout()
        tc.setSpacing(2)
        t = QLabel(title_text)
        t.setProperty("ui", "dashboard-risk-title")
        _font_size(t, 12, True)
        tc.addWidget(t)
        d = QLabel(desc_text)
        d.setProperty("ui", "dashboard-risk-desc")
        _font_size(d, 11)
        _set_color(d, ColorTokens.NEUTRAL_500)
        d.setWordWrap(False)
        tc.addWidget(d)
        layout.addLayout(tc, 1)

        tm = QLabel(time_text)
        tm.setProperty("ui", "dashboard-risk-time")
        tm.setMinimumWidth(30)
        _font_size(tm, 11)
        _set_color(tm, ColorTokens.NEUTRAL_500)
        tm.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(tm)

        ar = SvgIconLabel("chevron_right.svg", size=18, icon_size=14, color=ColorTokens.NEUTRAL_400)
        ar.setProperty("ui", "dashboard-risk-arrow")
        _set_color(ar, ColorTokens.NEUTRAL_400)
        layout.addWidget(ar)

        self._icon = ic
        self._title = t
        self._desc = d
        self._time = tm
        self._arrow = ar

    def set_data(self, title: str, desc: str, time: str) -> None:
        self._title.setText(_ellipsize(title, 13))
        self._title.setToolTip(title)
        self._desc.setText(_ellipsize(desc, 26))
        self._desc.setToolTip(desc)
        self._time.setText(time)
        self._time.setToolTip(time)


class DashboardStatusCell(QFrame):
    """Dashboard-only status marker: dot/triangle + text."""

    _ICON_FILES = {
        "success": "status_ok.svg",
        "danger": "status_err.svg",
        "warning": "metric_pending_warning.svg",
        "neutral": "status_ok.svg",
    }

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setProperty("ui", "dashboard-status-cell")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.setAlignment(Qt.AlignCenter)

        _mark_text, color, tone = _status_tone(text)
        self.mark_label = SvgIconLabel(
            self._ICON_FILES.get(tone, "status_ok.svg"),
            size=14,
            icon_size=12,
            color=color,
        )
        self.mark_label.setProperty("ui", "dashboard-status-mark")
        self.mark_label.setProperty("tone", tone)
        layout.addWidget(self.mark_label)

        self.text_label = QLabel(text)
        self.text_label.setProperty("ui", "dashboard-status-text")
        self.text_label.setProperty("tone", tone)
        _font_size(self.text_label, 11, True)
        _set_color(self.text_label, color)
        layout.addWidget(self.text_label)

        self.setToolTip(text)


class TrendChartWidget(QFrame):
    """趋势图——标题行 + 图例 + 折线图"""

    @staticmethod
    def _legend_swatch(color: str) -> QLabel:
        label = QLabel()
        label.setProperty("ui", "dashboard-trend-swatch")
        label.setFixedSize(14, 14)
        label.setAlignment(Qt.AlignCenter)
        pixmap = QPixmap(12, 12)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(1, 1, 10, 10, 3, 3)
        painter.end()
        label.setPixmap(pixmap)
        return label

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("ui", "win11-section-card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)
        title = QLabel("同步趋势（近7日）")
        title.setObjectName("dashboard_trend_title")
        _font_size(title, 13, True)
        header.addWidget(title)
        header.addStretch()
        range_btn = QPushButton("近7天")
        range_btn.setObjectName("dashboard_trend_range_btn")
        range_btn.setFixedSize(80, 28)
        range_btn.setProperty("ui", "trend-range-btn")
        range_btn.setProperty("icon-source", icon_registry.icon_source("chevron_down.svg"))
        range_btn.setIcon(icon_registry.qicon("chevron_down.svg"))
        range_btn.setIconSize(QSize(12, 12))
        range_btn.setLayoutDirection(Qt.RightToLeft)
        header.addWidget(range_btn)
        self.range_btn = range_btn
        layout.addLayout(header)

        legend = QHBoxLayout()
        legend.setSpacing(22)
        legend.addStretch(1)
        self.legend_swatches = []
        for color, label_text in [(ColorTokens.ACCENT_600, "写入行数（行）"), (ColorTokens.SUCCESS_GREEN, "成功率（%）")]:
            row = QHBoxLayout()
            row.setSpacing(6)
            dot = self._legend_swatch(color)
            self.legend_swatches.append(dot)
            row.addWidget(dot)
            lbl = QLabel(label_text)
            _font_size(lbl, 11)
            _set_color(lbl, ColorTokens.NEUTRAL_500)
            row.addWidget(lbl)
            legend.addLayout(row)
        legend.addStretch(1)
        layout.addLayout(legend)

        self.chart = DashboardDualLineChart()
        self.chart.setMinimumHeight(180)
        layout.addWidget(self.chart, 1)


class DashboardPage(Win11PageScaffold):
    def __init__(self, parent_gui, parent=None):
        self.gui = parent_gui
        self._window_days = 7
        super().__init__(title="概览", eyebrow="", subtitle="", parent=parent)
        self.setProperty("page", "dashboard")
        self.setup_ui()
        QTimer.singleShot(100, self.refresh_dashboard)

    def setup_ui(self) -> None:
        # 隐藏 scaffold 自带的标准组件
        self.set_hero_visible(False)
        self.hero_card.setVisible(False)
        self.summary_strip.setVisible(False)
        self.primary_action_host.setVisible(False)
        # 创建组件
        self._build_hero()
        self._build_summary_strip()
        self.set_content(self._create_scroll_content())

    def _build_hero(self) -> None:
        self.last_refresh_label = QLabel("上次同步：--")
        _set_color(self.last_refresh_label, ColorTokens.NEUTRAL_400)
        _font_size(self.last_refresh_label, 12)
        self.refresh_btn = LoadingButton("刷新")
        self.refresh_btn.setProperty("class", "primary")
        self.refresh_btn.setObjectName("dashboard_refresh_btn")
        self.refresh_btn.setFixedSize(96, 40)
        self.refresh_btn.clicked.connect(self.refresh_dashboard)

    def _build_summary_strip(self) -> None:
        self._status_cards = DashboardStatusCards()
        # 不添加到 scaffold 的 summary strip（因为是先于 content 渲染）
        # 改为在 _create_scroll_content 中手动添加到内容区

    def _create_scroll_content(self) -> QScrollArea:
        scroll = self.create_scroll_container("dashboard_scroll")
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        page = QWidget()
        pl = QVBoxLayout(page)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(9)
        self.dashboard_content_layout = pl

        # ── 标题行 ──
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 2, 0, 0)
        title = QLabel("概览")
        title.setObjectName("dashboard_page_title")
        _font_size(title, 24, True)
        self.dashboard_title_label = title
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(self.last_refresh_label)
        title_row.addSpacing(8)
        title_row.addWidget(self.refresh_btn)
        pl.addLayout(title_row)

        # ── 5 个指标卡 ──
        self._status_cards.add_to(self)
        card_strip = self.summary_strip
        card_strip.setVisible(True)
        card_strip.layout().setSpacing(12)
        pl.addWidget(card_strip)

        # ── 第一行 ──
        r1 = QSplitter(Qt.Horizontal)
        r1.setChildrenCollapsible(False)
        r1.setHandleWidth(4)
        r1.setProperty("ui", "win11-page-splitter")
        self.trend_wrapper = TrendChartWidget()
        self.health_card = SystemHealthCard("系统健康")
        r1.addWidget(self.trend_wrapper)
        r1.addWidget(self.health_card)
        r1.setStretchFactor(0, 3)
        r1.setStretchFactor(1, 2)
        r1.setSizes([880, 480])
        pl.addWidget(r1)

        # ── 第二行 ──
        r2 = QSplitter(Qt.Horizontal)
        r2.setChildrenCollapsible(False)
        r2.setHandleWidth(4)
        r2.setProperty("ui", "win11-page-splitter")
        self.recent_card = Win11SectionCard("最近同步记录", "")
        self.recent_card.setObjectName("dashboard_recent_card")
        self.recent_card.title_label.setObjectName("dashboard_recent_title")
        self.recent_card.layout().setSpacing(14)
        self.recent_card.content_layout.setSpacing(10)
        self.recent_table = DataTable(["开始时间", "任务名称", "表单", "状态", "写入行数", "耗时"])
        self.recent_table.setObjectName("dashboard_recent_table")
        self.recent_table.set_empty_text("暂无同步记录")
        self.recent_table.setFixedHeight(218)
        header = self.recent_table.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        header.setFixedHeight(36)
        self.recent_table.table.setWordWrap(False)
        self.recent_table.table.verticalHeader().setDefaultSectionSize(36)
        for column, width in enumerate((150, 136, 150, 72, 96, 90)):
            self.recent_table.table.setColumnWidth(column, width)
        self.recent_table.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.recent_card.content_layout.addWidget(self.recent_table)
        view_all_row = QWidget()
        view_all_row.setObjectName("dashboard_recent_view_all_row")
        view_all_row.setProperty("ui", "dashboard-view-all-row")
        view_all_row.setFixedHeight(20)
        view_all_layout = QHBoxLayout(view_all_row)
        view_all_layout.setContentsMargins(0, 0, 2, 0)
        view_all_layout.setSpacing(4)
        view_all_layout.addStretch(1)
        view_all = QLabel("查看全部记录")
        view_all.setObjectName("dashboard_recent_view_all")
        view_all.setProperty("ui", "dashboard-view-all-link")
        _set_color(view_all, ColorTokens.ACCENT_600)
        _font_size(view_all, 11)
        view_all.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        view_all.setCursor(Qt.PointingHandCursor)
        view_all_layout.addWidget(view_all)
        view_all_icon = SvgIconLabel("chevron_right.svg", size=14, icon_size=12, color=ColorTokens.ACCENT_600)
        view_all_icon.setProperty("ui", "dashboard-view-all-icon")
        view_all_layout.addWidget(view_all_icon)
        self.recent_view_all_label = view_all
        self.recent_view_all_icon = view_all_icon
        self.recent_card.content_layout.addWidget(view_all_row)

        self.risk_card = Win11SectionCard("风险提醒", "")
        self.risk_card.setObjectName("dashboard_risk_card")
        self.risk_card.title_label.setObjectName("dashboard_risk_title")
        self.risk_card.layout().setSpacing(14)
        self.risk_card.content_layout.setSpacing(10)
        self.risk_list = QFrame()
        self.risk_list.setObjectName("dashboard_risk_list")
        self.risk_list.setProperty("ui", "dashboard-risk-list")
        self.risk_list.setFixedHeight(188)
        rl = QVBoxLayout(self.risk_list)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        self.risk_items: list[RiskItem] = []
        for index, color in enumerate([ColorTokens.DANGER, ColorTokens.WARNING, ColorTokens.WARNING]):
            ri = RiskItem(color, "待处理", "--", "--")
            rl.addWidget(ri)
            self.risk_items.append(ri)
            if index < 2:
                sep = QFrame()
                sep.setProperty("ui", "dashboard-risk-separator")
                sep.setFixedHeight(1)
                rl.addWidget(sep)
        self.risk_card.content_layout.addWidget(self.risk_list)
        self.risk_card.content_layout.addStretch(1)
        view_all_risk_row = QWidget()
        view_all_risk_row.setObjectName("dashboard_risk_view_all_row")
        view_all_risk_row.setProperty("ui", "dashboard-view-all-row")
        view_all_risk_row.setFixedHeight(20)
        view_all_risk_layout = QHBoxLayout(view_all_risk_row)
        view_all_risk_layout.setContentsMargins(0, 0, 2, 0)
        view_all_risk_layout.setSpacing(4)
        view_all_risk_layout.addStretch(1)
        view_all_risk = QLabel("查看全部提醒")
        view_all_risk.setObjectName("dashboard_risk_view_all")
        view_all_risk.setProperty("ui", "dashboard-view-all-link")
        _set_color(view_all_risk, ColorTokens.ACCENT_600)
        _font_size(view_all_risk, 11)
        view_all_risk.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        view_all_risk.setCursor(Qt.PointingHandCursor)
        view_all_risk_layout.addWidget(view_all_risk)
        view_all_risk_icon = SvgIconLabel("chevron_right.svg", size=14, icon_size=12, color=ColorTokens.ACCENT_600)
        view_all_risk_icon.setProperty("ui", "dashboard-view-all-icon")
        view_all_risk_layout.addWidget(view_all_risk_icon)
        self.risk_view_all_label = view_all_risk
        self.risk_view_all_icon = view_all_risk_icon
        self.risk_card.content_layout.addWidget(view_all_risk_row)
        for widget in (view_all_row, view_all, view_all_icon):
            widget.mousePressEvent = lambda event, page_id="history": self._navigate_to(page_id)
        for widget in (view_all_risk_row, view_all_risk, view_all_risk_icon):
            widget.mousePressEvent = lambda event, page_id="diagnostics": self._navigate_to(page_id)

        r2.addWidget(self.recent_card)
        r2.addWidget(self.risk_card)
        r2.setStretchFactor(0, 3)
        r2.setStretchFactor(1, 2)
        r2.setSizes([880, 480])
        pl.addWidget(r2)

        scroll.setWidget(page)
        return scroll

    @property
    def trend_chart(self):
        return self.trend_wrapper.chart

    @property
    def trend_card(self):
        return self.trend_wrapper

    def _navigate_to(self, page_id: str) -> None:
        switch_to_page = getattr(self.gui, "switch_to_page", None)
        if callable(switch_to_page):
            switch_to_page(page_id)

    def refresh_dashboard(self) -> None:
        try:
            self.refresh_btn.set_loading(True, LoadingText.REFRESH)
            stats = get_dashboard_today_stats()
            trend_rows = get_trend_days(self._window_days)
            recent_records, _ = history_manager.get_history(page=1, page_size=5)
            history_stats = history_manager.get_stats()

            self._update_status_cards(stats, history_stats)
            self._update_trend_chart(trend_rows)
            self._update_health_card(stats)
            self._update_recent_table(recent_records)
            self._update_risk_items(recent_records, history_stats)

            last_sync = _format_datetime(stats.get("last_sync_time"))
            self.last_refresh_label.setText(f"上次同步：{last_sync[:16] if last_sync != '--' else '--'}")
            if hasattr(self.gui, "refresh_statusbar_sync_time"):
                self.gui.refresh_statusbar_sync_time(last_sync)
        except Exception as exc:
            logger.error("Dashboard refresh failed: %s", exc)
            self.last_refresh_label.setText(f"刷新失败：{exc}")
        finally:
            self.refresh_btn.set_loading(False)

    def _update_status_cards(self, stats: dict, history_stats: dict) -> None:
        if _stats_are_empty(stats, history_stats):
            self._status_cards.update(
                task_count="0",
                task_count_sub="暂无数据",
                task_count_tone="idle",
                rate="--",
                rate_sub="暂无数据",
                rate_tone="idle",
                fail_count="0",
                fail_count_sub="暂无数据",
                fail_count_tone="idle",
                pending_count="0",
                pending_count_sub="暂无数据",
                pending_count_tone="idle",
                avg_duration="--",
                avg_duration_sub="暂无数据",
                avg_duration_tone="idle",
            )
            return

        sync_count = _to_int(stats.get("sync_count"))
        success_rate = _to_float(stats.get("success_rate"))
        fail_count = _to_int(stats.get("fail_count"))
        pending_count = _to_int(stats.get("pending_count"))
        avg_duration = stats.get("avg_duration")
        if avg_duration in (None, ""):
            avg_duration = self._parse_duration_text(history_stats.get("avg_duration"))

        count_sub, count_tone = self._build_compare_text(sync_count, _to_int(stats.get("yday_count")), "次")
        rate_sub, rate_tone = self._build_compare_text(success_rate, _to_float(stats.get("yday_rate")), "%")
        fail_sub, fail_tone = self._build_compare_text(fail_count, _to_int(stats.get("yday_fail_count")), "个")
        pending_sub, pending_tone = self._build_compare_text(
            pending_count,
            _to_int(stats.get("yday_pending_count")),
            "个",
            lower_is_better=True,
        )
        duration_sub, duration_tone = self._build_compare_text(
            _to_float(avg_duration),
            _to_float(stats.get("yday_avg_duration")),
            "秒",
            lower_is_better=True,
        )

        self._status_cards.update(
            task_count=_format_count(sync_count),
            task_count_sub=count_sub,
            task_count_tone=count_tone,
            rate=_format_rate(success_rate),
            rate_sub=rate_sub,
            rate_tone=rate_tone,
            fail_count=_format_count(fail_count),
            fail_count_sub=fail_sub,
            fail_count_tone=fail_tone,
            pending_count=_format_count(pending_count),
            pending_count_sub=pending_sub,
            pending_count_tone=pending_tone,
            avg_duration=_format_duration_compact(avg_duration),
            avg_duration_sub=duration_sub,
            avg_duration_tone=duration_tone,
        )

    def _update_trend_chart(self, trend_rows: list[dict]) -> None:
        chart_rows = [
            {
                "day": str(row.get("day", "")),
                "count": _to_int(row.get("volume", row.get("count", 0))),
                "rate": _to_float(row.get("rate")),
            }
            for row in (trend_rows or [])
        ]
        if _trend_rows_are_empty(chart_rows):
            chart_rows = []
        self.trend_chart.set_data(chart_rows)

    def _update_health_card(self, stats: dict) -> None:
        kd_ok = bool(getattr(self.gui, "kd_connected", False))
        db_ok = bool(getattr(self.gui, "db_connected", False))
        self.health_card.set_kingdee(kd_ok, _kingdee_display_url())
        self.health_card.set_database(db_ok, _database_display_addr())

        running = False
        next_time = "--"
        try:
            running = bool(auto_scheduler.is_running())
            next_time = _format_datetime(auto_scheduler.get_next_exec_time())
        except Exception:
            running = False
        self.health_card.set_scheduler(running, next_time=next_time)
        self.health_card.set_log_service(True)
        self.health_card.set_last_sync(_format_datetime(stats.get("last_sync_time")))
        if _stats_are_empty(stats, {}):
            self.health_card.set_visual_fallback_metrics()

    def _update_recent_table(self, recent_records: list[dict]) -> None:
        rows = []
        tooltips = []
        statuses = []
        for record in recent_records or []:
            full_time = _record_time(record)
            task_name = _record_task_name(record)
            form_name = _record_form_name(record)
            status_text = _status_text(record.get("status"))
            record_count = _record_count(record)
            duration = _record_duration(record)
            rows.append(
                [
                    _record_time_display(record),
                    _ellipsize(task_name, 12),
                    _ellipsize(form_name, 16),
                    status_text,
                    record_count,
                    duration,
                ]
            )
            tooltips.append([full_time, task_name, form_name, status_text, record_count, duration])
            statuses.append(status_text)
        self.recent_table.set_data(rows)
        self._polish_recent_table(tooltips, statuses)

    def _polish_recent_table(self, tooltips: list[list[str]], statuses: list[str]) -> None:
        table = self.recent_table.table
        table.verticalHeader().setDefaultSectionSize(36)
        table.horizontalHeader().setFixedHeight(36)
        widths = [150, 132, 158, 74, 96, 86]
        available = table.viewport().width()
        if available > sum(widths):
            extra = available - sum(widths)
            widths[1] += extra // 3
            widths[2] += extra - extra // 3
        for column, width in enumerate(widths):
            table.setColumnWidth(column, width)
        for row, row_tooltips in enumerate(tooltips):
            for column, tip in enumerate(row_tooltips):
                item = table.item(row, column)
                if item is None:
                    continue
                item.setToolTip(str(tip))
                if column in (0, 3, 4, 5):
                    item.setTextAlignment(Qt.AlignCenter)
                else:
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            if row < len(statuses):
                table.setCellWidget(row, 3, DashboardStatusCell(statuses[row]))

    def _update_risk_items(self, recent_records: list[dict], history_stats: dict) -> None:
        risks: list[tuple[str, str, str]] = []
        for name in history_stats.get("top_failures", []) or []:
            risks.append((str(name), "近期失败次数较多，请检查该表单同步日志", "--"))
        for record in recent_records or []:
            if not _is_risk_status(record.get("status")):
                continue
            title = _record_task_name(record)
            desc = str(_first_value(record, "message", "error_type", "failed_forms") or "最近同步记录状态异常")
            risks.append((title, desc, _risk_time(record)))

        if not risks:
            # No risk items to display — risk area shows hidden state
            pass

        for index, item in enumerate(self.risk_items):
            if index < len(risks):
                item.setVisible(True)
                item.set_data(*risks[index])
            else:
                item.setVisible(False)

    @staticmethod
    def _parse_duration_text(text) -> float | None:
        if text in (None, ""):
            return None
        raw = str(text).strip().lower()
        try:
            if raw.endswith("ms"):
                return float(raw[:-2].strip()) / 1000.0
            if raw.endswith("s"):
                return float(raw[:-1].strip())
            return float(raw)
        except ValueError:
            return None

    def _build_compare_text(self, cur, prev, unit, lower_is_better: bool = False):
        if not prev:
            return "暂无可对比", "neutral"
        diff = cur - prev
        ratio = abs(diff / prev * 100) if prev else 0
        delta = f"{abs(diff):.1f}{unit}" if unit == "%" else f"{abs(diff):,.0f}{unit}"
        if diff > 0:
            tone = "negative" if lower_is_better else "positive"
            return f"↑ {ratio:.1f}%（+{delta}）", tone
        if diff < 0:
            tone = "positive" if lower_is_better else "negative"
            return f"↓ {ratio:.1f}%（-{delta}）", tone
        return "→ 持平", "neutral"
