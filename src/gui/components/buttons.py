"""
按钮组件模块
包含各种自定义按钮组件
"""

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QLabel, QPushButton, QWidget

from src.gui.design_tokens import ColorTokens, qcolor
from src.gui.ui_text import LoadingText


class ClickableLabel(QLabel):
    """可点击的标签"""

    clicked = Signal()

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        from PySide6.QtCore import Qt

        self.setCursor(Qt.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        from PySide6.QtCore import Qt

        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class SwitchButton(QWidget):
    """自定义开关按钮"""

    toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        from PySide6.QtCore import Qt

        self.setFixedSize(44, 24)
        self.setCursor(Qt.PointingHandCursor)
        self._checked = False
        self._bg_color = qcolor(ColorTokens.TEXT_DISABLED)
        self._circle_color = qcolor(ColorTokens.SURFACE_BASE)
        self._circle_x = 2

        self._anim = QPropertyAnimation(self, b"circle_pos", self)
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)

    def get_circle_pos(self):
        return self._circle_x

    def set_circle_pos(self, value):
        self._circle_x = value
        self.update()

    circle_pos = Property(float, get_circle_pos, set_circle_pos)

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        if self._checked != checked:
            self._checked = checked
            target = 22 if checked else 2
            self._bg_color = qcolor(ColorTokens.BRAND_600) if checked else qcolor(ColorTokens.TEXT_DISABLED)
            self._anim.setStartValue(self._circle_x)
            self._anim.setEndValue(target)
            self._anim.start()
            self.toggled.emit(checked)

    def mouseReleaseEvent(self, event):
        from PySide6.QtCore import Qt

        if event.button() == Qt.LeftButton:
            self.setChecked(not self._checked)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Background
        path = QPainterPath()
        path.addRoundedRect(0, 0, 44, 24, 12, 12)
        p.fillPath(path, self._bg_color)

        # Circle
        p.setBrush(self._circle_color)
        p.setPen(Qt.NoPen)
        p.drawEllipse(self._circle_x, 2, 20, 20)


class LoadingButton(QPushButton):
    """支持加载状态的主操作按钮"""

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        from PySide6.QtCore import Qt

        self.original_text = text
        self._loading_text = LoadingText.DEFAULT
        self.setCursor(Qt.PointingHandCursor)
        self._is_loading = False
        self._angle = 0

        # 阴影效果 (Hover动画)
        self._shadow = QGraphicsDropShadowEffect()
        self._shadow.setBlurRadius(0)
        self._shadow.setColor(qcolor(ColorTokens.BRAND_600, 80))
        self._shadow.setOffset(0, 4)
        self.setGraphicsEffect(self._shadow)

        self._anim_shadow = QPropertyAnimation(self._shadow, b"blurRadius")
        self._anim_shadow.setDuration(200)
        self._anim_shadow.setEasingCurve(QEasingCurve.OutQuad)

        # 动画定时器
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)

    def enterEvent(self, event):
        if not self._is_loading and self.isEnabled():
            self._anim_shadow.setEndValue(15)
            self._anim_shadow.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self._is_loading:
            self._anim_shadow.setEndValue(0)
            self._anim_shadow.start()
        super().leaveEvent(event)

    def setText(self, text):
        super().setText(text)
        if not self._is_loading:
            self.original_text = text

    def set_loading_text(self, text: str):
        self._loading_text = text or LoadingText.DEFAULT

    def set_loading(self, loading: bool, text: str | None = None):
        self._is_loading = loading
        self.setEnabled(not loading)
        if loading:
            self._loading_text = text or self._loading_text or LoadingText.DEFAULT
            QPushButton.setText(self, f" {self._loading_text}")
            self._timer.start(50)
        else:
            QPushButton.setText(self, self.original_text)
            self._timer.stop()
            self.update()

    def _rotate(self):
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, event):
        from PySide6.QtCore import Qt

        super().paintEvent(event)
        if self._is_loading:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)

            # 绘制旋转的 Spinner
            s = min(self.width(), self.height()) - 16
            x = 10
            y = (self.height() - s) // 2

            painter.translate(x + s / 2, y + s / 2)
            painter.rotate(self._angle)
            painter.translate(-(x + s / 2), -(y + s / 2))

            pen = QPen(qcolor(ColorTokens.SURFACE_BASE), 2)
            painter.setPen(pen)
            painter.drawArc(int(x), int(y), int(s), int(s), 0, 300 * 16)


class ScaleButton(QPushButton):
    """具有点击缩放效果的按钮"""

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        from PySide6.QtCore import Qt

        self.setCursor(Qt.PointingHandCursor)
        self._animation = QPropertyAnimation(self, b"geometry")
        self._animation.setDuration(100)
        self._animation.setEasingCurve(QEasingCurve.OutQuad)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        # 缩小效果
        rect = self.geometry()
        self._orig_rect = rect
        shrink_w = int(rect.width() * 0.95)
        shrink_h = int(rect.height() * 0.95)
        x = rect.x() + (rect.width() - shrink_w) // 2
        y = rect.y() + (rect.height() - shrink_h) // 2
        self.setGeometry(x, y, shrink_w, shrink_h)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        # 恢复原状
        if hasattr(self, "_orig_rect"):
            self.setGeometry(self._orig_rect)
