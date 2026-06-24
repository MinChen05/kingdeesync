"""History page filter panel component."""

from __future__ import annotations

from time import monotonic
from typing import Callable

from PySide6.QtWidgets import QComboBox, QGridLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from src.gui.components.page_shell import Win11SectionCard
from src.gui.design_tokens import SizeTokens, SpacingTokens
from src.gui.ui_text import ButtonText


class HistoryFilterPanel(Win11SectionCard):
    """Filter controls for the history page.

    Encapsulates search box, time range, status, and type combos.
    Handles responsive 2x2 / 1x4 layout internally.
    Does NOT call any service; page reads values via properties.
    """

    def __init__(
        self,
        on_query: Callable[[], None] | None = None,
        on_reset: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(
            "",
            "",
        )
        self.setProperty("ui", "history-filter-bar")
        self.title_label.setVisible(False)
        self.subtitle_label.setVisible(False)
        self._on_query = on_query
        self._on_reset = on_reset
        self._last_auto_query_at = 0.0
        self._suppress_auto_query = False

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("请输入任务名称")
        self.search_box.setProperty("td", "win11-input")
        self.search_box.setFixedHeight(SizeTokens.CONTROL_HEIGHT)
        self.search_box.setMinimumWidth(SizeTokens.HISTORY_FILTER_SEARCH_MIN_WIDTH)
        if self._on_query:
            self.search_box.returnPressed.connect(self._emit_query_once)
            self.search_box.editingFinished.connect(self._emit_query_once)

        self.combo_time_range = QComboBox()
        self.combo_time_range.setProperty("td", "win11-input")
        self.combo_time_range.setFixedSize(SizeTokens.HISTORY_FILTER_TIME_WIDTH, SizeTokens.CONTROL_HEIGHT)
        self.combo_time_range.addItem("开始日期  ~  结束日期", 0)
        self.combo_time_range.addItem("近 7 天", 7)
        self.combo_time_range.addItem("近 30 天", 30)
        if self._on_query:
            self.combo_time_range.currentIndexChanged.connect(self._emit_query_once)

        self.combo_status = QComboBox()
        self.combo_status.setProperty("td", "win11-input")
        self.combo_status.setFixedSize(SizeTokens.HISTORY_FILTER_SELECT_WIDTH, SizeTokens.CONTROL_HEIGHT)
        self.combo_status.addItem("全部", None)
        self.combo_status.addItem("成功", "success")
        self.combo_status.addItem("部分成功", "partial")
        self.combo_status.addItem("失败", "failed")
        self.combo_status.addItem("异常退出", "failed_abnormal_exit")
        if self._on_query:
            self.combo_status.currentIndexChanged.connect(self._emit_query_once)

        self.combo_type = QComboBox()
        self.combo_type.setProperty("td", "win11-input")
        self.combo_type.setFixedSize(SizeTokens.HISTORY_FILTER_SELECT_WIDTH, SizeTokens.CONTROL_HEIGHT)
        self.combo_type.addItem("全部", None)
        self.combo_type.addItem("增量", "incremental")
        self.combo_type.addItem("完全", "complete")
        if self._on_query:
            self.combo_type.currentIndexChanged.connect(self._emit_query_once)

        self.btn_query = QPushButton(ButtonText.QUERY)
        self.btn_query.setProperty("class", "primary")
        self.btn_query.setFixedSize(SizeTokens.HISTORY_FILTER_ACTION_WIDTH, SizeTokens.CONTROL_HEIGHT)
        if self._on_query:
            self.btn_query.clicked.connect(self._on_query)

        self.btn_reset = QPushButton("重置")
        self.btn_reset.setProperty("class", "secondary")
        self.btn_reset.setFixedSize(SizeTokens.HISTORY_FILTER_ACTION_WIDTH, SizeTokens.CONTROL_HEIGHT)
        if self._on_reset:
            self.btn_reset.clicked.connect(self._on_reset)

        self._grid = QWidget()
        self._grid.setProperty("compact", False)
        self._grid_layout = QGridLayout(self._grid)
        self._grid_layout.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        self._grid_layout.setHorizontalSpacing(SpacingTokens.LG)
        self._grid_layout.setVerticalSpacing(SpacingTokens.MD)

        self._filter_fields = [
            self._make_field("时间范围", self.combo_time_range),
            self._make_field("表单类型", self.combo_type),
            self._make_field("状态", self.combo_status),
            self._make_field("任务名称", self.search_box),
            self._make_actions(),
        ]
        self.content_layout.addWidget(self._grid)
        self._apply_layout()

    @staticmethod
    def _make_field(title: str, widget: QWidget) -> QWidget:
        row = QWidget()
        layout = QVBoxLayout(row)
        layout.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        layout.setSpacing(SpacingTokens.FORM_META_GAP)
        label = QLabel(title)
        label.setProperty("ui", "win11-row-title")
        layout.addWidget(label)
        layout.addWidget(widget)
        return row

    def _make_actions(self) -> QWidget:
        row = QWidget()
        layout = QVBoxLayout(row)
        layout.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        layout.setSpacing(SpacingTokens.FORM_META_GAP)
        label = QLabel("")
        label.setProperty("ui", "win11-row-title")
        layout.addWidget(label)
        action_row = QWidget()
        action_layout = QGridLayout(action_row)
        action_layout.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        action_layout.setHorizontalSpacing(SpacingTokens.MD)
        action_layout.addWidget(self.btn_query, 0, 0)
        action_layout.addWidget(self.btn_reset, 0, 1)
        layout.addWidget(action_row)
        return row

    def _emit_query_once(self) -> None:
        if not self._on_query or self._suppress_auto_query:
            return
        now = monotonic()
        if now - self._last_auto_query_at < 0.15:
            return
        self._last_auto_query_at = now
        self._on_query()

    def _apply_layout(self) -> None:
        compact = self.isVisible() and self.width() <= 1024
        self._grid.setProperty("compact", compact)
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        positions = (
            [(0, 0), (0, 1), (1, 0), (1, 1), (1, 2)]
            if compact
            else [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4)]
        )
        for (row, col), widget in zip(positions, self._filter_fields, strict=False):
            self._grid_layout.addWidget(widget, row, col)

    def reset_filters(self) -> None:
        self._suppress_auto_query = True
        try:
            self.combo_time_range.setCurrentIndex(0)
            self.combo_type.setCurrentIndex(0)
            self.combo_status.setCurrentIndex(0)
            self.search_box.clear()
        finally:
            self._suppress_auto_query = False

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._apply_layout()

    @property
    def search_text(self) -> str:
        return self.search_box.text().strip()

    @property
    def selected_days(self) -> int:
        return int(self.combo_time_range.currentData() or 0)

    @property
    def selected_status(self) -> str | None:
        return self.combo_status.currentData()

    @property
    def selected_sync_type(self) -> str | None:
        return self.combo_type.currentData()

    def set_quick_filter(self, days: int = 7, status: str | None = None, form_name: str | None = None) -> None:
        """Apply a quick filter when jumping from another page."""
        self._suppress_auto_query = True
        try:
            normalized_days = 30 if int(days or 0) >= 30 else 7
            self._set_combo_by_data(self.combo_time_range, normalized_days)
            if status in ("success", "partial", "failed", "failed_abnormal_exit"):
                self._set_combo_by_data(self.combo_status, status)
            else:
                self._set_combo_by_data(self.combo_status, None)
            self.search_box.setText(form_name or "")
        finally:
            self._suppress_auto_query = False

    @staticmethod
    def _set_combo_by_data(combo: QComboBox, target_value) -> None:
        for idx in range(combo.count()):
            if combo.itemData(idx) == target_value:
                combo.setCurrentIndex(idx)
                return
