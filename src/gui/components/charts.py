"""Chart components for dashboard pages."""

from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from src.gui.design_tokens import ChartTokens, ColorTokens, qcolor


class HorizontalBarChart(QWidget):
    """Horizontal bar chart used for ranked/volume data."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = []  # [{"name": "xx", "count": 100}]
        self.setMinimumHeight(200)

    def set_data(self, data):
        self.data = data or []
        self.update()

    def _draw_empty_state(self, painter: QPainter):
        painter.setPen(qcolor(ColorTokens.TEXT_DISABLED))
        painter.drawText(self.rect(), Qt.AlignCenter, "暂无图表数据")

    def paintEvent(self, event):
        if not self.data:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            self._draw_empty_state(painter)
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        n = len(self.data)
        if n == 0:
            return

        bar_height = 22
        gap = 18
        start_y = 8

        max_val = max([d.get("count", 0) for d in self.data]) if self.data else 1

        font = self.font()
        font.setPointSize(10)
        painter.setFont(font)

        for i, item in enumerate(self.data):
            y = start_y + i * (bar_height + gap)
            name = item.get("name", "Unknown")
            count = item.get("count", 0)

            rank_rect = QRect(0, y, 28, bar_height)
            painter.setPen(Qt.NoPen)
            painter.setBrush(qcolor(ColorTokens.BORDER_SUBTLE))
            painter.drawRoundedRect(rank_rect, 8, 8)
            painter.setPen(qcolor(ColorTokens.TEXT_MUTED))
            painter.drawText(rank_rect, Qt.AlignCenter, str(i + 1))

            painter.setPen(qcolor(ColorTokens.TEXT_SECONDARY))
            painter.drawText(40, y, 106, bar_height, Qt.AlignLeft | Qt.AlignVCenter, name)

            bar_x = 148
            bar_max_w = max(60, w - bar_x - 54)

            painter.setPen(Qt.NoPen)
            painter.setBrush(qcolor(ChartTokens.BAR_TRACK))
            painter.drawRoundedRect(bar_x, y + 5, bar_max_w, bar_height - 10, 5, 5)

            bar_w = (count / max_val) * bar_max_w if max_val > 0 else 0

            grad = QLinearGradient(bar_x, y, bar_x + max(bar_w, 1), y)
            grad.setColorAt(0, qcolor(ChartTokens.BAR_START))
            grad.setColorAt(1, qcolor(ChartTokens.BAR_END))
            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(bar_x, y + 4, bar_w, bar_height - 8, 4, 4)

            value_rect = QRect(w - 50, y, 50, bar_height)
            painter.setPen(qcolor(ColorTokens.TEXT_PRIMARY))
            painter.drawText(value_rect, Qt.AlignRight | Qt.AlignVCenter, str(count))


class SimpleLineChart(QWidget):
    """Line chart with optional alert threshold and point highlighting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = []
        self.setMinimumHeight(150)
        self.setMouseTracking(True)
        self.hover_pos = None
        self.alert_threshold = None
        self.alert_rate_key = "rate"

    def set_data(self, data):
        self.data = data or []
        self.update()

    def set_alert_threshold(self, threshold: float | None, rate_key: str = "rate"):
        if threshold is None:
            self.alert_threshold = None
        else:
            self.alert_threshold = max(0.0, min(float(threshold), 100.0))
        self.alert_rate_key = rate_key
        self.update()

    def _is_alert_point(self, item: dict) -> bool:
        if self.alert_threshold is None:
            return False
        try:
            rate = float(item.get(self.alert_rate_key, 100.0) or 0.0)
        except Exception:
            return False
        return rate < self.alert_threshold

    def mouseMoveEvent(self, event):
        self.hover_pos = event.pos()
        self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.hover_pos = None
        self.update()
        super().leaveEvent(event)

    def _draw_empty_state(self, painter: QPainter):
        painter.setPen(qcolor(ColorTokens.TEXT_DISABLED))
        painter.drawText(self.rect(), Qt.AlignCenter, "暂无趋势数据")

    def paintEvent(self, event):
        if not self.data:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            self._draw_empty_state(painter)
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        padding_left = 30
        padding_bottom = 25
        padding_top = 20
        padding_right = 20

        draw_w = w - padding_left - padding_right
        draw_h = h - padding_bottom - padding_top

        counts = [d.get("count", d.get("value", 0)) for d in self.data]
        if not counts:
            return
        max_val = max(counts) if max(counts) > 0 else 10

        painter.setPen(QPen(qcolor(ColorTokens.GRID_LINE), 1))
        for ratio in (0.25, 0.5, 0.75, 1.0):
            y = padding_top + draw_h - draw_h * ratio
            painter.drawLine(padding_left, int(y), w - padding_right, int(y))
            label_text = str(int(max_val * ratio))
            painter.setPen(qcolor(ColorTokens.TEXT_DISABLED))
            painter.drawText(0, int(y) - 8, padding_left - 6, 16, Qt.AlignRight | Qt.AlignVCenter, label_text)
            painter.setPen(QPen(qcolor(ColorTokens.GRID_LINE), 1))

        if self.alert_threshold is not None:
            threshold_ratio = max(0.0, min(self.alert_threshold / 100.0, 1.0))
            threshold_y = padding_top + draw_h - draw_h * threshold_ratio
            threshold_pen = QPen(qcolor(ColorTokens.DANGER), 1, Qt.DashLine)
            threshold_pen.setDashPattern([6, 4])
            painter.setPen(threshold_pen)
            painter.drawLine(padding_left, int(threshold_y), w - padding_right, int(threshold_y))
            painter.setPen(qcolor(ColorTokens.DANGER))
            painter.drawText(
                padding_left + 4,
                int(threshold_y) - 16,
                120,
                14,
                Qt.AlignLeft | Qt.AlignVCenter,
                f"阈值 {self.alert_threshold:.0f}%",
            )

        points = []
        n = len(self.data)
        step_x = draw_w / (n - 1) if n > 1 else draw_w

        for i, val in enumerate(counts):
            x = padding_left + i * step_x
            y = padding_top + draw_h - (val / max_val) * draw_h
            points.append(QPointF(x, y))

        if points:
            path_fill = QPainterPath()
            path_fill.moveTo(points[0])
            for p in points[1:]:
                path_fill.lineTo(p)
            path_fill.lineTo(points[-1].x(), padding_top + draw_h)
            path_fill.lineTo(points[0].x(), padding_top + draw_h)
            path_fill.closeSubpath()

            grad = QLinearGradient(0, padding_top, 0, padding_top + draw_h)
            grad.setColorAt(0, QColor(*ChartTokens.LINE_FILL_START))
            grad.setColorAt(1, QColor(*ChartTokens.LINE_FILL_END))

            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.NoPen)
            painter.drawPath(path_fill)

        path = QPainterPath()
        path.moveTo(points[0])
        for p in points[1:]:
            path.lineTo(p)

        painter.setPen(QPen(qcolor(ChartTokens.LINE), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

        closest_idx = -1
        min_dist = 9999
        if self.hover_pos:
            for i, p in enumerate(points):
                dist = abs(p.x() - self.hover_pos.x())
                if dist < min_dist:
                    min_dist = dist
                    closest_idx = i
            if min_dist > step_x / 2:
                closest_idx = -1

        for i, p in enumerate(points):
            is_alert = self._is_alert_point(self.data[i])
            radius = 5 if i == closest_idx else 3
            point_color = qcolor(ColorTokens.DANGER) if is_alert else qcolor(ChartTokens.LINE)

            painter.setPen(QPen(point_color, 2))
            painter.setBrush(QBrush(qcolor(ColorTokens.SURFACE_BASE)))
            if is_alert:
                painter.setBrush(QBrush(point_color))
            painter.drawEllipse(p, radius, radius)

            day_str = str(self.data[i].get("day", self.data[i].get("label", "")))
            if "-" in day_str:
                day_str = day_str.split("-")[-1]

            painter.setPen(qcolor(ColorTokens.DANGER) if is_alert else qcolor(ColorTokens.TEXT_DISABLED))
            painter.drawText(int(p.x()) - 20, h - 20, 40, 20, Qt.AlignCenter, day_str)

        if closest_idx != -1:
            p = points[closest_idx]
            count = counts[closest_idx]
            day = self.data[closest_idx].get("day", self.data[closest_idx].get("label", ""))
            rate = self.data[closest_idx].get(self.alert_rate_key)
            is_alert = self._is_alert_point(self.data[closest_idx])

            guide_color = qcolor(ColorTokens.DANGER) if is_alert else qcolor(ColorTokens.GRID_LINE)
            painter.setPen(QPen(guide_color, 1, Qt.DashLine))
            painter.drawLine(QPointF(p.x(), padding_top), QPointF(p.x(), padding_top + draw_h))

            tip_text = f"{day} / {count} 次"
            if rate is not None:
                try:
                    tip_text += f" / 成功率 {float(rate):.1f}%"
                except Exception:
                    pass
            tip_w = painter.fontMetrics().horizontalAdvance(tip_text) + 24
            tip_h = 28
            tip_x = p.x() - tip_w / 2
            tip_y = p.y() - 35

            if tip_x < 0:
                tip_x = 0
            if tip_x + tip_w > w:
                tip_x = w - tip_w

            painter.setBrush(QBrush(qcolor(ChartTokens.TOOLTIP_BG)))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(QRect(int(tip_x), int(tip_y), int(tip_w), int(tip_h)), 6, 6)

            painter.setPen(qcolor(ChartTokens.TOOLTIP_TEXT))
            painter.drawText(QRect(int(tip_x), int(tip_y), int(tip_w), int(tip_h)), Qt.AlignCenter, tip_text)


class SuccessRateBar(QWidget):
    """Success rate progress bar."""

    def __init__(self, rate: float, parent=None):
        super().__init__(parent)
        self.rate = rate
        self.setFixedHeight(24)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        painter.setBrush(QBrush(qcolor(ColorTokens.SURFACE_MUTED)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 6, w, 12, 6, 6)

        if self.rate >= 100:
            color = qcolor(ColorTokens.SUCCESS)
        elif self.rate >= 90:
            color = qcolor(ColorTokens.WARNING)
        else:
            color = qcolor(ColorTokens.DANGER)

        fill_w = (self.rate / 100.0) * w
        fill_w = min(fill_w, w)
        painter.setBrush(QBrush(color))
        painter.drawRoundedRect(0, 6, int(fill_w), 12, 6, 6)

        text = f"{self.rate:.1f}%"
        painter.setPen(qcolor(ColorTokens.TEXT_PRIMARY))
        painter.drawText(0, 0, w, h, Qt.AlignCenter, text)
