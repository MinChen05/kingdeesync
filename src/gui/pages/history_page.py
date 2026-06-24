"""History page built on the shared Windows 11 page scaffold."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core.history_manager import history_manager
from src.gui.components.common import StatusChip, SvgIconLabel
from src.gui.components.data_table import DataTable
from src.gui.components.page_shell import Win11PageScaffold
from src.gui.design_tokens import ColorTokens, SizeTokens, SpacingTokens
from src.gui.feedback import UiFeedback
from src.gui.pages._history_filter_panel import HistoryFilterPanel
from src.gui.pages._history_pagination_card import HistoryPaginationCard
from src.gui.ui_text import ButtonText

logger = logging.getLogger(__name__)


def _set_label_color(label: QLabel, color: str) -> None:
    palette = label.palette()
    palette.setColor(QPalette.WindowText, QColor(color))
    label.setPalette(palette)


def _set_font(label: QLabel, point_size: int, bold: bool = False) -> None:
    font = label.font()
    font.setPointSize(point_size)
    font.setBold(bold)
    label.setFont(font)


def _format_count(value) -> str:
    if value in (None, ""):
        return "--"
    try:
        return f"{int(float(value)):,}"
    except (TypeError, ValueError):
        return str(value)


def _format_seconds(value) -> str:
    if value in (None, ""):
        return "--"
    text = str(value).strip().lower()
    try:
        seconds = float(text[:-1] if text.endswith("s") else text)
    except ValueError:
        return str(value)
    return str(int(round(seconds)))


def _format_clock(value) -> str:
    seconds_text = _format_seconds(value)
    if seconds_text == "--":
        return "--"
    seconds = int(seconds_text)
    hours, rem = divmod(seconds, 3600)
    minutes, sec = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{sec:02d}"


def _format_rate(value) -> str:
    if value in (None, ""):
        return "--"
    raw = str(value).strip()
    if raw.endswith("%"):
        return raw
    try:
        return f"{float(raw):.2f}%"
    except ValueError:
        return raw


def _format_trend_html(text: str | None) -> str:
    raw = (text or "--").strip()
    if raw in {"", "--", "较昨日 --"}:
        return f'<span style="color:{ColorTokens.NEUTRAL_500};">较昨日 --</span>'
    tone = ColorTokens.SUCCESS_GREEN if ("↑" in raw or "↓" in raw) else ColorTokens.NEUTRAL_500
    if " " in raw:
        prefix, suffix = raw.split(" ", 1)
        return f'<span style="color:{ColorTokens.NEUTRAL_500};">{prefix} </span><span style="color:{tone};">{suffix}</span>'
    return f'<span style="color:{tone};">{raw}</span>'


class HistoryMetricIcon(QWidget):
    """Small painter icon used by history metric cards."""

    def __init__(self, icon_type: str, color: str, parent=None) -> None:
        super().__init__(parent)
        self.icon_type = icon_type
        self.color = QColor(color)
        self.setFixedSize(58, 58)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        bg = QColor(self.color)
        bg.setAlpha(34)
        painter.setBrush(bg)
        painter.drawEllipse(self.rect().adjusted(2, 2, -2, -2))

        pen = QPen(self.color, 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        rect = self.rect()
        cx = rect.center().x()
        cy = rect.center().y()
        if self.icon_type == "clock":
            painter.drawEllipse(cx - 16, cy - 16, 32, 32)
            painter.drawLine(cx, cy, cx, cy - 13)
            painter.drawLine(cx, cy, cx + 10, cy + 6)
        elif self.icon_type == "cross":
            painter.drawEllipse(cx - 15, cy - 15, 30, 30)
            painter.drawLine(cx - 7, cy - 7, cx + 7, cy + 7)
            painter.drawLine(cx + 7, cy - 7, cx - 7, cy + 7)
        elif self.icon_type == "database":
            painter.drawEllipse(cx - 14, cy - 18, 28, 10)
            painter.drawLine(cx - 14, cy - 13, cx - 14, cy + 13)
            painter.drawLine(cx + 14, cy - 13, cx + 14, cy + 13)
            painter.drawArc(cx - 14, cy - 2, 28, 10, 180 * 16, 180 * 16)
            painter.drawArc(cx - 14, cy + 8, 28, 10, 180 * 16, 180 * 16)
        else:
            painter.drawRoundedRect(cx - 12, cy - 17, 24, 34, 2, 2)
            painter.drawLine(cx - 7, cy - 5, cx + 7, cy - 5)
            painter.drawLine(cx - 7, cy + 3, cx + 7, cy + 3)
            painter.drawLine(cx - 7, cy + 11, cx + 3, cy + 11)
        painter.end()


_HISTORY_METRIC_ICONS = {
    "clock": "summary_clock.svg",
    "cross": "summary_fail.svg",
    "database": "summary_rows.svg",
    "document": "summary_document.svg",
}


class HistoryDonut(QWidget):
    """Simple donut chart for success rate composition."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.success = 0
        self.failed = 0
        self.not_run = 0
        self.center_text = "--"
        self.setFixedSize(112, 112)

    def set_data(self, success: int, failed: int, not_run: int) -> None:
        self.success = max(0, int(success or 0))
        self.failed = max(0, int(failed or 0))
        self.not_run = max(0, int(not_run or 0))
        self.update()

    def set_center_text(self, text: str) -> None:
        self.center_text = text or "--"
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        total = self.success + self.failed + self.not_run
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(10, 10, -10, -10)
        start = 90 * 16
        values = [
            (self.success, ColorTokens.SUCCESS_GREEN),
            (self.failed, ColorTokens.DANGER),
            (self.not_run, ColorTokens.NEUTRAL_200),
        ]
        if total <= 0:
            values = [(1, ColorTokens.NEUTRAL_200)]
            total = 1
        pen = QPen()
        pen.setWidth(16)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        for value, color in values:
            span = int(-360 * 16 * (value / total))
            pen.setColor(QColor(color))
            painter.setPen(pen)
            painter.drawArc(rect, start, span)
            start += span
        painter.setPen(QColor(ColorTokens.NEUTRAL_900))
        font = painter.font()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.center_text)
        painter.end()


