"""History page pagination card component."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QSpinBox, QWidget

from src.gui import icon_registry
from src.gui.design_tokens import SizeTokens, SpacingTokens


class HistoryPaginationCard(QFrame):
    """Pagination controls for the history page.

    Pure UI component; page state (current_page / total_records / page_size)
    stays in HistoryPage.  Updated via ``update_state()``.
    """

    def __init__(
        self,
        *,
        on_prev: Callable[[], None] | None = None,
        on_next: Callable[[], None] | None = None,
        on_jump: Callable[[int], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("ui", "win11-pagination-card")
        self.setFixedHeight(46)
        self._on_jump = on_jump

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            SpacingTokens.NONE, SpacingTokens.XS,
            SpacingTokens.NONE, SpacingTokens.XS,
        )
        layout.setSpacing(SpacingTokens.SM)

        page_size_label = QLabel("每页条数：")
        page_size_label.setProperty("ui", "win11-row-title")
        layout.addWidget(page_size_label)

        self.page_size_combo = QComboBox()
        self.page_size_combo.setProperty("td", "win11-input")
        self.page_size_combo.addItem("10", 10)
        self.page_size_combo.addItem("20", 20)
        self.page_size_combo.addItem("50", 50)
        self.page_size_combo.setFixedHeight(SizeTokens.PAGINATION_BUTTON_HEIGHT)
        self.page_size_combo.setFixedWidth(SizeTokens.HISTORY_PAGINATION_COMBO_WIDTH)
        layout.addWidget(self.page_size_combo)

        layout.addStretch(1)

        self.lbl_page_info = QLabel("共 0 条")
        self.lbl_page_info.setProperty("ui", "history-page-info")
        self.lbl_page_info.setMinimumWidth(102)
        self.lbl_page_info.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.lbl_page_info)
        layout.addSpacing(SpacingTokens.SM)

        self.btn_prev = QPushButton("")
        self.btn_prev.setProperty("class", "secondary")
        self.btn_prev.setProperty("icon-source", icon_registry.icon_source("chevron_left.svg"))
        self.btn_prev.setIcon(icon_registry.qicon("chevron_left.svg"))
        self.btn_prev.setFixedHeight(SizeTokens.PAGINATION_BUTTON_HEIGHT)
        self.btn_prev.setFixedWidth(SizeTokens.PAGINATION_SIZE)
        if on_prev:
            self.btn_prev.clicked.connect(on_prev)

        self._page_buttons: list[QPushButton] = [
            self._make_page_button(str(index), active=(index == 1)) for index in range(1, 8)
        ]
        self.lbl_curr_page = self._page_buttons[0]
        self._page_labels = self._page_buttons[1:6]
        self.lbl_last_page = self._page_buttons[-1]

        self.btn_next = QPushButton("")
        self.btn_next.setProperty("class", "secondary")
        self.btn_next.setProperty("icon-source", icon_registry.icon_source("chevron_right.svg"))
        self.btn_next.setIcon(icon_registry.qicon("chevron_right.svg"))
        self.btn_next.setFixedHeight(SizeTokens.PAGINATION_BUTTON_HEIGHT)
        self.btn_next.setFixedWidth(SizeTokens.PAGINATION_SIZE)
        if on_next:
            self.btn_next.clicked.connect(on_next)

        self.jump_label = QLabel("跳转到")
        self.jump_label.setProperty("ui", "win11-row-title")
        self.jump_label.setVisible(False)

        self.jump_box = QSpinBox()
        self.jump_box.setProperty("td", "win11-input")
        self.jump_box.setMinimum(1)
        self.jump_box.setFixedWidth(SizeTokens.PAGINATION_JUMP_WIDTH)
        self.jump_box.setVisible(False)
        if on_jump:
            self.jump_box.editingFinished.connect(lambda: on_jump(self.jump_box.value()))

        layout.addWidget(self.btn_prev)
        for button in self._page_buttons:
            layout.addWidget(button)
        layout.addWidget(self.btn_next)
        layout.addSpacing(SpacingTokens.SM)
        layout.addWidget(self.jump_label)
        layout.addWidget(self.jump_box)

    def _make_page_button(self, text: str, *, active: bool = False) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("ui", "win11-page-badge" if active else "win11-page-badge-muted")
        button.setFixedSize(SizeTokens.HISTORY_PAGINATION_LABEL_WIDTH, SizeTokens.PAGINATION_BUTTON_HEIGHT)
        button.clicked.connect(lambda _checked=False, btn=button: self._handle_page_button(btn))
        return button

    def _handle_page_button(self, button: QPushButton) -> None:
        if not callable(self._on_jump):
            return
        text = button.text().strip()
        if not text.isdigit():
            return
        self._on_jump(int(text))

    def update_state(self, current_page: int, total_records: int, page_size: int) -> None:
        """Refresh controls to reflect current pagination state."""
        self.lbl_page_info.setText(f"共 {total_records:,} 条")
        total_pages = max(1, (total_records + page_size - 1) // page_size)
        self.btn_prev.setEnabled(current_page > 1)
        self.btn_next.setEnabled(current_page < total_pages)
        self.jump_box.setMaximum(total_pages)
        page_items: list[str] = [str(page) for page in range(1, min(5, total_pages) + 1)]
        if total_pages > 6:
            page_items.extend(["...", str(total_pages)])
        elif total_pages == 6:
            page_items.append("6")

        for index, button in enumerate(self._page_buttons):
            if index >= len(page_items):
                button.setVisible(False)
                continue
            text = page_items[index]
            button.setText(text)
            button.setVisible(True)
            is_active = text.isdigit() and int(text) == current_page
            button.setEnabled(text != "..." and not is_active)
            button.setProperty("ui", "win11-page-badge" if is_active else "win11-page-badge-muted")
            button.style().unpolish(button)
            button.style().polish(button)
        self.jump_box.setValue(current_page)
