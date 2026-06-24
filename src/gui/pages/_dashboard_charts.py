"""Dashboard trend and volume charts component."""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from src.gui.components.charts import HorizontalBarChart, SimpleLineChart
from src.gui.components.page_shell import Win11SectionCard
from src.gui.design_tokens import SizeTokens, SpacingTokens


class DashboardCharts:
    """Trend chart + volume chart with range buttons.

    Does NOT call any service; data is pushed in via ``update_trend()``
    and ``update_volume()``.  Window-day changes are reported via the
    ``on_window_days_changed`` callback.
    """

    def __init__(self, success_alert_threshold: float = 95.0, on_window_days_changed: Callable[[int], None] | None = None) -> None:
        self._window_days = 7
        self._on_window_days_changed = on_window_days_changed

        # ── Trend card ──
        self.trend_card = Win11SectionCard("任务趋势", "")
        self._trend_title = self.trend_card.title_label
        self._trend_sub = self.trend_card.subtitle_label
        self._trend_sub.setVisible(True)

        trend_toolbar = QHBoxLayout()
        trend_toolbar.setSpacing(SpacingTokens.ACTION_BAR_GAP)
        trend_toolbar.addStretch()

        self.range_btn_7 = QPushButton("7天")
        self.range_btn_7.setProperty("class", "secondary")
        self.range_btn_7.setFixedHeight(SizeTokens.PAGINATION_BUTTON_HEIGHT)
        self.range_btn_7.clicked.connect(lambda: self._on_range_clicked(7))

        self.range_btn_30 = QPushButton("30天")
        self.range_btn_30.setProperty("class", "secondary")
        self.range_btn_30.setFixedHeight(SizeTokens.PAGINATION_BUTTON_HEIGHT)
        self.range_btn_30.clicked.connect(lambda: self._on_range_clicked(30))

        trend_toolbar.addWidget(self.range_btn_7)
        trend_toolbar.addWidget(self.range_btn_30)
        self.trend_card.content_layout.addLayout(trend_toolbar)

        self.trend_chart = SimpleLineChart()
        self.trend_chart.setMinimumHeight(SizeTokens.DASHBOARD_TREND_CHART_MIN_HEIGHT)
        self.trend_chart.set_alert_threshold(success_alert_threshold, rate_key="rate")
        self.trend_card.content_layout.addWidget(self.trend_chart)

        # ── Volume card ──
        self.volume_card = Win11SectionCard(
            "吞吐分布",
            "按日记录量有助于发现同步需求的突变。",
        )
        self._volume_title = self.volume_card.title_label
        self._volume_sub = self.volume_card.subtitle_label
        self.volume_chart = HorizontalBarChart()
        self.volume_chart.setMinimumHeight(SizeTokens.DASHBOARD_VOLUME_CHART_MIN_HEIGHT)
        self.volume_card.content_layout.addWidget(self.volume_chart)

    def _on_range_clicked(self, days: int) -> None:
        target = 30 if days >= 30 else 7
        if self._window_days == target:
            return
        self._window_days = target
        self._sync_range_ui()
        if self._on_window_days_changed:
            self._on_window_days_changed(target)

    def _sync_range_ui(self) -> None:
        days = self._window_days
        self._trend_title.setText(f"近{days}天任务趋势")
        self._trend_sub.setText("按日执行次数；当成功率低于目标阈值时会标注提醒。")
        self._volume_title.setText(f"近{days}天吞吐分布")
        self._volume_sub.setText("对比每日记录量，观察工作负载的变化。")
        self._set_range_btn_active(self.range_btn_7, days == 7)
        self._set_range_btn_active(self.range_btn_30, days == 30)

    @staticmethod
    def _set_range_btn_active(button: QPushButton, active: bool) -> None:
        button.setProperty("class", "primary" if active else "secondary")
        style = button.style()
        if style is not None:
            style.unpolish(button)
            style.polish(button)

    def sync_window_days(self, days: int) -> None:
        """Update range UI to match the given window days (called by page)."""
        self._window_days = days
        self._sync_range_ui()

    def update_trend(self, trend_data: list[dict]) -> None:
        """Push trend chart data."""
        chart_data = [
            {
                "day": item.get("day", ""),
                "count": item.get("count", 0),
                "rate": float(item.get("rate", 0.0) or 0.0),
            }
            for item in trend_data
        ]
        self.trend_chart.set_data(chart_data)

    def update_volume(self, trend_data: list[dict]) -> None:
        """Push volume chart data."""
        volume_source = trend_data[-10:] if self._window_days > 10 else trend_data
        volume_data = [
            {"name": item.get("day", ""), "count": item.get("volume", item.get("count", 0))}
            for item in volume_source
        ]
        self.volume_chart.set_data(volume_data)
