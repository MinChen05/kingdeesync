"""
状态视图组件
统一空态、错误态、加载态展示。
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class StateWidget(QWidget):
    """统一状态面板"""

    ICON_MAP = {
        "empty": "空",
        "error": "错",
        "loading": "载",
    }

    def __init__(self, mode="empty", title="", desc="", parent=None):
        super().__init__(parent)
        self._mode = mode

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignCenter)

        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)

        self.title_label = QLabel()
        self.title_label.setAlignment(Qt.AlignCenter)

        self.desc_label = QLabel()
        self.desc_label.setAlignment(Qt.AlignCenter)
        self.desc_label.setWordWrap(True)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.desc_label)

        self.set_state(mode, title, desc)

    def set_state(self, mode="empty", title="", desc=""):
        self._mode = mode
        self.setProperty("state", mode)

        self.icon_label.setText(self.ICON_MAP.get(mode, "态"))
        self.icon_label.setProperty("class", f"state-badge state-badge-{mode}")
        self.title_label.setText(title)
        self.title_label.setProperty("class", "state-title")
        self.desc_label.setText(desc)
        self.desc_label.setProperty("class", "state-desc")

        for widget in (self, self.icon_label, self.title_label, self.desc_label):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
