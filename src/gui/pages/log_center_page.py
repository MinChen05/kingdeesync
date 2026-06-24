"""Log center page with real log data from app.jsonl."""

from __future__ import annotations

import json
import logging
import os
from collections import Counter
from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.gui.components.common import StatusChip, SvgIconLabel
from src.gui.components.data_table import DataTable
from src.gui.components.page_shell import Win11PageScaffold, Win11SectionCard
from src.gui.design_tokens import ColorTokens, SizeTokens, SpacingTokens

logger = logging.getLogger(__name__)

_SENSITIVE_PATTERNS = ("password", "token", "secret", "app_key", "authorization", "credential")

_LEVEL_LABELS = {
    "INFO": "信息",
    "WARNING": "警告",
    "ERROR": "错误",
    "DEBUG": "调试",
    "CRITICAL": "严重",
}

_MODULE_LABELS = {
    "kingdee_api": "金蝶 API",
    "mysql_manager": "SQL Server",
    "scheduler": "调度服务",
    "data_sync": "数据同步",
    "form_sync_runner": "数据写入",
    "kingdee_sync_tool": "系统",
    "retry_manager": "重试管理",
    "sync_page": "同步执行",
    "schedule_page": "调度管理",
    "dashboard_page": "概览",
    "log_center_page": "日志中心",
}

_MESSAGE_TRANSLATIONS = (
    ("cannot be null", "不能为空"),
    ("login failed", "登录失败"),
    ("timeout", "请求超时"),
    ("connection refused", "连接被拒绝"),
    ("connection reset", "连接被重置"),
    ("permission denied", "权限不足"),
    ("duplicate key", "重复键冲突"),
    ("deadlock", "数据库死锁"),
    ("failed", "失败"),
    ("success", "成功"),
)


def _mask_sensitive(text: str) -> str:
    """Mask sensitive information in log messages."""
    lower = text.lower()
    for pattern in _SENSITIVE_PATTERNS:
        if pattern in lower:
            return "[REDACTED]"
    return text


def _friendly_level(level: str) -> str:
    """Return a Chinese display label for a log level."""
    level = str(level or "--")
    return _LEVEL_LABELS.get(level.upper(), level)


def _friendly_module(module: str) -> str:
    """Return a Chinese display label while preserving unknown module names."""
    module = str(module or "--")
    lower = module.lower()
    for key, label in _MODULE_LABELS.items():
        if key in lower:
            return label
    return module.split(".")[-1] if "." in module else module


def _friendly_message(message: str) -> str:
    """Translate common English fragments without changing field names/errors."""
    masked = _mask_sensitive(str(message or "--"))
    if masked == "[REDACTED]":
        return masked

    friendly = masked
    for english, chinese in _MESSAGE_TRANSLATIONS:
        friendly = friendly.replace(english, chinese)
        friendly = friendly.replace(english.capitalize(), chinese)
        friendly = friendly.replace(english.upper(), chinese)

    field_prefixes = ("Field '", 'Field "')
    for prefix in field_prefixes:
        if prefix in friendly and "不能为空" in friendly:
            field = friendly.split(prefix, 1)[1].split(prefix[-1], 1)[0]
            return f"字段 {field} 不能为空" + (f"；{friendly}" if "；" not in friendly else "")

    return friendly


