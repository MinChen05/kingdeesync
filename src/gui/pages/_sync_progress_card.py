"""Sync page progress card component."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from src.gui.design_tokens import SizeTokens, SpacingTokens


class SyncProgressCard(QFrame):
    """Progress bar + status text for sync execution.

    Lightweight QFrame with ``ui="win11-progress-card"`` so QSS
    ``QFrame[ui="win11-progress-card"]`` matches directly.
    Pure UI component; sync state stays in SyncPage.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("ui", "win11-progress-card")
        self.setMinimumHeight(76)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SpacingTokens.PROGRESS_PANEL_PADDING, SpacingTokens.PROGRESS_PANEL_PADDING,
            SpacingTokens.PROGRESS_PANEL_PADDING, SpacingTokens.PROGRESS_PANEL_PADDING,
        )
        layout.setSpacing(SpacingTokens.MD)

        row = QHBoxLayout()
        label = QLabel("任务进度")
        label.setProperty("ui", "win11-row-title")
        row.addWidget(label)
        row.addStretch(1)

        self.progress_status_lbl = QLabel("等待中")
        self.progress_status_lbl.setProperty("ui", "win11-inline-title")
        row.addWidget(self.progress_status_lbl)

        layout.addLayout(row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(12)
        layout.addWidget(self.progress_bar)

    def set_progress(self, value: int, text: str | None = None) -> None:
        """Update progress bar value and optional status text."""
        self.progress_bar.setValue(value)
        if text is not None:
            self.progress_status_lbl.setText(text)
        else:
            self.progress_status_lbl.setText(f"{value}%")

    def set_status(self, text: str) -> None:
        """Update status label text only (no progress bar change)."""
        self.progress_status_lbl.setText(text)

    def reset(self) -> None:
        """Reset to initial state."""
        self.progress_bar.setValue(0)
        self.progress_status_lbl.setText("等待中")
