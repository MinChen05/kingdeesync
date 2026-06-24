"""Minimal data table component."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from src.gui.design_tokens import SizeTokens, SpacingTokens


class DataTable(QFrame):
    """Minimal data table with empty-state support.

    First version: columns, rows, empty_state, set_data(), clear().
    No sorting, no pagination, no complex loading state.
    """

    def __init__(self, headers: list[str], *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("ui", "win11-data-table-wrapper")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        layout.setSpacing(SpacingTokens.NONE)

        self._table = QTableWidget(0, len(headers))
        self._table.setHorizontalHeaderLabels(headers)
        self._table.setProperty("ui", "win11-data-table")
        self._table.verticalHeader().setVisible(False)
        self._table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setMinimumSectionSize(SizeTokens.DATA_TABLE_MIN_SECTION_WIDTH)
        self._table.verticalHeader().setDefaultSectionSize(SizeTokens.DATA_TABLE_ROW_HEIGHT)

        self._empty_label = QLabel("暂无数据")
        self._empty_label.setProperty("ui", "win11-helper-text")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setVisible(True)

        layout.addWidget(self._table)
        layout.addWidget(self._empty_label)

    @property
    def table(self) -> QTableWidget:
        return self._table

    def set_empty_text(self, text: str) -> None:
        self._empty_label.setText(text)

    def set_data(self, rows: list[list[str]]) -> None:
        self._table.clearContents()
        self._table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for col_index, text in enumerate(row):
                item = QTableWidgetItem(text)
                if col_index == 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._table.setItem(row_index, col_index, item)
        self._empty_label.setVisible(len(rows) == 0)
        self._table.setVisible(len(rows) > 0)

    def clear(self) -> None:
        self._table.clearContents()
        self._table.setRowCount(0)
        self._empty_label.setVisible(True)
        self._table.setVisible(False)
