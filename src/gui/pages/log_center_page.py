"""Sync monitoring page — real-time sync run records with filtering and metrics."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.history_manager import history_manager
from src.gui.components.common import SvgIconLabel
from src.gui.components.data_table import DataTable
from src.gui.components.page_shell import Win11PageScaffold
from src.gui.design_tokens import ColorTokens, SizeTokens, SpacingTokens
from src.gui.feedback import UiFeedback

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _status_display(status: str) -> tuple[str, str, str]:
    """Map sync status to (display_text, tone, icon_color)."""
    s = (status or "").strip().lower()
    if s in ("success", "completed", "done"):
        return "成功", "success", ColorTokens.SUCCESS_GREEN
    if s in ("failed", "failure", "error", "failed_abnormal_exit"):
        return "失败", "danger", ColorTokens.DANGER
    if s in ("partial", "partial_success"):
        return "部分成功", "warning", ColorTokens.WARNING
    if s in ("running", "in_progress", "processing"):
        return "运行中", "info", ColorTokens.ACCENT_600
    if s in ("pending", "queued", "waiting"):
        return "等待中", "info", ColorTokens.ACCENT_600
    if s in ("paused", "paused_by_user"):
        return "已暂停", "warning", ColorTokens.WARNING
    return str(status or "--"), "idle", ColorTokens.NEUTRAL_400


def _format_count(value: Any) -> str:
    try:
        n = int(value)
        if n >= 10000:
            return f"{n:,}"
        return str(n)
    except (TypeError, ValueError):
        return str(value or "0")


def _format_duration(value: Any) -> str:
    try:
        secs = float(value or 0)
        if secs < 60:
            return f"{int(secs)} 秒"
        minutes = int(secs // 60)
        seconds = int(secs % 60)
        return f"{minutes} 分 {seconds} 秒"
    except (TypeError, ValueError):
        return str(value or "--")


def _format_duration_compact(value: Any) -> str:
    try:
        secs = float(value or 0)
        if secs < 60:
            return f"{int(secs)}s"
        return f"{int(secs // 60)}m{int(secs % 60)}s"
    except (TypeError, ValueError):
        return "--"


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

class LogCenterPage(Win11PageScaffold):
    """Real-time sync monitoring page with metrics, filtering, and detail table."""

    _COLUMNS = ["开始时间", "同步类型", "表单", "状态", "写入行数", "耗时"]

    def __init__(self, parent_gui, parent=None):
        self.gui = parent_gui
        self._all_records: list[dict[str, Any]] = []
        self._total_count = 0
        self._current_page = 1
        self._page_size = 20

        super().__init__(
            title="同步监控",
            eyebrow="",
            subtitle="实时查看同步任务执行状态、结果和统计",
            parent=parent,
        )
        self.setProperty("page", "log-center")
        self.set_hero_visible(False)
        self.hero_card.setVisible(False)
        self.primary_action_host.setVisible(False)
        self.summary_strip.setVisible(False)
        self._build_ui()
        self._load_data()

    # -- UI Build ---------------------------------------------------------------

    def _build_ui(self) -> None:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # ---- Metric cards row ----
        layout.addWidget(self._build_metric_cards())

        # ---- Filter bar ----
        layout.addWidget(self._build_filter_bar())

        # ---- Detail table ----
        layout.addWidget(self._build_table_area(), 1)

        # ---- Pagination bar ----
        layout.addWidget(self._build_pagination_bar())

        self.set_content(content)

    def _build_metric_cards(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._stat_cards: dict[str, QWidget] = {}
        stat_defs = [
            ("今日同步", "0", "total", ColorTokens.ACCENT_600, "sync_record.svg"),
            ("成功", "0", "success", ColorTokens.SUCCESS_GREEN, "sync_result.svg"),
            ("失败", "0", "failed", ColorTokens.DANGER, "sync_status.svg"),
            ("成功率", "0%", "rate", ColorTokens.ACCENT_600, "sync_progress.svg"),
            ("平均耗时", "--", "avg_dur", ColorTokens.INFO, "sync_runtime.svg"),
        ]
        for title, default_val, key, color, icon_file in stat_defs:
            card = self._create_stat_card(title, default_val, color, icon_file)
            self._stat_cards[key] = card
            layout.addWidget(card)
        return row

    def _create_stat_card(self, title: str, value: str, color: str, icon_file: str) -> QWidget:
        card = QFrame()
        card.setProperty("ui", "sync-stat-card")
        card.setMinimumWidth(140)

        inner = QVBoxLayout(card)
        inner.setContentsMargins(12, 10, 12, 10)
        inner.setSpacing(4)

        icon = SvgIconLabel(icon_file, size=32, icon_size=20, color=color)
        icon.setProperty("ui", "sync-stat-icon")
        inner.addWidget(icon)

        title_lbl = QLabel(title)
        title_lbl.setProperty("ui", "sync-stat-title")
        inner.addWidget(title_lbl)

        value_lbl = QLabel(value)
        value_lbl.setProperty("ui", "sync-stat-value")
        inner.addWidget(value_lbl)

        card._value_label = value_lbl
        return card

    def _build_filter_bar(self) -> QFrame:
        bar = QFrame()
        bar.setProperty("ui", "sync-filter-bar")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)

        # Time range
        time_label = QLabel("时间范围")
        time_label.setProperty("ui", "sync-filter-label")
        layout.addWidget(time_label)

        self.combo_time = QComboBox()
        self.combo_time.addItems(["今天", "最近 7 天", "最近 30 天", "全部"])
        self.combo_time.setFixedHeight(32)
        self.combo_time.setMinimumWidth(120)
        self.combo_time.currentTextChanged.connect(lambda _t: self._on_filter_changed())
        layout.addWidget(self.combo_time)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFixedHeight(20)
        layout.addWidget(sep)

        # Status filter
        status_label = QLabel("状态")
        status_label.setProperty("ui", "sync-filter-label")
        layout.addWidget(status_label)

        self.combo_status = QComboBox()
        self.combo_status.addItems(["全部状态", "成功", "失败", "运行中", "部分成功", "已暂停"])
        self.combo_status.setFixedHeight(32)
        self.combo_status.setMinimumWidth(100)
        self.combo_status.currentTextChanged.connect(lambda _t: self._on_filter_changed())
        layout.addWidget(self.combo_status)

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setFixedHeight(20)
        layout.addWidget(sep2)

        # Search
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索任务名称、表单或错误摘要...")
        self.search_box.setFixedHeight(32)
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setMinimumWidth(240)
        self.search_box.returnPressed.connect(self._on_filter_changed)
        self.search_box.editingFinished.connect(self._on_filter_changed)
        layout.addWidget(self.search_box, 1)

        # Refresh button
        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.setProperty("class", "primary")
        self.btn_refresh.setFixedHeight(34)
        self.btn_refresh.setFixedWidth(80)
        self.btn_refresh.clicked.connect(self._load_data)
        layout.addWidget(self.btn_refresh)

        return bar

    def _build_table_area(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sync_table = DataTable(self._COLUMNS)
        self.sync_table.set_empty_text("暂无同步记录")
        self.sync_table.setMinimumHeight(200)
        layout.addWidget(self.sync_table, 1)

        return container

    def _build_pagination_bar(self) -> QFrame:
        bar = QFrame()
        bar.setProperty("ui", "sync-pagination-bar")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(12)

        self.lbl_total = QLabel("共 0 条")
        self.lbl_total.setProperty("ui", "sync-pagination-text")
        layout.addWidget(self.lbl_total)

        layout.addStretch()

        self.btn_prev = QPushButton("←")
        self.btn_prev.setFixedWidth(40)
        self.btn_prev.setFixedHeight(30)
        self.btn_prev.setEnabled(False)
        self.btn_prev.clicked.connect(self._go_prev_page)
        layout.addWidget(self.btn_prev)

        self.page_buttons: list[QPushButton] = []
        self._page_btn_group = QHBoxLayout()
        self._page_btn_group.setSpacing(4)
        layout.addLayout(self._page_btn_group)

        self.btn_next = QPushButton("→")
        self.btn_next.setFixedWidth(40)
        self.btn_next.setFixedHeight(30)
        self.btn_next.setEnabled(False)
        self.btn_next.clicked.connect(self._go_next_page)
        layout.addWidget(self.btn_next)

        layout.addStretch()

        self.lbl_page = QLabel("1/1 页")
        self.lbl_page.setProperty("ui", "sync-pagination-text")
        layout.addWidget(self.lbl_page)

        return bar

    # -- Data Loading -----------------------------------------------------------

    def _load_data(self) -> None:
        """Load sync run records from history_manager."""
        try:
            start_date, end_date = self._resolve_time_range()
            status_map = {
                "成功": "success",
                "失败": "failed",
                "运行中": "running",
                "部分成功": "partial",
                "已暂停": "paused",
            }
            status_raw = self.combo_status.currentText() if hasattr(self, "combo_status") else "全部状态"
            status_filter = status_map.get(status_raw)

            records, total = history_manager.get_history(
                page=self._current_page,
                page_size=self._page_size,
                start_date=start_date,
                end_date=end_date,
                status=status_filter,
            )
            self._all_records = records
            self._total_count = total
        except Exception as exc:
            logger.warning("Failed to load sync records: %s", exc)
            self._all_records = []
            self._total_count = 0

        self._update_table()
        self._update_pagination()
        self._update_metrics()

    def _resolve_time_range(self) -> tuple:
        """Return (start_datetime_or_None, end_datetime_or_None)."""
        today = datetime.now()
        text = self.combo_time.currentText() if hasattr(self, "combo_time") else "今天"
        if text == "今天":
            return today.replace(hour=0, minute=0, second=0, microsecond=0), None
        if text == "最近 7 天":
            return today - timedelta(days=7), None
        if text == "最近 30 天":
            return today - timedelta(days=30), None
        return None, None

    def _update_table(self) -> None:
        """Render loaded records into the DataTable."""
        rows = []
        for rec in self._all_records:
            status_text, _, _ = _status_display(rec.get("status", ""))
            rows.append([
                str(rec.get("start_time_str", rec.get("start_time", "--")))[:19],
                str(rec.get("sync_type", "--")),
                str(rec.get("form_name", rec.get("forms_summary", "--"))),
                status_text,
                _format_count(rec.get("total_records", rec.get("record_count", 0))),
                _format_duration_compact(rec.get("duration_seconds", 0)),
            ])

        # Apply keyword filter client-side if search box has text
        keyword = self.search_box.text().strip().lower() if hasattr(self, "search_box") else ""
        if keyword:
            rows = [r for r in rows if keyword in " ".join(r).lower()]

        self.sync_table.set_data(rows)

    def _update_metrics(self) -> None:
        """Update metric cards from loaded records."""
        try:
            stats = history_manager.get_stats()
        except Exception as exc:
            logger.warning("Failed to load stats: %s", exc)
            stats = {}

        total = self._total_count
        success_count = sum(1 for r in self._all_records if str(r.get("status", "")).lower() in ("success", "completed"))
        fail_count = sum(1 for r in self._all_records if str(r.get("status", "")).lower() in ("failed", "failure", "error", "failed_abnormal_exit"))

        rate = stats.get("today_success_rate", "0%")
        avg_dur = stats.get("avg_duration", "--")

        for key, val in [
            ("total", str(total)),
            ("success", str(success_count)),
            ("failed", str(fail_count)),
            ("rate", rate),
            ("avg_dur", avg_dur),
        ]:
            card = self._stat_cards.get(key)
            if card is not None:
                card._value_label.setText(val)

    def _update_pagination(self) -> None:
        """Rebuild pagination buttons and update labels."""
        total_pages = max(1, (self._total_count + self._page_size - 1) // self._page_size)
        self.lbl_total.setText(f"共 {self._total_count:,} 条")
        self.lbl_page.setText(f"{self._current_page}/{total_pages} 页")

        self.btn_prev.setEnabled(self._current_page > 1)
        self.btn_next.setEnabled(self._current_page < total_pages)

        # Clear old page buttons
        for btn in self.page_buttons:
            self._page_btn_group.removeWidget(btn)
            btn.deleteLater()
        self.page_buttons.clear()

        # Show at most 7 page numbers
        start = max(1, self._current_page - 3)
        end = min(total_pages, start + 6)
        if end - start < 6:
            start = max(1, end - 6)

        for p in range(start, end + 1):
            btn = QPushButton(str(p))
            btn.setFixedWidth(36)
            btn.setFixedHeight(30)
            btn.setProperty("class", "page-btn")
            btn.setCheckable(True)
            btn.setChecked(p == self._current_page)
            btn.clicked.connect(lambda _checked=False, page=p: self._go_page(page))
            self._page_btn_group.addWidget(btn)
            self.page_buttons.append(btn)

    # -- Filter / Navigation ----------------------------------------------------

    def _on_filter_changed(self) -> None:
        self._current_page = 1
        self._load_data()

    def _go_prev_page(self) -> None:
        if self._current_page > 1:
            self._current_page -= 1
            self._load_data()

    def _go_next_page(self) -> None:
        total_pages = max(1, (self._total_count + self._page_size - 1) // self._page_size)
        if self._current_page < total_pages:
            self._current_page += 1
            self._load_data()

    def _go_page(self, page: int) -> None:
        self._current_page = page
        self._load_data()