class HistoryRateCard(QFrame):
    """Visual success rate summary card."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("ui", "history-summary-card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(184)
        root = QVBoxLayout(self)
        root.setContentsMargins(SpacingTokens.LG, SpacingTokens.XL, SpacingTokens.LG, SpacingTokens.LG)
        root.setSpacing(SpacingTokens.LG)

        self.title_label = QLabel("成功率")
        self.title_label.setProperty("ui", "history-summary-title")
        _set_font(self.title_label, 13, True)
        root.addWidget(self.title_label)

        body = QHBoxLayout()
        body.setSpacing(SpacingTokens.MD)
        self.donut = HistoryDonut()
        body.addWidget(self.donut)

        text_col = QVBoxLayout()
        text_col.setSpacing(SpacingTokens.SM)
        self.value_label = QLabel("--")
        _set_font(self.value_label, 16, True)
        self.value_label.setVisible(False)
        text_col.addWidget(self.value_label)
        self.detail_label = QLabel("成功 --\n失败 --\n未运行 --")
        self.detail_label.setProperty("ui", "win11-helper-text")
        self.detail_label.setVisible(False)
        text_col.addWidget(self.detail_label)
        self.legend_rows = [
            self._make_legend_row("成功", "success"),
            self._make_legend_row("失败", "danger"),
            self._make_legend_row("未运行", "neutral"),
        ]
        for _, _value_label, row in self.legend_rows:
            text_col.addWidget(row)
        text_col.addStretch(1)
        body.addLayout(text_col, 1)
        root.addLayout(body)

    @staticmethod
    def _make_legend_row(label_text: str, tone: str):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        layout.setSpacing(SpacingTokens.SM)
        dot = QLabel()
        dot.setProperty("ui", "history-rate-dot")
        dot.setProperty("tone", tone)
        dot.setFixedSize(9, 9)
        name = QLabel(label_text)
        name.setProperty("ui", "history-rate-name")
        value = QLabel("--")
        value.setProperty("ui", "history-rate-value")
        layout.addWidget(dot)
        layout.addWidget(name)
        layout.addStretch(1)
        layout.addWidget(value)
        return label_text, value, row

    def set_data(self, rate: str, success: int = 0, failed: int = 0, not_run: int = 0) -> None:
        rate_text = _format_rate(rate)
        self.value_label.setText(rate_text)
        self.donut.set_center_text(rate_text)
        self.donut.set_data(success, failed, not_run)
        self.detail_label.setText(
            f"成功 {_format_count(success)}\n失败 {_format_count(failed)}\n未运行 {_format_count(not_run)}"
        )
        total = max(1, int(success or 0) + int(failed or 0) + int(not_run or 0))
        values = (success, failed, not_run)
        for (_, value_label, _), count in zip(self.legend_rows, values, strict=False):
            percent = (int(count or 0) / total) * 100
            value_label.setText(f"{percent:.2f}%\n({_format_count(count)})")


class HistoryMetricCard(QFrame):
    """Visual metric card with icon, value and trend text."""

    def __init__(self, title: str, icon_type: str, icon_color: str, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("ui", "history-summary-card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(184)
        root = QVBoxLayout(self)
        root.setContentsMargins(SpacingTokens.LG, SpacingTokens.XL, SpacingTokens.LG, SpacingTokens.LG)
        root.setSpacing(SpacingTokens.LG)

        self.title_label = QLabel(title)
        self.title_label.setProperty("ui", "history-summary-title")
        _set_font(self.title_label, 13, True)
        root.addWidget(self.title_label)

        body = QHBoxLayout()
        body.setSpacing(SpacingTokens.MD)
        icon = SvgIconLabel(
            _HISTORY_METRIC_ICONS.get(icon_type, "summary_document.svg"),
            size=60,
            icon_size=31,
            color=icon_color,
        )
        icon.setProperty("ui", "history-summary-icon")
        icon.setProperty("tone", icon_type)
        body.addWidget(icon)
        self.value_label = QLabel("--")
        self.value_label.setProperty("ui", "history-summary-value")
        _set_font(self.value_label, 21, True)
        self.value_label.setMinimumWidth(96)
        self.value_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        body.addWidget(self.value_label, 1)
        root.addLayout(body)

        self.subtitle_label = QLabel("--")
        self.subtitle_label.setProperty("ui", "history-summary-trend")
        self.subtitle_label.setTextFormat(Qt.TextFormat.RichText)
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        root.addWidget(self.subtitle_label)

    def set_data(self, value: str, subtitle: str | None = None) -> None:
        self.value_label.setText(value or "--")
        self.subtitle_label.setText(_format_trend_html(subtitle))


class HistoryStatusMark(QWidget):
    """Painter mark used inside status tags."""

    def __init__(self, tone: str, parent=None) -> None:
        super().__init__(parent)
        self.tone = tone
        self.setFixedSize(12, 12)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        color_map = {
            "success": ColorTokens.SUCCESS_GREEN,
            "danger": ColorTokens.DANGER,
            "warning": ColorTokens.WARNING,
            "info": ColorTokens.ACCENT_600,
        }
        color = QColor(color_map.get(self.tone, ColorTokens.NEUTRAL_400))
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        rect = self.rect().adjusted(2, 2, -2, -2)
        if self.tone == "warning":
            path = QPainterPath()
            path.moveTo(rect.center().x(), rect.top())
            path.lineTo(rect.right(), rect.bottom())
            path.lineTo(rect.left(), rect.bottom())
            path.closeSubpath()
            painter.drawPath(path)
        else:
            painter.drawEllipse(rect)
        pen = QPen(QColor(Qt.GlobalColor.white), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        if self.tone == "success":
            painter.drawLine(4, 6, 6, 8)
            painter.drawLine(6, 8, 9, 4)
        elif self.tone == "danger":
            painter.drawLine(4, 4, 8, 8)
            painter.drawLine(8, 4, 4, 8)
        elif self.tone == "warning":
            painter.drawLine(6, 4, 6, 7)
            painter.drawPoint(6, 9)
        painter.end()


class HistoryStatusTag(QWidget):
    """Status display matching target table: mark + text."""

    def __init__(self, text: str, tone: str, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("tone", tone)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        layout.setSpacing(SpacingTokens.XS)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mark = HistoryStatusMark(tone)
        layout.addWidget(self.mark)
        self.label = QLabel(text)
        _set_font(self.label, 12, True)
        color_map = {
            "success": ColorTokens.SUCCESS_GREEN,
            "danger": ColorTokens.DANGER,
            "warning": ColorTokens.WARNING,
            "info": ColorTokens.ACCENT_600,
        }
        _set_label_color(self.label, color_map.get(tone, ColorTokens.NEUTRAL_500))
        layout.addWidget(self.label)


HistorySummaryCard = HistoryMetricCard


class HistoryPage(Win11PageScaffold):
    """Filterable history table for past sync activity."""

    def __init__(self, parent_gui, parent=None):
        self.gui = parent_gui
        self.current_page = 1
        self.page_size = 10
        self.total_records = 0
        self.current_records: list[dict] = []

        super().__init__(
            title="同步历史",
            eyebrow="同步历史",
            subtitle="查看过往同步执行记录，按条件筛选并分页浏览，支持导出当前结果视图。",
            parent=parent,
        )
        self.setProperty("page", "history")

        self.setup_ui()
        self.load_history(1)

    def setup_ui(self) -> None:
        self._init_filters()
        self._build_hero()
        self._build_summary_strip()
        self.hero_card.setVisible(False)
        self.primary_action_host.setVisible(False)
        self.summary_strip.setVisible(False)
        self.set_content(self._create_content())

    def _init_filters(self) -> None:
        self._filter_panel = HistoryFilterPanel(on_query=lambda: self.load_history(1), on_reset=self.reset_filters)
        self.search_box = self._filter_panel.search_box
        self.combo_time_range = self._filter_panel.combo_time_range
        self.combo_status = self._filter_panel.combo_status
        self.combo_type = self._filter_panel.combo_type
        self.btn_query = self._filter_panel.btn_query
        self.btn_reset = self._filter_panel.btn_reset

    def _build_hero(self) -> None:
        self.hero_badge = StatusChip("历史浏览", tone="info")

        self.summary_hint = QLabel("当前筛选条件下共有 0 条记录。")
        self.summary_hint.setProperty("ui", "win11-meta-text")
        self.summary_hint.setWordWrap(True)

        self.page_title = QLabel("同步历史")
        self.page_title.setProperty("ui", "history-page-title")
        _set_font(self.page_title, 20, True)

        self.btn_export = QPushButton(ButtonText.EXPORT)
        self.btn_export.setProperty("class", "secondary")
        self.btn_export.setObjectName("history_export_btn")
        self.btn_export.setProperty("icon-source", "export.svg")
        self.btn_export.setIcon(QIcon(str(SvgIconLabel._ASSETS_DIR / "icons" / "export.svg")))
        self.btn_export.setIconSize(QSize(15, 15))
        self.btn_export.setFixedSize(SizeTokens.HISTORY_EXPORT_BUTTON_WIDTH, SizeTokens.HISTORY_EXPORT_BUTTON_HEIGHT)
        self.btn_export.clicked.connect(self.export_data)

    def _build_summary_strip(self) -> None:
        self.card_rate = HistoryRateCard()
        self.card_duration = HistoryMetricCard("平均耗时", "clock", ColorTokens.ACCENT_600)
        self.card_fail = HistoryMetricCard("失败数量", "cross", ColorTokens.DANGER)
        self.card_rows = HistoryMetricCard("写入行数（总计）", "database", ColorTokens.SUCCESS_GREEN)
        self.card_updates = HistoryMetricCard("数据更新（总计）", "document", ColorTokens.WARNING)

    def _create_content(self) -> QWidget:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        layout.setSpacing(SpacingTokens.WORKSPACE_COLUMN_GAP)

        title_row = QWidget()
        title_layout = QHBoxLayout(title_row)
        title_layout.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        title_layout.setSpacing(SpacingTokens.MD)
        title_row.setFixedHeight(40)
        title_layout.addWidget(self.page_title)
        title_layout.addStretch(1)
        title_layout.addWidget(self.btn_export)

        summary_grid = QWidget()
        summary_layout = QGridLayout(summary_grid)
        summary_layout.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        summary_layout.setHorizontalSpacing(SpacingTokens.SM)
        summary_layout.setVerticalSpacing(SpacingTokens.SM)
        cards = (self.card_rate, self.card_duration, self.card_fail, self.card_rows, self.card_updates)
        for index, card in enumerate(cards):
            summary_layout.addWidget(card, 0, index)
            summary_layout.setColumnStretch(index, 1)

        layout.addWidget(title_row)
        layout.addWidget(self._filter_panel)
        layout.addWidget(summary_grid)
        layout.addWidget(self._create_table_card(), 1)
        return root

    def _create_table_card(self) -> QFrame:
        card = QFrame()
        card.setProperty("ui", "history-table-card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(SpacingTokens.XL, SpacingTokens.LG, SpacingTokens.XL, SpacingTokens.MD)
        layout.setSpacing(SpacingTokens.XS)

        self._data_table = DataTable(
            ["开始时间 ↓", "任务名称", "表单", "状态", "写入行数", "耗时（秒）", "数据原因"],
        )
        self._data_table.set_empty_text("当前筛选条件下没有匹配的历史记录。")
        self.table = self._data_table.table
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 170)
        self.table.setColumnWidth(1, 210)
        self.table.setColumnWidth(2, 185)
        self.table.setColumnWidth(3, 112)
        self.table.setColumnWidth(4, 112)
        self.table.setColumnWidth(5, 116)
        self.table.verticalHeader().setDefaultSectionSize(SizeTokens.HISTORY_TABLE_ROW_HEIGHT)
        self.table.horizontalHeader().setFixedHeight(SizeTokens.HISTORY_TABLE_HEADER_HEIGHT)
        layout.addWidget(self._data_table, 1)
        layout.addWidget(self._create_pagination_card())
        return card

    def _create_pagination_card(self) -> QFrame:
        self._pagination_card = HistoryPaginationCard(
            on_prev=self.prev_page,
            on_next=self.next_page,
            on_jump=lambda page: self.load_history(page),
        )
        self._pagination_card.page_size_combo.setCurrentIndex(0)
        self._pagination_card.page_size_combo.currentIndexChanged.connect(self._handle_page_size_changed)
        # Alias properties for backward compatibility with existing tests/code
        self.btn_prev = self._pagination_card.btn_prev
        self.btn_next = self._pagination_card.btn_next
        self.lbl_curr_page = self._pagination_card.lbl_curr_page
        self.jump_box = self._pagination_card.jump_box
        self.lbl_page_info = self._pagination_card.lbl_page_info
        return self._pagination_card

    def load_history(self, page=None) -> None:
        if page:
            self.current_page = page

        self.lbl_curr_page.setText(str(self.current_page))
        self.jump_box.setValue(self.current_page)

        days = int(self.combo_time_range.currentData() or 0)
        today = datetime.now()
        start_anchor = today - timedelta(days=days)
        start_date = start_anchor.strftime("%Y-%m-%d") + " 00:00:00"
        end_date = today.strftime("%Y-%m-%d") + " 23:59:59"

        status = self.combo_status.currentData()
        sync_type = self.combo_type.currentData()
        form_name = self.search_box.text().strip()

        try:
            records, total = history_manager.get_history(
                page=self.current_page,
                page_size=self.page_size,
                start_date=start_date,
                end_date=end_date,
                status=status,
                sync_type=sync_type,
                form_name=form_name if form_name else None,
            )
            self.total_records = total
            self.current_records = records
            self.summary_hint.setText(f"当前筛选条件下共有 {total} 条记录。")
            self.update_table(records)
            self.update_pagination()

            stats = history_manager.get_stats()
            fail_count = stats.get("fail_count", stats.get("today_fail_count", 0))
            success_count = stats.get("success_count", stats.get("today_success_count", 0))
            not_run_count = stats.get("not_run_count", stats.get("pending_count", 0))
            self.card_rate.set_data(
                stats.get("today_success_rate", "0%"),
                success_count,
                fail_count,
                not_run_count,
            )
            self.card_duration.set_data(
                _format_clock(stats.get("avg_duration", "0s")),
                stats.get("duration_delta", "较昨日 --"),
            )
            self.card_fail.set_data(_format_count(fail_count), stats.get("fail_delta", "较昨日 --"))
            total_written = stats.get("total_records_synced", stats.get("total_inserted", "--"))
            total_updated = stats.get("total_updated", "--")
            self.card_rows.set_data(_format_count(total_written), stats.get("rows_delta", "较昨日 --"))
            self.card_updates.set_data(_format_count(total_updated), stats.get("updates_delta", "较昨日 --"))
        except Exception as exc:
            logger.error("加载历史记录失败：%s", exc)
            UiFeedback.error(self, "加载失败", f"无法加载同步历史记录：\n{exc}")
            self.total_records = 0
            self.current_records = []
            self._data_table.clear()
            self.summary_hint.setText("当前筛选条件下共有 0 条记录。")
            self.update_pagination()

    def update_table(self, records) -> None:
        if not records:
            self._data_table.set_data([])
            return

        rows = []
        for row_data in records:
            task_name = (
                row_data.get("task_name")
                or row_data.get("name")
                or row_data.get("sync_type", "")
                or row_data.get("operation", "")
                or row_data.get("form_name", "")
            )
            rows.append([
                str(row_data.get("start_time_str") or row_data.get("start_time", "")),
                str(task_name),
                str(row_data.get("form_name") or row_data.get("table_name", "")),
                "",
                _format_count(row_data.get("record_count", row_data.get("records_synced", 0) or 0)),
                _format_seconds(row_data.get("duration_seconds", row_data.get("duration", 0))),
                str(row_data.get("message", ""))[:40] or "-",
            ])
        self._data_table.set_data(rows)

        for row_index, row_data in enumerate(records):
            item = self.table.item(row_index, 4)
            if item is not None:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item = self.table.item(row_index, 5)
            if item is not None:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_text, tone = self._get_status_display(row_data.get("status"))
            self.table.setCellWidget(row_index, 3, self._build_tag(status_text, tone))

    def _build_tag(self, text: str, tone: str) -> QWidget:
        return HistoryStatusTag(text, tone)

    def _get_status_display(self, status: str | None):
        if status == "success":
            return "成功", "success"
        if status == "partial":
            return "警告", "warning"
        if status == "failed":
            return "失败", "danger"
        if status == "failed_abnormal_exit":
            return "失败", "danger"
        return str(status or "--"), "info"

    def update_pagination(self) -> None:
        self._pagination_card.update_state(self.current_page, self.total_records, self.page_size)

    def reset_filters(self) -> None:
        self._filter_panel.reset_filters()
        self.load_history(1)

    def _handle_page_size_changed(self, *_args) -> None:
        self.page_size = int(self._pagination_card.page_size_combo.currentData() or 10)
        self.load_history(1)

    def apply_quick_filter(self, days: int = 7, status: str | None = None, form_name: str | None = None) -> None:
        """Apply a quick filter when jumping from another page."""
        self._filter_panel.set_quick_filter(days, status, form_name)
        self.load_history(1)

    def prev_page(self) -> None:
        if self.current_page > 1:
            self.load_history(self.current_page - 1)

    def next_page(self) -> None:
        total_pages = max(1, (self.total_records + self.page_size - 1) // self.page_size)
        if self.current_page < total_pages:
            self.load_history(self.current_page + 1)

    def export_data(self) -> None:
        try:
            if not self.current_records:
                UiFeedback.info(self, "暂无可导出内容", "当前视图没有可导出的历史记录。")
                return

            content = []
            for row_index in range(self.table.rowCount()):
                row_data = []
                for col_index in range(self.table.columnCount()):
                    if col_index == 3:
                        widget = self.table.cellWidget(row_index, col_index)
                        if isinstance(widget, HistoryStatusTag):
                            row_data.append(widget.label.text())
                        elif widget and widget.layout() and widget.layout().count():
                            child = widget.layout().itemAt(0).widget()
                            row_data.append(child.text() if hasattr(child, "text") else "")
                        else:
                            row_data.append("")
                    else:
                        item = self.table.item(row_index, col_index)
                        row_data.append(item.text() if item else "")
                content.append("\t".join(row_data))

            QApplication.clipboard().setText("\n".join(content))
            UiFeedback.success(self, "导出成功", "历史数据已复制到剪贴板。")
        except Exception as exc:
            UiFeedback.error(self, "导出失败", f"无法导出历史数据：\n{exc}")
