"""Dashboard failure records table component."""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import QWidget

from src.gui.components.data_table import DataTable
from src.gui.components.page_shell import Win11SectionCard


class DashboardFailTable(Win11SectionCard):
    """Failure records table for the dashboard.

    Wraps a DataTable inside a section card.  Row-click navigates
    to the history page via the provided callback.
    """

    def __init__(self, on_row_clicked: Callable[[int], None] | None = None) -> None:
        super().__init__(
            "近期失败",
            "点击行可跳转到历史记录并应用快捷筛选。",
        )
        self._on_row_clicked = on_row_clicked
        self._fail_rows_meta: list[dict] = []

        self._data_table = DataTable(["时间", "表单", "状态", "摘要"])
        self._data_table.table.cellClicked.connect(self._handle_row_clicked)
        self.content_layout.addWidget(self._data_table)

    def _handle_row_clicked(self, row: int, _column: int) -> None:
        if self._on_row_clicked and 0 <= row < len(self._fail_rows_meta):
            self._on_row_clicked(row)

    def set_fail_data(self, rows: list[list[str]], meta: list[dict]) -> None:
        """Update table rows and store metadata for click handling."""
        self._fail_rows_meta = meta
        self._data_table.set_data(rows)

    def get_row_meta(self, row: int) -> dict | None:
        if 0 <= row < len(self._fail_rows_meta):
            return self._fail_rows_meta[row]
        return None
