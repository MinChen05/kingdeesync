"""Schedule page preset button group component."""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from src.gui.design_tokens import SizeTokens, SpacingTokens


class PresetButtonGroup(QFrame):
    """Quick preset buttons for schedule interval selection.

    Pure UI component; interval state stays in SchedulePage.
    """

    def __init__(
        self,
        presets: tuple[int, ...] = (15, 30, 60, 120),
        on_selected: Callable[[int], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("ui", "win11-inline-card")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SpacingTokens.MD, SpacingTokens.MD, SpacingTokens.MD, SpacingTokens.MD)
        layout.setSpacing(SpacingTokens.SM)

        title = QLabel("快捷预设")
        title.setProperty("ui", "win11-inline-title")
        layout.addWidget(title)
        layout.addStretch(1)

        self.interval_presets: list[tuple[int, QPushButton]] = []
        for minutes in presets:
            btn = QPushButton(f"{minutes} 分钟")
            btn.setProperty("class", "secondary")
            btn.setFixedHeight(SizeTokens.SCHEDULE_PRESET_BUTTON_HEIGHT)
            if on_selected:
                btn.clicked.connect(lambda _checked=False, value=minutes: on_selected(value))
            self.interval_presets.append((minutes, btn))
            layout.addWidget(btn)

    def set_active(self, minutes: int) -> None:
        """Highlight the button matching the current interval."""
        for m, btn in self.interval_presets:
            btn.setProperty("class", "primary" if m == minutes else "secondary")
            style = btn.style()
            if style is not None:
                style.unpolish(btn)
                style.polish(btn)