def _get_log_dir() -> str:
    """Get the log directory path."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    return os.path.join(base_dir, "logs")


def _read_jsonl_logs(max_lines: int = 1000) -> list[dict]:
    """Read log entries from app.jsonl."""
    log_file = os.path.join(_get_log_dir(), "app.jsonl")
    if not os.path.exists(log_file):
        return []

    entries = []
    try:
        with open(log_file, encoding="utf-8") as f:
            for line in f:
                if len(entries) >= max_lines:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    entries.append(entry)
                except json.JSONDecodeError:
                    continue
    except Exception as exc:
        logger.warning("Failed to read log file: %s", exc)

    return entries


class _ModuleItem(QFrame):
    """Module sidebar entry with name, icon, and count."""

    def __init__(self, name: str, count: str, indent: int = 0, selected: bool = False, parent=None):
        super().__init__(parent)
        self.setProperty("ui", "lc-module-item")
        if selected:
            self.setProperty("selected", True)

        root = QHBoxLayout(self)
        root.setContentsMargins(14 + indent * 16, 8, 14, 8)
        root.setSpacing(8)

        icon_lbl = SvgIconLabel("log_total.svg", size=16, icon_size=14, color=_module_icon_color(name))
        root.addWidget(icon_lbl)

        name_lbl = QLabel(name)
        name_lbl.setProperty("ui", "lc-module-name")
        root.addWidget(name_lbl, 1)

        if count:
            count_lbl = QLabel(count)
            count_lbl.setProperty("ui", "lc-module-count")
            count_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            root.addWidget(count_lbl)


def _module_icon_color(module: str) -> str:
    """Return icon color based on module name."""
    color_map = {
        "全部模块": ColorTokens.ACCENT_600,
        "金蝶 API": ColorTokens.ACCENT_600,
        "SQL Server": ColorTokens.SUCCESS_GREEN,
        "调度服务": ColorTokens.WARNING,
        "日志服务": ColorTokens.NEUTRAL_500,
        "数据同步任务": ColorTokens.INFO,
        "系统": ColorTokens.NEUTRAL_500,
    }
    return color_map.get(module, ColorTokens.NEUTRAL_500)


class LogCenterPage(Win11PageScaffold):
    """Log center page with real log data from app.jsonl."""

    _FALLBACK_LOG_ROWS = [
        ["--", "--", "--", "--", "暂无日志数据"],
    ]

    _FALLBACK_MODULES = [
        ("全部模块", "0", 0),
    ]

    def __init__(self, parent_gui, parent=None):
        self.gui = parent_gui
        self._all_entries: list[dict[str, Any]] = []
        self._filtered_entries: list[dict[str, Any]] = []
        self._selected_module = "全部"
        super().__init__(
            title="日志中心",
            eyebrow="",
            subtitle="集中查看运行日志，按时间、级别、模块和关键词筛选",
            parent=parent,
        )
        self.setProperty("page", "log-center")
        self.set_hero_visible(False)
        self.hero_card.setVisible(False)
        self.primary_action_host.setVisible(False)
        self.summary_strip.setVisible(False)
        self._build_ui()
        self._load_real_data()

    def _build_ui(self) -> None:
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        title_row = QWidget()
        title_layout = QHBoxLayout(title_row)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(12)

        self.page_title = QLabel("日志中心")
        self.page_title.setProperty("ui", "lc-page-title")
        title_layout.addWidget(self.page_title)
        title_layout.addStretch()

        self.btn_clear = QPushButton("清空视图")
        self.btn_clear.setProperty("class", "secondary")
        self.btn_clear.setFixedHeight(36)
        self.btn_clear.clicked.connect(self.clear_view)
        title_layout.addWidget(self.btn_clear)

        self.btn_copy = QPushButton("复制日志")
        self.btn_copy.setProperty("class", "secondary")
        self.btn_copy.setFixedHeight(36)
        self.btn_copy.clicked.connect(self.copy_logs)
        title_layout.addWidget(self.btn_copy)

        self.btn_export = QPushButton("导出日志")
        self.btn_export.setProperty("class", "primary")
        self.btn_export.setFixedHeight(36)
        self.btn_export.clicked.connect(self.export_logs)
        title_layout.addWidget(self.btn_export)
        content_layout.addWidget(title_row)

        filter_row = QWidget()
        filter_layout = QHBoxLayout(filter_row)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(12)

        time_label = QLabel("时间范围")
        time_label.setProperty("ui", "lc-filter-label")
        filter_layout.addWidget(time_label)

        self.combo_time = QComboBox()
        self.combo_time.addItems(["今天", "最近 7 天", "最近 30 天"])
        self.combo_time.setFixedHeight(34)
        self.combo_time.setMinimumWidth(180)
        self.combo_time.currentTextChanged.connect(lambda _text: self.apply_filters())
        filter_layout.addWidget(self.combo_time)

        level_label = QLabel("日志级别")
        level_label.setProperty("ui", "lc-filter-label")
        filter_layout.addWidget(level_label)

        self.combo_level = QComboBox()
        self.combo_level.addItems(["全部", "信息", "警告", "错误"])
        self.combo_level.setFixedHeight(34)
        self.combo_level.setMinimumWidth(100)
        self.combo_level.currentTextChanged.connect(lambda _text: self.apply_filters())
        filter_layout.addWidget(self.combo_level)

        module_label = QLabel("模块")
        module_label.setProperty("ui", "lc-filter-label")
        filter_layout.addWidget(module_label)

        self.combo_module = QComboBox()
        self.combo_module.addItems(["全部", "金蝶 API", "SQL Server", "调度服务", "数据同步任务"])
        self.combo_module.setFixedHeight(34)
        self.combo_module.setMinimumWidth(120)
        self.combo_module.currentTextChanged.connect(self._set_module_filter)
        filter_layout.addWidget(self.combo_module)

        task_label = QLabel("任务名称")
        task_label.setProperty("ui", "lc-filter-label")
        filter_layout.addWidget(task_label)

        self.combo_task = QComboBox()
        self.combo_task.addItems(["全部"])
        self.combo_task.setFixedHeight(34)
        self.combo_task.setMinimumWidth(120)
        self.combo_task.currentTextChanged.connect(lambda _text: self.apply_filters())
        filter_layout.addWidget(self.combo_task)

        search_label = QLabel("关键词搜索")
        search_label.setProperty("ui", "lc-filter-label")
        filter_layout.addWidget(search_label)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索日志内容或错误摘要")
        self.search_box.setFixedHeight(34)
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setMinimumWidth(180)
        self.search_box.editingFinished.connect(self.apply_filters)
        filter_layout.addWidget(self.search_box, 1)
        content_layout.addWidget(filter_row)

        stats_row = QWidget()
        stats_layout = QHBoxLayout(stats_row)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(12)

        self.stat_defs = [
            ("今日日志", "0", "较昨日 --", ColorTokens.ACCENT_600),
            ("错误", "0", "较昨日 --", ColorTokens.DANGER),
            ("警告", "0", "较昨日 --", ColorTokens.WARNING),
            ("最近错误时间", "--", "--", ColorTokens.INFO),
            ("日志文件大小", "0 MB", "较昨日 --", ColorTokens.SUCCESS_GREEN),
        ]
        for index, (title, value, trend, color) in enumerate(self.stat_defs):
            icon_file = (
                "log_total.svg",
                "log_error.svg",
                "log_warning.svg",
                "log_recent.svg",
                "log_size.svg",
            )[index]
            card = self._create_stat_card(title, value, trend, color, icon_file)
            stats_layout.addWidget(card)
        content_layout.addWidget(stats_row)

        body_splitter = QSplitter(Qt.Horizontal)
        body_splitter.setHandleWidth(1)

        sidebar_widget = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        sidebar_header_row = QHBoxLayout()
        sidebar_header_row.setContentsMargins(14, 10, 14, 6)
        sidebar_header_row.setSpacing(8)
        sidebar_header = QLabel("模块与日志文件")
        sidebar_header.setProperty("ui", "lc-sidebar-title")
        sidebar_header_row.addWidget(sidebar_header)
        sidebar_header_row.addStretch()
        refresh_btn = QPushButton("")
        refresh_btn.setProperty("ui", "lc-refresh-btn")
        refresh_btn.setProperty("icon-source", "refresh.svg")
        refresh_btn.setIcon(QIcon(str(SvgIconLabel._ASSETS_DIR / "icons" / "refresh.svg")))
        refresh_btn.setFixedSize(24, 24)
        sidebar_header_row.addWidget(refresh_btn)
        sidebar_layout.addLayout(sidebar_header_row)

        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setFrameShape(QFrame.NoFrame)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.sidebar_content = QWidget()
        self.sidebar_content_layout = QVBoxLayout(self.sidebar_content)
        self.sidebar_content_layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar_content_layout.setSpacing(0)
        self.sidebar_content_layout.addStretch()
        sidebar_scroll.setWidget(self.sidebar_content)
        sidebar_layout.addWidget(sidebar_scroll, 1)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        view_toggle_row = QHBoxLayout()
        view_toggle_row.setContentsMargins(0, 0, 0, 8)
        view_toggle_row.setSpacing(8)
        view_toggle_row.addStretch()

        self.btn_table_view = QPushButton("表格视图")
        self.btn_table_view.setProperty("ui", "lc-view-btn")
        self.btn_table_view.setFixedHeight(30)
        self.btn_table_view.setCheckable(True)
        self.btn_table_view.setChecked(True)
        view_toggle_row.addWidget(self.btn_table_view)

        self.btn_text_view = QPushButton("文本视图")
        self.btn_text_view.setProperty("ui", "lc-view-btn")
        self.btn_text_view.setFixedHeight(30)
        self.btn_text_view.setCheckable(True)
        self.btn_text_view.setVisible(False)
        view_toggle_row.addWidget(self.btn_text_view)
        right_layout.addLayout(view_toggle_row)

        self.log_table = DataTable(["时间", "级别", "模块", "任务", "消息"])
        self.log_table.set_empty_text("暂无日志记录")
        right_layout.addWidget(self.log_table, 1)

        body_splitter.addWidget(sidebar_widget)
        body_splitter.addWidget(right_widget)
        body_splitter.setStretchFactor(0, 0)
        body_splitter.setStretchFactor(1, 1)
        body_splitter.setSizes([280, 800])

        content_layout.addWidget(body_splitter, 1)

        bottom_row = QWidget()
        bottom_layout = QHBoxLayout(bottom_row)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(16)

        self.auto_scroll_btn = QPushButton("自动滚动")
        self.auto_scroll_btn.setProperty("ui", "lc-bottom-btn")
        self.auto_scroll_btn.setCheckable(True)
        bottom_layout.addWidget(self.auto_scroll_btn)

        self.error_only_btn = QPushButton("仅显示错误")
        self.error_only_btn.setProperty("ui", "lc-bottom-btn")
        self.error_only_btn.setCheckable(True)
        self.error_only_btn.clicked.connect(self.apply_filters)
        bottom_layout.addWidget(self.error_only_btn)

        refresh_label = QLabel("刷新间隔")
        refresh_label.setProperty("ui", "lc-bottom-label")
        refresh_label.setVisible(False)
        self.refresh_label = refresh_label
        bottom_layout.addWidget(refresh_label)

        self.refresh_combo = QComboBox()
        self.refresh_combo.addItems(["3 秒", "5 秒", "10 秒", "30 秒"])
        self.refresh_combo.setFixedHeight(28)
        self.refresh_combo.setMinimumWidth(80)
        self.refresh_combo.setVisible(False)
        bottom_layout.addWidget(self.refresh_combo)

        bottom_layout.addStretch()

        self.lbl_total = QLabel("筛选结果 0 条")
        self.lbl_total.setProperty("ui", "lc-bottom-label")
        bottom_layout.addWidget(self.lbl_total)

        self.lbl_page = QLabel("筛选结果")
        self.lbl_page.setProperty("ui", "lc-bottom-label")
        bottom_layout.addWidget(self.lbl_page)

        page_size_label = QLabel("")
        page_size_label.setProperty("ui", "lc-bottom-label")
        page_size_label.setVisible(False)
        self.page_size_label = page_size_label
        bottom_layout.addWidget(page_size_label)

        content_layout.addWidget(bottom_row)

        self.set_content(content_widget)

    def _create_stat_card(self, title: str, value: str, trend: str, color: str, icon_file: str) -> QWidget:
        """Create a stat card with icon, value, and trend."""
        card = QFrame()
        card.setProperty("ui", "lc-stat-card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        icon_widget = SvgIconLabel(icon_file, size=36, icon_size=22, color=color)
        icon_widget.setProperty("ui", "lc-stat-icon")
        layout.addWidget(icon_widget)

        title_lbl = QLabel(title)
        title_lbl.setProperty("ui", "lc-stat-title")
        layout.addWidget(title_lbl)

        value_lbl = QLabel(value)
        value_lbl.setProperty("ui", "lc-stat-value")
        layout.addWidget(value_lbl)

        trend_lbl = QLabel(trend)
        trend_lbl.setProperty("ui", "lc-stat-trend")
        layout.addWidget(trend_lbl)

        card._value_label = value_lbl
        card._trend_label = trend_lbl
        return card

    def _load_real_data(self) -> None:
        """Load real log data from app.jsonl."""
        try:
            self._all_entries = _read_jsonl_logs(max_lines=10000)
            self._populate_filter_options()
            self._load_log_stats()
        except Exception as exc:
            logger.warning("Failed to load log stats: %s", exc)

        try:
            self.apply_filters()
        except Exception as exc:
            logger.warning("Failed to load log table: %s", exc)

        try:
            self._load_module_list()
        except Exception as exc:
            logger.warning("Failed to load module list: %s", exc)

    def _load_log_stats(self) -> None:
        """Load log statistics from real log data."""
        entries = self._all_entries

        total = len(entries)
        error_count = sum(1 for e in entries if e.get("levelname") == "ERROR")
        warning_count = sum(1 for e in entries if e.get("levelname") == "WARNING")

        last_error_time = "--"
        for e in reversed(entries):
            if e.get("levelname") == "ERROR":
                last_error_time = e.get("asctime", "--")[:19]
                break

        log_file = os.path.join(_get_log_dir(), "app.jsonl")
        file_size = "0 MB"
        if os.path.exists(log_file):
            size_bytes = os.path.getsize(log_file)
            file_size = f"{size_bytes / (1024 * 1024):.1f} MB"

        stat_cards = [w for w in self.findChildren(QFrame) if w.property("ui") == "lc-stat-card"]
        if len(stat_cards) >= 5:
            stat_cards[0]._value_label.setText(f"{total:,}")
            stat_cards[1]._value_label.setText(str(error_count))
            stat_cards[2]._value_label.setText(str(warning_count))
            stat_cards[3]._value_label.setText(last_error_time)
            stat_cards[4]._value_label.setText(file_size)

    def _load_log_table(self) -> None:
        """Load log table from real log data."""
        self.apply_filters()

    def _load_module_list(self) -> None:
        """Load module list from real log data."""
        entries = self._all_entries

        module_counter = Counter()
        for e in entries:
            name = e.get("name", "unknown")
            module_counter[name] += 1

        modules = [("全部模块", str(len(entries)), 0)]

        for name, count in module_counter.most_common(20):
            short_name = name.split(".")[-1] if "." in name else name
            modules.append((short_name, str(count), 0))

        for item in self.sidebar_content.findChildren(_ModuleItem):
            self.sidebar_content_layout.removeWidget(item)
            item.deleteLater()

        for i, (name, count, indent) in enumerate(modules):
            item = _ModuleItem(name, count, indent=indent, selected=(i == 0))
            item.mousePressEvent = lambda _event, module=name: self._set_module_filter(module)
            self.sidebar_content_layout.insertWidget(i, item)

    def _populate_filter_options(self) -> None:
        """Populate task options from the loaded log messages."""
        tasks = sorted({self._extract_task(entry) for entry in self._all_entries if self._extract_task(entry) != "--"})
        current = self.combo_task.currentText() if hasattr(self, "combo_task") else "全部"
        self.combo_task.blockSignals(True)
        self.combo_task.clear()
        self.combo_task.addItem("全部")
        self.combo_task.addItems(tasks)
        if current in ["全部", *tasks]:
            self.combo_task.setCurrentText(current)
        self.combo_task.blockSignals(False)

    def _set_module_filter(self, module: str) -> None:
        """Set module filter from combo box or sidebar click."""
        module = module or "全部"
        if module == "全部模块":
            module = "全部"
        self._selected_module = module
        if self.combo_module.currentText() != module and module in [self.combo_module.itemText(i) for i in range(self.combo_module.count())]:
            self.combo_module.blockSignals(True)
            self.combo_module.setCurrentText(module)
            self.combo_module.blockSignals(False)
        self.apply_filters()

    def apply_filters(self) -> None:
        """Apply all visible filters to loaded log entries."""
        rows = []
        filtered = []
        for entry in self._all_entries:
            if not self._entry_matches_filters(entry):
                continue
            filtered.append(entry)
            rows.append(self._entry_to_row(entry))

        self._filtered_entries = filtered
        self.log_table.set_data(rows[:30])
        self.lbl_total.setText(f"筛选结果 {len(filtered):,} 条")
        self.lbl_page.setText("筛选结果")

    def _entry_matches_filters(self, entry: dict[str, Any]) -> bool:
        level_map = {"信息": "INFO", "警告": "WARNING", "错误": "ERROR"}
        level_filter = self.combo_level.currentText()
        if level_filter != "全部" and entry.get("levelname") != level_map.get(level_filter):
            return False

        if self.error_only_btn.isChecked() and entry.get("levelname") != "ERROR":
            return False

        module_filter = self._selected_module if self._selected_module != "全部" else self.combo_module.currentText()
        if module_filter not in ("全部", "全部模块") and not self._module_matches(entry, module_filter):
            return False

        task_filter = self.combo_task.currentText()
        if task_filter != "全部" and self._extract_task(entry) != task_filter:
            return False

        keyword = self.search_box.text().strip().lower()
        if keyword:
            haystack = " ".join(str(part) for part in self._entry_to_row(entry)).lower()
            if keyword not in haystack:
                return False

        return self._matches_time_range(entry)

    def _matches_time_range(self, entry: dict[str, Any]) -> bool:
        value = str(entry.get("asctime", ""))[:10]
        if not value:
            return True
        try:
            log_date = datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return True

        today = datetime.now().date()
        selected = self.combo_time.currentText()
        if selected == "今天":
            return log_date == today
        if selected == "最近 7 天":
            return (today - log_date).days <= 7
        if selected == "最近 30 天":
            return (today - log_date).days <= 30
        return True

    def _module_matches(self, entry: dict[str, Any], module_filter: str) -> bool:
        name = str(entry.get("name", ""))
        message = str(entry.get("message", ""))
        normalized = module_filter.lower().replace(" ", "_")
        if module_filter == "金蝶 API":
            return "kingdee" in name.lower() or "api" in name.lower()
        if module_filter == "SQL Server":
            return "sql" in name.lower() or "mysql" in name.lower()
        if module_filter == "调度服务":
            return "scheduler" in name.lower()
        if module_filter == "数据同步任务":
            return "sync" in name.lower() or "同步" in message
        return normalized in name.lower() or module_filter.lower() in name.lower()

    def _entry_to_row(self, entry: dict[str, Any]) -> list[str]:
        time_str = str(entry.get("asctime", "--"))[:19]
        level = _friendly_level(str(entry.get("levelname", "--")))
        module = _friendly_module(str(entry.get("name", "--")))
        task = self._extract_task(entry)
        message = _friendly_message(str(entry.get("message", "--")))[:120]
        return [time_str, level, module, task, message]

    def _extract_task(self, entry: dict[str, Any]) -> str:
        text = f"{entry.get('name', '')} {entry.get('message', '')}"
        for prefix in ("T_BD_", "T_SAL_", "T_PUR_", "T_INV_"):
            index = text.find(prefix)
            if index >= 0:
                token = text[index:].split()[0].strip("，,。.;；:：")
                return token
        return "--"

    def _current_view_text(self) -> str:
        rows = [self._entry_to_row(entry) for entry in self._filtered_entries]
        lines = ["时间\t级别\t模块\t任务\t消息"]
        lines.extend("\t".join(row) for row in rows)
        return "\n".join(lines)

    def clear_view(self) -> None:
        """Clear only the current table view without deleting log files."""
        self._filtered_entries = []
        self.log_table.clear()
        self.lbl_total.setText("筛选结果 0 条")
        self.lbl_page.setText("筛选结果")

    def copy_logs(self) -> None:
        """Copy current filtered log rows."""
        QApplication.clipboard().setText(self._current_view_text())

    def export_logs(self) -> None:
        """Export current filtered log rows as a local text file."""
        log_dir = _get_log_dir()
        os.makedirs(log_dir, exist_ok=True)
        path = os.path.join(log_dir, f"log_center_export_{datetime.now().strftime('%Y%m%d%H%M%S')}.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(self._current_view_text())
        QApplication.clipboard().setText(path)
