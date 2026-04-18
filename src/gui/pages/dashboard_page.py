"""Dashboard page built on the shared Windows 11 page scaffold."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from PySide6.QtCore import QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from src.core.history_manager import history_manager
from src.gui.components.buttons import LoadingButton
from src.gui.components.charts import HorizontalBarChart, SimpleLineChart
from src.gui.components.page_shell import Win11PageScaffold, Win11SectionCard, Win11SummaryCard
from src.gui.design_tokens import ColorTokens
from src.gui.ui_text import ButtonText, LoadingText
from src.services.reporting import get_dashboard_today_stats, get_top_forms_days, get_trend_days

logger = logging.getLogger(__name__)


class DashboardSummaryCard(Win11SummaryCard):
    """Dashboard stat card with colored trend subtitles."""

    def __init__(self, title: str, value: str = "--", subtitle: str = "", parent=None):
        super().__init__(title=title, value=value, subtitle=subtitle, parent=parent)
        self.subtitle_label.setProperty("ui", "win11-helper-text")

    def set_data(self, value: str, subtitle: str | None = None, tone: str = "neutral") -> None:
        self.set_value(value)
        if subtitle is not None:
            self.set_subtitle(subtitle)

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


class DonutGauge(QWidget):
    """Simple success-rate donut gauge."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.value = 0.0
        self.scope_days = 7
        self.setMinimumSize(220, 220)

    def set_value(self, value: float) -> None:
        self.value = max(0.0, min(float(value), 100.0))
        self.update()

    def set_scope_days(self, days: int) -> None:
        self.scope_days = max(int(days or 0), 1)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        side = min(self.width(), self.height()) - 28
        rect = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)

        track_pen = QPen(QColor(ColorTokens.STROKE_SUBTLE), 16)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawArc(rect, 0, 360 * 16)

        value_pen = QPen(QColor(ColorTokens.ACCENT_600), 16)
        value_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(value_pen)
        painter.drawArc(rect, 90 * 16, int(-self.value / 100 * 360 * 16))

        painter.setPen(QColor(ColorTokens.TEXT_PRIMARY))
        value_font = painter.font()
        value_font.setPointSize(22)
        value_font.setBold(True)
        painter.setFont(value_font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{self.value:.0f}%")

        sub_font = painter.font()
        sub_font.setPointSize(10)
        sub_font.setBold(False)
        painter.setFont(sub_font)
        painter.setPen(QColor(ColorTokens.TEXT_MUTED))
        sub_rect = QRectF(rect.x(), rect.center().y() + 16, rect.width(), 24)
        painter.drawText(sub_rect, Qt.AlignmentFlag.AlignCenter, f"最近{self.scope_days}天")


class InsightTable(Win11SectionCard):
    """Lightweight table card for top forms and recent failures."""

    def __init__(self, title: str, subtitle: str, headers: list[str], parent=None):
        super().__init__(title=title, subtitle=subtitle, parent=parent)
        self.table = QTableWidget(0, len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setProperty("ui", "win11-data-table")
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setMinimumSectionSize(60)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.content_layout.addWidget(self.table)

    def set_rows(self, rows: list[list[str]]) -> None:
        self.table.clearContents()
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for col_index, text in enumerate(row):
                item = QTableWidgetItem(text)
                if col_index == 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_index, col_index, item)


class DashboardPage(Win11PageScaffold):
    def __init__(self, parent_gui, parent=None):
        self.gui = parent_gui
        self._window_days = 7
        self._fail_rows_meta: list[dict] = []
        self._success_alert_threshold = 95.0
        self._responsive_splitters: list[tuple[QSplitter, list[int], list[int]]] = []
        super().__init__(
            title="运营总览",
            eyebrow="仪表盘",
            subtitle="在同一运营面板中查看同步健康度、吞吐量与失败队列。",
            parent=parent,
        )
        self.setProperty("page", "dashboard")
        self.setup_ui()
        QTimer.singleShot(100, self.refresh_dashboard)

    def setup_ui(self) -> None:
        self._build_hero()
        self._build_summary_strip()
        self.add_primary_action(self.refresh_btn)
        self.set_content(self._create_scroll_content())
        self._sync_window_scope_ui()
        self._apply_workspace_layout()

    def _build_hero(self) -> None:
        meta_widget = QWidget()
        meta_layout = QVBoxLayout(meta_widget)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(6)

        self.status_badge = QLabel("空闲")
        self.status_badge.setProperty("ui", "win11-status-chip")
        self.status_badge.setProperty("tone", "neutral")

        self.window_scope_badge = QLabel("")
        self.window_scope_badge.setProperty("ui", "win11-status-chip")
        self.window_scope_badge.setProperty("tone", "info")

        self.last_refresh_label = QLabel("上次刷新：--")
        self.last_refresh_label.setProperty("ui", "win11-meta-text")

        self.risk_tip_label = QLabel("健康提示：等待首次刷新。")
        self.risk_tip_label.setProperty("ui", "win11-meta-text")
        self.risk_tip_label.setProperty("tone", "neutral")
        self.risk_tip_label.setWordWrap(True)

        meta_layout.addWidget(self.status_badge, 0, Qt.AlignmentFlag.AlignLeft)
        meta_layout.addWidget(self.window_scope_badge, 0, Qt.AlignmentFlag.AlignLeft)
        meta_layout.addWidget(self.last_refresh_label)
        meta_layout.addWidget(self.risk_tip_label)

        self.refresh_btn = LoadingButton(ButtonText.REFRESH_DATA)
        self.refresh_btn.setProperty("class", "primary")
        self.refresh_btn.setFixedHeight(36)
        self.refresh_btn.clicked.connect(self.refresh_dashboard)

        self.add_hero_widget(meta_widget)

    def _build_summary_strip(self) -> None:
        self.card_count = DashboardSummaryCard("今日任务数", "--", "包含计划任务与手动同步执行。")
        self.card_records = DashboardSummaryCard("今日处理记录", "--", "今日插入与更新的记录总量。")
        self.card_rate = DashboardSummaryCard("今日成功率", "--", "今日同步任务的整体完成率。")
        self.card_status = DashboardSummaryCard("当前状态", "--", "当前整体运行与就绪情况。")

        for card in (self.card_count, self.card_records, self.card_rate, self.card_status):
            self.add_summary_card(card)

    def _create_scroll_content(self) -> QScrollArea:
        scroll = self.create_scroll_container("dashboard_scroll")

        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(16)

        self.overview_card = Win11SectionCard(
            "每日概览",
            "快速查看吞吐、风险与当前统计窗口。",
        )
        self.overview_text = QLabel(
            "本面板汇总同步量、稳定性与失败队列，便于快速定位需要处理的问题。"
        )
        self.overview_text.setWordWrap(True)
        self.overview_text.setProperty("ui", "win11-helper-text")
        self.overview_card.content_layout.addWidget(self.overview_text)
        page_layout.addWidget(self.overview_card)

        self.middle_splitter = self._register_splitter(
            self._create_middle_row(),
            compact_sizes=[500, 320],
            wide_sizes=[860, 520],
        )
        self.rank_splitter = self._register_splitter(
            self._create_rank_row(),
            compact_sizes=[320, 320],
            wide_sizes=[700, 700],
        )
        self.bottom_splitter = self._register_splitter(
            self._create_bottom_row(),
            compact_sizes=[320, 320],
            wide_sizes=[860, 520],
        )
        page_layout.addWidget(self.middle_splitter)
        page_layout.addWidget(self.rank_splitter)
        page_layout.addWidget(self.bottom_splitter)
        page_layout.addStretch(1)

        scroll.setWidget(page)
        return scroll

    def _register_splitter(self, splitter: QSplitter, *, compact_sizes: list[int], wide_sizes: list[int]) -> QSplitter:
        self._responsive_splitters.append((splitter, compact_sizes, wide_sizes))
        return splitter

    def _create_middle_row(self) -> QSplitter:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)
        splitter.setProperty("ui", "win11-page-splitter")

        trend_card = Win11SectionCard("任务趋势", "")
        self.trend_title = trend_card.title_label
        self.trend_sub = trend_card.subtitle_label
        self.trend_sub.setVisible(True)

        trend_toolbar = QHBoxLayout()
        trend_toolbar.setSpacing(10)
        trend_toolbar.addStretch()

        self.range_btn_7 = QPushButton("7天")
        self.range_btn_7.setProperty("class", "secondary")
        self.range_btn_7.setFixedHeight(34)
        self.range_btn_7.clicked.connect(lambda: self._set_window_days(7))

        self.range_btn_30 = QPushButton("30天")
        self.range_btn_30.setProperty("class", "secondary")
        self.range_btn_30.setFixedHeight(34)
        self.range_btn_30.clicked.connect(lambda: self._set_window_days(30))

        trend_toolbar.addWidget(self.range_btn_7)
        trend_toolbar.addWidget(self.range_btn_30)
        trend_card.content_layout.addLayout(trend_toolbar)

        self.trend_chart = SimpleLineChart()
        self.trend_chart.setMinimumHeight(300)
        self.trend_chart.set_alert_threshold(self._success_alert_threshold, rate_key="rate")
        trend_card.content_layout.addWidget(self.trend_chart)
        splitter.addWidget(trend_card)

        gauge_card = Win11SectionCard(
            "成功率概览",
            "所选统计窗口的直观提示。",
        )
        self.success_gauge = DonutGauge()
        self.gauge_meta = QLabel("最近7天失败数：0")
        self.gauge_meta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gauge_meta.setProperty("ui", "win11-helper-text")
        gauge_card.content_layout.addWidget(self.success_gauge, 1)
        gauge_card.content_layout.addWidget(self.gauge_meta)
        splitter.addWidget(gauge_card)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([860, 520])
        return splitter

    def _create_rank_row(self) -> QSplitter:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)
        splitter.setProperty("ui", "win11-page-splitter")

        self.top_forms_table = InsightTable(
            "表单活跃度排行",
            "当前统计窗口内最活跃的表单。",
            ["排名", "表单", "执行次数", "成功率"],
        )
        self.fail_table = InsightTable(
            "近期失败",
            "点击行可跳转到历史记录并应用快捷筛选。",
            ["时间", "表单", "状态", "摘要"],
        )
        self.fail_table.table.cellClicked.connect(self._on_fail_row_clicked)

        splitter.addWidget(self.top_forms_table)
        splitter.addWidget(self.fail_table)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([700, 700])
        return splitter

    def _create_bottom_row(self) -> QSplitter:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)
        splitter.setProperty("ui", "win11-page-splitter")

        volume_card = Win11SectionCard(
            "吞吐分布",
            "按日记录量有助于发现同步需求的突变。",
        )
        self.volume_title = volume_card.title_label
        self.volume_sub = volume_card.subtitle_label
        self.volume_chart = HorizontalBarChart()
        self.volume_chart.setMinimumHeight(240)
        volume_card.content_layout.addWidget(self.volume_chart)
        splitter.addWidget(volume_card)

        summary_card = Win11SectionCard(
            "关键指标",
            "所选统计窗口的汇总读数。",
        )
        self.summary_metrics: list[QLabel] = []
        self.summary_labels: list[QLabel] = []
        for label_text in (
            "总吞吐量",
            "成功次数",
            "失败次数",
            "最活跃表单",
        ):
            item = QFrame()
            item.setProperty("ui", "win11-inline-card")
            item_layout = QVBoxLayout(item)
            item_layout.setContentsMargins(12, 12, 12, 12)
            item_layout.setSpacing(4)

            label = QLabel(label_text)
            label.setProperty("ui", "win11-inline-title")
            value = QLabel("--")
            value.setProperty("ui", "win11-inline-value")

            item_layout.addWidget(label)
            item_layout.addWidget(value)
            summary_card.content_layout.addWidget(item)

            self.summary_labels.append(label)
            self.summary_metrics.append(value)

        summary_card.content_layout.addStretch(1)
        splitter.addWidget(summary_card)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([860, 520])
        return splitter

    def _sync_window_scope_ui(self) -> None:
        days = self._window_days
        self.window_scope_badge.setText(f"近{days}天")
        self.trend_title.setText(f"近{days}天任务趋势")
        self.trend_sub.setText("按日执行次数；当成功率低于目标阈值时会标注提醒。")
        self.top_forms_table.set_subtitle(f"最近{days}天内最活跃的表单。")
        self.volume_title.setText(f"近{days}天吞吐分布")
        self.volume_sub.setText("对比每日记录量，观察工作负载的变化。")
        self.summary_labels[0].setText(f"总吞吐量（{days}天）")
        self.summary_labels[1].setText(f"成功次数（{days}天）")
        self.summary_labels[2].setText(f"失败次数（{days}天）")
        self.success_gauge.set_scope_days(days)
        self._set_range_btn_active(self.range_btn_7, days == 7)
        self._set_range_btn_active(self.range_btn_30, days == 30)

    def _set_range_btn_active(self, button: QPushButton, active: bool) -> None:
        button.setProperty("class", "primary" if active else "secondary")
        style = button.style()
        if style is not None:
            style.unpolish(button)
            style.polish(button)

    def _set_window_days(self, days: int) -> None:
        target_days = 30 if int(days) >= 30 else 7
        if self._window_days == target_days:
            return
        self._window_days = target_days
        self._sync_window_scope_ui()
        self.refresh_dashboard()

    def _apply_workspace_layout(self) -> None:
        compact = self.width() <= 1366
        for splitter, compact_sizes, wide_sizes in self._responsive_splitters:
            splitter.setOrientation(Qt.Orientation.Vertical if compact else Qt.Orientation.Horizontal)
            splitter.setSizes(compact_sizes if compact else wide_sizes)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._apply_workspace_layout()
        super().resizeEvent(event)

    def _on_fail_row_clicked(self, row: int, _column: int) -> None:
        if row < 0 or row >= len(self._fail_rows_meta):
            return

        record = self._fail_rows_meta[row]
        form_name = str(record.get("form_name", record.get("table_name", "")) or "").strip()
        status = str(record.get("status") or "").strip()
        if status not in ("failed", "partial"):
            status = "failed"

        if hasattr(self.gui, "switch_to_page"):
            self.gui.switch_to_page("history")
        history_page = getattr(self.gui, "pages", {}).get("history") if hasattr(self.gui, "pages") else None
        if history_page is not None and hasattr(history_page, "apply_quick_filter"):
            history_page.apply_quick_filter(days=self._window_days, status=status, form_name=form_name or None)

    def refresh_dashboard(self) -> None:
        try:
            self.refresh_btn.set_loading(True, LoadingText.REFRESH)
            stats = get_dashboard_today_stats()
            trend_data = get_trend_days(self._window_days)
            top_forms = get_top_forms_days(6, self._window_days)

            now = datetime.now()
            start_date = (now - timedelta(days=self._window_days - 1)).strftime("%Y-%m-%d") + " 00:00:00"
            end_date = now.strftime("%Y-%m-%d") + " 23:59:59"
            fail_records, _ = history_manager.get_history(
                page=1,
                page_size=6,
                start_date=start_date,
                end_date=end_date,
                status=("failed", "partial"),
            )

            sync_count = int(stats.get("sync_count", 0) or 0)
            sync_records = int(stats.get("sync_records", 0) or 0)
            success_rate = float(stats.get("success_rate", 0.0) or 0.0)
            yday_count = int(stats.get("yday_count", 0) or 0)
            yday_records = int(stats.get("yday_records", 0) or 0)
            yday_rate = float(stats.get("yday_rate", 0.0) or 0.0)

            today_success = int(round(sync_count * (success_rate / 100.0)))
            today_fail = max(sync_count - today_success, 0)
            is_running = bool(getattr(self.gui, "sync_running", False))

            if is_running:
                status_text = "运行中"
                status_tone = "info"
                risk_text = "健康提示：同步正在执行，请关注实时日志与失败队列。"
                risk_tone = "info"
            elif sync_count == 0:
                status_text = "空闲"
                status_tone = "neutral"
                risk_text = "健康提示：今日尚无同步执行。"
                risk_tone = "neutral"
            elif today_fail > 0 or success_rate < 95.0:
                status_text = "需关注"
                status_tone = "danger"
                risk_text = f"健康提示：今日有 {today_fail} 次失败/部分成功，需要尽快处理。"
                risk_tone = "danger"
            else:
                status_text = "健康"
                status_tone = "success"
                risk_text = "健康提示：同步链路当前稳定。"
                risk_tone = "success"

            self._set_chip(self.status_badge, status_text, status_tone)
            self._set_meta_tone(self.risk_tip_label, risk_text, risk_tone)
            self.last_refresh_label.setText(datetime.now().strftime("上次刷新：%Y-%m-%d %H:%M:%S"))
            self.overview_text.setText(
                f"今日已执行 {sync_count} 次任务，处理 {sync_records:,} 条记录，成功率 {success_rate:.1f}%。"
                "可结合下方趋势与失败队列决定优先处理项。"
            )

            self.card_count.set_data(str(sync_count), *self._build_compare_text(sync_count, yday_count, "次"))
            self.card_records.set_data(
                f"{sync_records:,}",
                *self._build_compare_text(sync_records, yday_records, "条"),
            )
            self.card_rate.set_data(f"{success_rate:.1f}%", *self._build_compare_text(success_rate, yday_rate, "%"))

            if is_running:
                status_subtitle = "同步任务正在执行。"
            elif today_fail > 0:
                status_subtitle = "下一轮开始前建议先复核失败与部分成功任务。"
            else:
                status_subtitle = "系统已就绪，可开始下一轮同步。"
            self.card_status.set_data("运行中" if is_running else "空闲", status_subtitle)

            self.success_gauge.set_value(success_rate)
            total_tasks_scope = sum(int(item.get("count", 0) or 0) for item in trend_data)
            total_success_scope = sum(
                int(round((float(item.get("rate", 0.0) or 0.0) / 100.0) * int(item.get("count", 0) or 0)))
                for item in trend_data
            )
            fail_count_scope = max(total_tasks_scope - total_success_scope, 0)
            self.gauge_meta.setText(f"最近{self._window_days}天失败数：{fail_count_scope}")

            chart_data = [
                {
                    "day": item.get("day", ""),
                    "count": item.get("count", 0),
                    "rate": float(item.get("rate", 0.0) or 0.0),
                }
                for item in trend_data
            ]
            self.trend_chart.set_data(chart_data)

            volume_source = trend_data[-10:] if self._window_days > 10 else trend_data
            volume_data = [
                {"name": item.get("day", ""), "count": item.get("volume", item.get("count", 0))}
                for item in volume_source
            ]
            self.volume_chart.set_data(volume_data)

            top_rows = []
            for idx, item in enumerate(top_forms, start=1):
                top_rows.append(
                    [
                        str(idx),
                        str(item.get("name", "--")),
                        str(item.get("count", 0)),
                        f"{float(item.get('rate', 0)):.1f}%",
                    ]
                )
            if not top_rows:
                top_rows = [["-", "暂无数据", "-", "-"]]
            self.top_forms_table.set_rows(top_rows)

            fail_rows = []
            for record in fail_records:
                status_text = "部分成功" if record.get("status") == "partial" else "失败"
                fail_rows.append(
                    [
                        (record.get("start_time_str", "--") or "--")[-8:],
                        str(record.get("form_name", record.get("table_name", "--"))),
                        status_text,
                        str(record.get("message", "无详情"))[:24],
                    ]
                )
            if not fail_rows:
                fail_rows = [["--", "无失败", "--", "所选窗口内暂无失败记录。"]]
                self._fail_rows_meta = []
            else:
                self._fail_rows_meta = list(fail_records)[: len(fail_rows)]
            self.fail_table.set_rows(fail_rows)

            total_volume = sum(int(item.get("volume", 0) or 0) for item in trend_data)
            self.summary_metrics[0].setText(f"{total_volume:,}")
            self.summary_metrics[1].setText(str(total_success_scope))
            self.summary_metrics[2].setText(str(fail_count_scope))
            self.summary_metrics[3].setText(str(top_forms[0].get("name", "--")) if top_forms else "--")
        except Exception as exc:  # pragma: no cover - defensive UI guard
            logger.error("Dashboard refresh failed: %s", exc)
            self.overview_text.setText(f"仪表盘刷新失败：{exc}")
            self._set_chip(self.status_badge, "错误", "danger")
            self._set_meta_tone(
                self.risk_tip_label,
                "健康提示：仪表盘刷新失败，请检查数据库连接或查看应用日志。",
                "danger",
            )
        finally:
            self.refresh_btn.set_loading(False)

    def _set_chip(self, widget: QLabel, text: str, tone: str) -> None:
        widget.setText(text)
        widget.setProperty("tone", tone)
        style = widget.style()
        if style is not None:
            style.unpolish(widget)
            style.polish(widget)

    def _set_meta_tone(self, widget: QLabel, text: str, tone: str) -> None:
        widget.setText(text)
        widget.setProperty("tone", tone)
        style = widget.style()
        if style is not None:
            style.unpolish(widget)
            style.polish(widget)

    def _build_compare_text(self, current, previous, unit: str) -> tuple[str, str]:
        if not previous:
            return "暂无可对比的上一周期数据。", "neutral"

        diff = current - previous
        ratio = abs(diff / previous * 100) if previous else 0
        delta = f"{abs(diff):.1f}{unit}" if unit == "%" else f"{abs(diff):,.0f}{unit}"
        if diff > 0:
            return f"较昨日上升 {ratio:.1f}%（+{delta}）。", "positive"
        if diff < 0:
            return f"较昨日下降 {ratio:.1f}%（-{delta}）。", "negative"
        return "与昨日持平。", "neutral"
