"""
Windows 11-style page primitives.

These widgets are intentionally light on styling: we expose `ui` properties and
stable `objectName`s so the app's QSS can skin them consistently.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

EXPLANATION_LABEL_UIS = {
    "win11-hero-subtitle",
    "win11-summary-subtitle",
    "win11-section-subtitle",
    "win11-meta-text",
    "win11-helper-text",
    "win11-helper-text-success",
    "win11-helper-text-danger",
    "win11-inline-banner",
    "win11-row-note",
}


def hide_explanation_labels(root: QWidget) -> None:
    """Hide explanatory labels to keep the workspace concise."""
    if root is None:
        return

    for label in root.findChildren(QLabel):
        ui = label.property("ui")
        if ui in EXPLANATION_LABEL_UIS:
            label.setVisible(False)


class Win11SummaryCard(QFrame):
    """Small stat card for a summary strip."""

    def __init__(self, title: str = "", value: str = "", subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("ui", "win11-summary-card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setProperty("ui", "win11-summary-title")

        self.value_label = QLabel(value)
        self.value_label.setProperty("ui", "win11-summary-value")

        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setProperty("ui", "win11-summary-subtitle")
        self.subtitle_label.setVisible(bool(subtitle))
        self.subtitle_label.setWordWrap(True)

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.subtitle_label)
        layout.addStretch(1)

    def set_title(self, title: str) -> None:
        self.title_label.setText(title or "")

    def set_value(self, value: str) -> None:
        self.value_label.setText(value or "")

    def set_subtitle(self, subtitle: str) -> None:
        subtitle = subtitle or ""
        self.subtitle_label.setText(subtitle)
        self.subtitle_label.setVisible(False)


class Win11SectionCard(QFrame):
    """Shared content card with a title, subtitle, and body area."""

    def __init__(self, title: str = "", subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("ui", "win11-section-card")

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        self.title_label = QLabel(title)
        self.title_label.setProperty("ui", "win11-section-title")

        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setProperty("ui", "win11-section-subtitle")
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setVisible(bool(subtitle))

        root.addWidget(self.title_label)
        root.addWidget(self.subtitle_label)

        self.body = QWidget(self)
        self.body.setProperty("ui", "win11-section-body")

        self.content_layout = QVBoxLayout(self.body)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(12)

        root.addWidget(self.body)

    def set_title(self, title: str) -> None:
        self.title_label.setText(title or "")

    def set_subtitle(self, subtitle: str) -> None:
        subtitle = subtitle or ""
        self.subtitle_label.setText(subtitle)
        self.subtitle_label.setVisible(False)


class Win11PageScaffold(QWidget):
    """
    Reusable page scaffold:
    - Hero card (eyebrow + title + subtitle + optional right-side widgets)
    - Summary strip (cards)
    - Content host (page-specific widgets)
    """

    def __init__(
        self,
        title: str = "",
        *,
        eyebrow: str = "",
        subtitle: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("ui", "win11-page")

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 18)
        root.setSpacing(12)

        self.hero_card = QFrame(self)
        self.hero_card.setObjectName("page_hero_card")
        self.hero_card.setProperty("ui", "win11-hero-card")
        self.hero_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        hero_layout = QHBoxLayout(self.hero_card)
        hero_layout.setContentsMargins(18, 16, 18, 16)
        hero_layout.setSpacing(16)

        hero_text_host = QWidget(self.hero_card)
        hero_text_host.setProperty("ui", "win11-hero-copy")
        hero_text_layout = QVBoxLayout(hero_text_host)
        hero_text_layout.setContentsMargins(0, 0, 0, 0)
        hero_text_layout.setSpacing(4)

        self.hero_eyebrow = QLabel("", hero_text_host)
        self.hero_eyebrow.setObjectName("page_hero_eyebrow")
        self.hero_eyebrow.setProperty("ui", "win11-hero-eyebrow")
        self.hero_eyebrow.setVisible(False)

        self.hero_title = QLabel(title, hero_text_host)
        self.hero_title.setObjectName("page_hero_title")
        self.hero_title.setProperty("ui", "win11-hero-title")
        self.hero_title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.hero_subtitle = QLabel("", hero_text_host)
        self.hero_subtitle.setObjectName("page_hero_subtitle")
        self.hero_subtitle.setProperty("ui", "win11-hero-subtitle")
        self.hero_subtitle.setWordWrap(True)
        self.hero_subtitle.setVisible(False)

        hero_text_layout.addWidget(self.hero_eyebrow)
        hero_text_layout.addWidget(self.hero_title)
        hero_text_layout.addWidget(self.hero_subtitle)

        hero_layout.addWidget(hero_text_host, 1)

        self.hero_actions_host = QWidget(self.hero_card)
        self.hero_actions_host.setObjectName("page_hero_actions")
        self.hero_actions_host.setProperty("ui", "win11-hero-actions")
        self.hero_actions_host.setVisible(False)

        self.hero_actions_layout = QHBoxLayout(self.hero_actions_host)
        self.hero_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.hero_actions_layout.setSpacing(12)
        self.hero_actions_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        hero_layout.addWidget(self.hero_actions_host, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        self.primary_action_host = QFrame(self)
        self.primary_action_host.setObjectName("page_primary_actions")
        self.primary_action_host.setProperty("ui", "win11-primary-action-bar")
        self.primary_action_host.setVisible(False)

        self.primary_action_layout = QHBoxLayout(self.primary_action_host)
        self.primary_action_layout.setContentsMargins(14, 12, 14, 12)
        self.primary_action_layout.setSpacing(10)

        self.summary_strip = QWidget(self)
        self.summary_strip.setObjectName("page_summary_strip")
        self.summary_strip.setProperty("ui", "win11-summary-strip")

        summary_layout = QHBoxLayout(self.summary_strip)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(10)
        summary_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.content_host = QWidget(self)
        self.content_host.setObjectName("page_content_host")
        self.content_host.setProperty("ui", "win11-content-host")
        self.content_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        content_layout = QVBoxLayout(self.content_host)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        root.addWidget(self.hero_card)
        root.addWidget(self.primary_action_host)
        root.addWidget(self.summary_strip)
        root.addWidget(self.content_host, 1)

        self.set_hero_eyebrow(eyebrow)
        self.set_hero_subtitle(subtitle)
        self.set_hero_visible(False)

    def set_title(self, title: str) -> None:
        self.hero_title.setText(title or "")

    def set_hero_eyebrow(self, text: str) -> None:
        text = text or ""
        self.hero_eyebrow.setText(text)
        self.hero_eyebrow.setVisible(bool(text))

    def set_hero_subtitle(self, text: str) -> None:
        text = text or ""
        self.hero_subtitle.setText(text)
        self.hero_subtitle.setVisible(False)

    def set_hero_visible(self, visible: bool) -> None:
        self.hero_card.setVisible(bool(visible))

    def add_hero_widget(self, widget: QWidget) -> None:
        self.hero_actions_host.setVisible(True)
        self.hero_actions_layout.addWidget(widget)
        hide_explanation_labels(widget)

    def add_primary_action(self, widget: QWidget) -> None:
        self.primary_action_host.setVisible(True)
        self.primary_action_layout.addWidget(widget)

    def add_summary_card(self, card: QWidget) -> None:
        layout = self.summary_strip.layout()
        if layout is not None:
            layout.addWidget(card)
            hide_explanation_labels(card)

    def create_scroll_container(self, object_name: str) -> QScrollArea:
        scroll = QScrollArea(self)
        scroll.setObjectName(object_name)
        scroll.setProperty("ui", "win11-page-scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        return scroll

    def set_content(self, widget: QWidget) -> None:
        """
        Replace the page's content area with `widget`.

        Important: this is a destructive replacement. Any existing widgets and
        nested layouts previously added to `page_content_host` are removed and
        scheduled for deletion via `deleteLater()`. Callers must not expect to
        reuse or reattach the old widgets after calling this.
        """

        layout = self.content_host.layout()
        if layout is None:
            return

        self._clear_layout(layout)
        layout.addWidget(widget)
        hide_explanation_labels(widget)

    @staticmethod
    def _clear_layout(layout: QLayout) -> None:
        """
        Remove all items from a layout, including nested layouts and spacers.

        This is important for pages that compose content via sub-layouts; simply
        detaching direct widgets can leave nested widgets parented and leaking.
        """

        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                continue

            child_layout = item.layout()
            if child_layout is not None:
                Win11PageScaffold._clear_layout(child_layout)
                child_layout.setParent(None)
                child_layout.deleteLater()
                continue

            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
                continue

            spacer = item.spacerItem()
            if spacer is not None:
                continue
