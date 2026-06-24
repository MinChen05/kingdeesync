"""Schedule page status panel component."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from src.gui.design_tokens import SizeTokens, SpacingTokens


class ScheduleStatusPanel(QFrame):
    """Status display for the schedule page.

    Lightweight QFrame with ``ui="win11-progress-card"`` matching the
    existing QSS selector.  Pure UI; scheduler state stays in SchedulePage.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("ui", "win11-progress-card")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SpacingTokens.PROGRESS_PANEL_PADDING, SpacingTokens.PROGRESS_PANEL_PADDING,
            SpacingTokens.PROGRESS_PANEL_PADDING, SpacingTokens.PROGRESS_PANEL_PADDING,
        )
        layout.setSpacing(SpacingTokens.SM)

        self.status_text = QLabel("空闲")
        self.status_text.setProperty("ui", "win11-inline-value")
        self.status_text.setMinimumHeight(SizeTokens.SCHEDULE_STATUS_TEXT_MIN_HEIGHT)
        self.status_text.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.lbl_last_exec = QLabel("最近执行：--")
        self.lbl_last_exec.setProperty("ui", "win11-inline-title")

        self.lbl_next_exec = QLabel("下次执行：--")
        self.lbl_next_exec.setProperty("ui", "win11-inline-title")

        layout.addWidget(self.status_text)
        layout.addWidget(self.lbl_last_exec)
        layout.addWidget(self.lbl_next_exec)

    def set_status(self, text: str) -> None:
        """Update the main status text."""
        self.status_text.setText(text)

    def set_last_exec(self, text: str) -> None:
        """Update last execution time display."""
        self.lbl_last_exec.setText(f"最近执行：{text}")

    def set_next_exec(self, text: str) -> None:
        """Update next execution time display."""
        self.lbl_next_exec.setText(f"下次执行：{text}")

    def reset(self) -> None:
        """Reset to initial state."""
        self.status_text.setText("空闲")
        self.lbl_last_exec.setText("最近执行：--")
        self.lbl_next_exec.setText("下次执行：--")
