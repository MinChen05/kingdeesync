"""Shared reusable UI primitives for pages."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.gui.design_tokens import ColorTokens, SizeTokens, SpacingTokens
from src.gui.ui_text import ButtonText


class ActionBar(QWidget):
    """Horizontal container for page top action areas."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("ui", "win11-action-bar")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        self._layout.setSpacing(SpacingTokens.ACTION_BAR_GAP)

    def add_action(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)

    def add_stretch(self) -> None:
        self._layout.addStretch(1)


class FieldRow(QFrame):
    """Title + note + editor row for settings / config pages."""

    def __init__(
        self,
        title_text: str,
        note_text: str,
        editor: QWidget,
        *,
        compact: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("ui", "win11-setting-row")

        self._editor = editor
        self._compact = compact

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(SpacingTokens.NONE, SpacingTokens.FIELD_ROW_VERTICAL, SpacingTokens.NONE, SpacingTokens.FIELD_ROW_VERTICAL)
        self._layout.setSpacing(SpacingTokens.FIELD_ROW_GAP)

        text_wrap = QVBoxLayout()
        text_wrap.setSpacing(SpacingTokens.XXS)

        self.title_label = QLabel(title_text)
        self.title_label.setProperty("ui", "win11-row-title")

        self.note_label = QLabel(note_text)
        self.note_label.setProperty("ui", "win11-row-note")
        self.note_label.setWordWrap(True)

        text_wrap.addWidget(self.title_label)
        text_wrap.addWidget(self.note_label)

        self._layout.addLayout(text_wrap, 1)

        editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._layout.addWidget(editor, 1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        if compact:
            self._apply_compact()

    def set_compact(self, compact: bool) -> None:
        self._compact = compact
        self._apply_compact()

    def _apply_compact(self) -> None:
        from PySide6.QtWidgets import QBoxLayout, QSpinBox

        self._layout.setDirection(
            QBoxLayout.Direction.TopToBottom if self._compact else QBoxLayout.Direction.LeftToRight
        )
        if isinstance(self._editor, QSpinBox):
            self._editor.setFixedWidth(SizeTokens.FIELD_ROW_SPIN_WIDTH_COMPACT if self._compact else SizeTokens.FIELD_ROW_SPIN_WIDTH)
        else:
            self._editor.setMinimumWidth(0)
            self._editor.setMaximumWidth(SizeTokens.QT_MAX_WIDTH if self._compact else SizeTokens.FIELD_ROW_EDITOR_MAX_WIDTH)


class StatusChip(QLabel):
    """Unified status indicator with tone property."""

    _VALID_TONES = {"success", "warning", "danger", "info", "neutral"}

    def __init__(self, text: str = "", tone: str = "info", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setProperty("ui", "win11-status-chip")
        self.setProperty("tone", tone if tone in self._VALID_TONES else "info")

    def set_tone(self, tone: str) -> None:
        self.setProperty("tone", tone if tone in self._VALID_TONES else "info")
        self.style().unpolish(self)
        self.style().polish(self)


class SvgIconLabel(QLabel):
    """Small asset-backed SVG icon label for consistent line icons."""

    _ASSETS_DIR = Path(__file__).resolve().parents[3] / "assets"

    def __init__(
        self,
        icon_file: str,
        *,
        size: int = 20,
        icon_size: int | None = None,
        color: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.icon_file = icon_file
        self.icon_color = color
        self.setProperty("ui", "svg-icon")
        self.setProperty("icon-source", icon_file)
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_icon(icon_file, icon_size or size)

    def set_icon(self, icon_file: str, icon_size: int | None = None, color: str | None = None) -> None:
        self.icon_file = icon_file
        if color is not None:
            self.icon_color = color
        self.setProperty("icon-source", icon_file)
        path = self._ASSETS_DIR / "icons" / icon_file
        if not path.exists():
            path = self._ASSETS_DIR / icon_file
        size = icon_size or min(self.width(), self.height())
        if self.icon_color and path.exists():
            svg = path.read_text(encoding="utf-8").replace("currentColor", self.icon_color)
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
            renderer.render(painter, QRectF(0, 0, size, size))
            painter.end()
            self.setPixmap(pixmap)
            palette = self.palette()
            palette.setColor(self.foregroundRole(), QColor(self.icon_color))
            self.setPalette(palette)
            return
        self.setPixmap(QIcon(str(path)).pixmap(QSize(size, size)))

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.set_icon(self.icon_file)
        super().showEvent(event)


class LogPanel(QFrame):
    """Log text area with clear / copy toolbar and optional export."""

    clear_requested = Signal()
    copy_requested = Signal()
    export_requested = Signal()

    def __init__(self, *, placeholder: str = "", show_filter: bool = False, show_export: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("ui", "win11-log-panel")

        root = QVBoxLayout(self)
        root.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        root.setSpacing(SpacingTokens.NONE)

        toolbar_host = QFrame()
        toolbar_host.setProperty("ui", "win11-log-toolbar")
        toolbar = QHBoxLayout(toolbar_host)
        toolbar.setContentsMargins(SpacingTokens.LOG_TOOLBAR_H_PADDING, SpacingTokens.LOG_TOOLBAR_V_PADDING, SpacingTokens.LOG_TOOLBAR_H_PADDING, SpacingTokens.LOG_TOOLBAR_V_PADDING)
        toolbar.setSpacing(SpacingTokens.SM)

        if show_filter:
            self._filter_input = QLineEdit()
            self._filter_input.setPlaceholderText(placeholder)
            self._filter_input.setProperty("ui", "win11-log-filter")
            self._filter_input.setClearButtonEnabled(True)
            toolbar.addWidget(self._filter_input, 1)

        self._btn_clear = QPushButton(ButtonText.CLEAR)
        self._btn_clear.setProperty("class", "secondary")
        self._btn_clear.setFixedHeight(SizeTokens.LOG_ACTION_BUTTON_HEIGHT)
        self._btn_clear.clicked.connect(self._on_clear)
        self.clear_requested.connect(self.clear_log)

        self._btn_copy = QPushButton(ButtonText.COPY)
        self._btn_copy.setProperty("class", "secondary")
        self._btn_copy.setFixedHeight(SizeTokens.LOG_ACTION_BUTTON_HEIGHT)
        self._btn_copy.clicked.connect(self._on_copy)
        self.copy_requested.connect(self.copy_log)

        toolbar.addWidget(self._btn_clear)
        toolbar.addWidget(self._btn_copy)

        if show_export:
            self._btn_export = QPushButton(ButtonText.EXPORT)
            self._btn_export.setProperty("class", "secondary")
            self._btn_export.setFixedHeight(SizeTokens.LOG_ACTION_BUTTON_HEIGHT)
            self._btn_export.clicked.connect(self.export_requested.emit)
            toolbar.addWidget(self._btn_export)

        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setProperty("ui", "win11-log-text")
        self._log_text.setProperty("class", "win11-log")

        root.addWidget(toolbar_host)
        root.addWidget(self._log_text, 1)

    def _on_clear(self) -> None:
        self.clear_requested.emit()

    def _on_copy(self) -> None:
        self.copy_requested.emit()

    @property
    def log_text(self) -> QTextEdit:
        return self._log_text

    def append_log(self, message: str, level: str = "INFO") -> None:
        import html as _html

        timestamp = datetime.now().strftime("%H:%M:%S")
        safe_msg = _html.escape(str(message))
        color_map = {
            "ERROR": ColorTokens.DANGER,
            "WARNING": ColorTokens.WARNING,
            "INFO": ColorTokens.TEXT_SECONDARY,
            "DEBUG": ColorTokens.TEXT_MUTED,
        }
        color = color_map.get(level.upper(), ColorTokens.TEXT_SECONDARY)
        self._log_text.append(
            f'<span style="color:{ColorTokens.TEXT_DISABLED};">[{timestamp}]</span> '
            f'<span style="color:{color};">{safe_msg}</span>'
        )
        sb = self._log_text.verticalScrollBar()
        if sb is not None:
            sb.setValue(sb.maximum())

    def clear_log(self) -> None:
        self._log_text.clear()

    def copy_log(self) -> None:
        from PySide6.QtWidgets import QApplication

        text = self._log_text.toPlainText()
        if text:
            clipboard = QApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(text)

    def get_plain_text(self) -> str:
        return self._log_text.toPlainText()


class MetricCard(QFrame):
    """Compact metric card: title + value + optional note."""

    def __init__(self, title: str, value: str = "--", note: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("ui", "win11-metric-card")
        self.setMinimumHeight(SizeTokens.METRIC_CARD_MIN_HEIGHT)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SpacingTokens.LG, SpacingTokens.FIELD_ROW_VERTICAL, SpacingTokens.LG, SpacingTokens.FIELD_ROW_VERTICAL)
        layout.setSpacing(SpacingTokens.XS)

        self.title_label = QLabel(title)
        self.title_label.setProperty("ui", "win11-inline-title")

        self.value_label = QLabel(value)
        self.value_label.setProperty("ui", "win11-inline-value")

        self.note_label = QLabel(note)
        self.note_label.setProperty("ui", "win11-helper-text")
        self.note_label.setWordWrap(True)
        self.note_label.setVisible(bool(note))

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.note_label)

    def set_data(self, value: str, note: str | None = None) -> None:
        self.value_label.setText(value)
        if note is not None:
            self.note_label.setText(note)
            self.note_label.setVisible(bool(note))
