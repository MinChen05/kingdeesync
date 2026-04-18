"""
下拉框组件模块
包含可搜索下拉框等组件
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Signal, Qt, QPoint, QTimer
from PySide6.QtGui import QColor, QIcon


class ComboPopup(QWidget):
    """下拉弹出框"""

    itemClicked = Signal(str, object)

    def __init__(self, parent, items, searchable=True):
        super().__init__(parent, Qt.Popup)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setFocusPolicy(Qt.StrongFocus)

        # 外观
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 阴影容器
        self.container = QWidget(self)
        self.container.setObjectName("combo_popup_container")

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 4)
        self.container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(self.container)

        popup_layout = QVBoxLayout(self.container)
        popup_layout.setContentsMargins(8, 8, 8, 8)
        popup_layout.setSpacing(0)

        # 搜索框
        if searchable:
            self.search_box = QLineEdit()
            self.search_box.setObjectName("combo_popup_search")
            self.search_box.setPlaceholderText("输入搜索关键字...")
            self.search_box.setClearButtonEnabled(True)
            self.search_box.textChanged.connect(self.filter_items)
            popup_layout.addWidget(self.search_box)
        else:
            self.search_box = None

        # 列表
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("combo_popup_list")
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        popup_layout.addWidget(self.list_widget)

        self.items_data = items
        self.populate_list()

    def populate_list(self, filter_text=""):
        self.list_widget.clear()
        for text, icon, data in self.items_data:
            if filter_text.lower() in text.lower():
                item = QListWidgetItem(f"{icon}  {text}")
                item.setData(Qt.UserRole, (text, data))
                self.list_widget.addItem(item)

    def filter_items(self, text):
        self.populate_list(text)

    def on_item_clicked(self, item):
        text, data = item.data(Qt.UserRole)
        self.itemClicked.emit(text, data)
        self.close()

    def focusOutEvent(self, event):
        # 简单处理：失焦就关闭。可能需要延时判断
        QTimer.singleShot(100, self.close)


class SearchableComboBox(QWidget):
    """可搜索的卡片式下拉框"""

    currentTextChanged = Signal(str)
    currentIndexChanged = Signal(int)

    def __init__(self, parent=None, placeholder="请选择", items=None, searchable=True):
        super().__init__(parent)
        self.items_data = items or []  # list of (text, icon, data)
        self.searchable = searchable
        self.placeholder = placeholder
        self._current_text = ""
        self._current_data = None

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Main Button
        self.btn = QPushButton(self.placeholder)
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.setProperty("class", "combo-btn")

        # Add shadow to the button
        shadow = QGraphicsDropShadowEffect(self.btn)
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 15))
        shadow.setOffset(0, 2)
        self.btn.setGraphicsEffect(shadow)

        self.btn.clicked.connect(self.show_popup)
        layout.addWidget(self.btn)

    def show_popup(self):
        # Create popup
        self.popup = ComboPopup(self, self.items_data, self.searchable)
        self.popup.itemClicked.connect(self.on_item_selected)

        # Calculate position
        pos = self.mapToGlobal(QPoint(0, self.height()))
        self.popup.move(pos.x() - 10, pos.y() - 10)
        self.popup.setFixedWidth(self.width() + 20)

        # Height limit
        content_height = min(len(self.items_data) * 40 + 60, 300)
        self.popup.setFixedHeight(content_height)

        self.popup.show()

    def on_item_selected(self, text, data):
        self._current_text = text
        self._current_data = data

        # Find icon
        icon = ""
        for t, i, d in self.items_data:
            if t == text:
                icon = i
                break

        display_text = f"{icon}  {text}" if isinstance(icon, str) and icon else text
        self.btn.setText(display_text)
        self.currentTextChanged.emit(text)

        # Find index
        idx = -1
        for i, (t, _, _) in enumerate(self.items_data):
            if t == text:
                idx = i
                break
        self.currentIndexChanged.emit(idx)

    def addItems(self, texts):
        # Compatibility method
        new_items = []
        for t in texts:
            icon = "单"
            if "同步所有" in t:
                icon = "全"
            elif "自定义" in t:
                icon = "配"
            elif "增量" in t:
                icon = "增"
            elif "全量" in t:
                icon = "全"
            elif "重置" in t:
                icon = "重"

            new_items.append((t, icon, t))

        self.items_data.extend(new_items)

    def currentText(self):
        return self._current_text

    def currentIndex(self):
        for i, (t, _, _) in enumerate(self.items_data):
            if t == self._current_text:
                return i
        return -1

    def setCurrentIndex(self, index):
        if 0 <= index < len(self.items_data):
            text, icon, data = self.items_data[index]
            self.on_item_selected(text, data)

    def count(self):
        return len(self.items_data)

    def itemText(self, index):
        if 0 <= index < len(self.items_data):
            return self.items_data[index][0]
        return ""

    def setCurrentText(self, text):
        for i, (t, _, d) in enumerate(self.items_data):
            if t == text:
                self.on_item_selected(t, d)
                return

    def clear(self):
        self.items_data = []
        self._current_text = ""
        self.btn.setText(self.placeholder)
