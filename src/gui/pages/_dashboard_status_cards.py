"""Dashboard summary status cards — visual-aligned to D:/Kingdee/assets/概览.png.

Each card: 左侧自绘SVG风格图标(40x40圆角方块) + 右侧标题/大数值/趋势文案。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.gui.components.common import SvgIconLabel
from src.gui.components.page_shell import Win11SummaryCard
from src.gui.design_tokens import ColorTokens

_METRIC_ICON_FILES = {
    "trend": "metric_sync_count.svg",
    "shield": "metric_success_rate.svg",
    "cross": "metric_failed_task.svg",
    "warning": "metric_pending_warning.svg",
    "clock": "metric_avg_time.svg",
}


class DashboardSummaryCard(Win11SummaryCard):
    """Dashboard stat card — 左图标(自绘) + 右侧标题/大数值/趋势文案。"""

    def __init__(self, title: str, value: str = "--", subtitle: str = "",
                 icon_type: str = "trend", icon_color: str = "", parent=None):
        super().__init__(title=title, value=value, subtitle=subtitle, parent=parent)
        self.setFixedHeight(96)
        self.subtitle_label.setProperty("ui", "win11-helper-text")
        color = icon_color if icon_color else ColorTokens.ACCENT_600

        old_layout = self.layout()
        old_layout.setContentsMargins(18, 0, 16, 0)
        old_layout.setSpacing(0)
        for w in (self.title_label, self.value_label, self.subtitle_label):
            old_layout.removeWidget(w)
        # 移除旧 layout 中的 stretch
        while old_layout.count():
            item = old_layout.takeAt(0)
            if item and item.widget():
                item.widget().setParent(None)

        hbox = QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(14)

        self._icon = SvgIconLabel(
            _METRIC_ICON_FILES.get(icon_type, "metric_sync_count.svg"),
            size=48,
            icon_size=28,
            color=color,
        )
        self._icon.setProperty("ui", "dashboard-metric-icon")
        self._icon.setProperty("tone", icon_type)
        self._icon.setProperty("icon-color", color)
        hbox.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignVCenter)

        vbox = QVBoxLayout()
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        for w in (self.title_label, self.value_label, self.subtitle_label):
            vbox.addWidget(w)
        hbox.addLayout(vbox, 1)
        old_layout.addStretch(1)
        old_layout.addLayout(hbox)
        old_layout.addStretch(1)

    def set_data(self, value: str, subtitle: str | None = None, tone: str = "neutral") -> None:
        self.set_value(value)
        if subtitle is not None:
            self.subtitle_label.setText(subtitle or "")
            self.subtitle_label.setVisible(bool(subtitle))
        tone_map = {
            "positive": "win11-helper-text-success",
            "negative": "win11-helper-text-danger",
            "neutral": "win11-helper-text",
        }
        target_ui = tone_map.get(tone, "win11-helper-text")
        if self.subtitle_label.property("ui") != target_ui:
            self.subtitle_label.setProperty("ui", target_ui)
            style = self.subtitle_label.style()
            if style is not None:
                style.unpolish(self.subtitle_label)
                style.polish(self.subtitle_label)


class DashboardStatusCards:
    """5 个指标卡容器。"""

    def __init__(self) -> None:
        self.card_count = DashboardSummaryCard("今日同步次数", "--", "较昨日 —", icon_type="trend", icon_color=ColorTokens.ACCENT_600)
        self.card_rate = DashboardSummaryCard("成功率", "--", "较昨日 —", icon_type="shield", icon_color=ColorTokens.SUCCESS_GREEN)
        self.card_fail = DashboardSummaryCard("失败任务", "--", "较昨日 —", icon_type="cross", icon_color=ColorTokens.DANGER)
        self.card_pending = DashboardSummaryCard("待处理异常", "--", "较昨日 —", icon_type="warning", icon_color=ColorTokens.WARNING)
        self.card_duration = DashboardSummaryCard("平均耗时", "--", "较昨日 —", icon_type="clock", icon_color=ColorTokens.ACCENT_700)

    def add_to(self, page) -> None:
        for card in (self.card_count, self.card_rate, self.card_fail, self.card_pending, self.card_duration):
            page.add_summary_card(card)

    def update(self, *, task_count, task_count_sub, task_count_tone, records="", records_sub="", records_tone="neutral",
               rate, rate_sub, rate_tone, status="", status_sub="",
               fail_count="0", fail_count_sub="", fail_count_tone="neutral",
               pending_count="0", pending_count_sub="", pending_count_tone="neutral",
               avg_duration="--", avg_duration_sub="", avg_duration_tone="neutral") -> None:
        self.card_count.set_data(task_count, task_count_sub, task_count_tone)
        self.card_rate.set_data(rate, rate_sub, rate_tone)
        self.card_fail.set_data(fail_count, fail_count_sub, fail_count_tone)
        self.card_pending.set_data(pending_count, pending_count_sub, pending_count_tone)
        self.card_duration.set_data(avg_duration, avg_duration_sub, avg_duration_tone)
