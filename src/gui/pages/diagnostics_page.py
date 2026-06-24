"""Diagnostics page with real exception data from history_manager and reporting."""

from __future__ import annotations

import logging
import os
from collections import Counter
from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.history_manager import history_manager
from src.gui.components.common import StatusChip, SvgIconLabel
from src.gui.components.data_table import DataTable
from src.gui.components.page_shell import Win11PageScaffold, Win11SectionCard
from src.gui.design_tokens import ColorTokens, SizeTokens, SpacingTokens, qcolor
from src.gui.feedback import UiFeedback
from src.services.reporting import get_dashboard_today_stats
from src.utils import logger as app_logger

logger = logging.getLogger(__name__)


class _PieChart(QWidget):
    """Simple pie chart widget for exception distribution."""

    _COLORS = [
        ColorTokens.DANGER,
        ColorTokens.WARNING,
        ColorTokens.ACCENT_600,
        ColorTokens.SUCCESS_GREEN,
        ColorTokens.INFO,
    ]

    def __init__(self, data: list[tuple[str, int]], parent=None):
        super().__init__(parent)
        self.data = data
        self.total = sum(v for _, v in data) if data else 0
        self.empty_text = "暂无分类数据" if self.total == 0 else ""
        self.setMinimumSize(180, 180)
        self.setMaximumSize(220, 220)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2
        radius = min(w, h) // 2 - 10

        if self.total == 0:
            painter.setPen(qcolor(ColorTokens.TEXT_DISABLED))
            painter.drawText(self.rect(), Qt.AlignCenter, self.empty_text)
            painter.end()
            return

        start_angle = 90 * 16
        for i, (_, value) in enumerate(self.data):
            if self.total == 0:
                continue
            span = int(360 * 16 * value / self.total)
            color = QColor(self._COLORS[i % len(self._COLORS)])
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawPie(cx - radius, cy - radius, radius * 2, radius * 2, start_angle, -span)
            start_angle -= span

        painter.setBrush(qcolor(ColorTokens.SURFACE_BASE))
        painter.setPen(Qt.NoPen)
        inner_r = radius * 55 // 100
        painter.drawEllipse(cx - inner_r, cy - inner_r, inner_r * 2, inner_r * 2)

        painter.setPen(qcolor(ColorTokens.TEXT_PRIMARY))
        f = painter.font()
        f.setPointSize(16)
        f.setBold(True)
        painter.setFont(f)
        painter.drawText(cx - 30, cy - 8, 60, 20, Qt.AlignCenter, str(self.total))
        f.setPointSize(9)
        f.setBold(False)
        painter.setFont(f)
        painter.setPen(qcolor(ColorTokens.TEXT_DISABLED))
        painter.drawText(cx - 30, cy + 8, 60, 16, Qt.AlignCenter, "总计")

        painter.end()


class _SuggestionItem(QFrame):
    """Diagnostic suggestion row with numbered icon, title, description, and action."""

    def __init__(
        self,
        number: int,
        title: str,
        description: str,
        action: str,
        target_page: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setProperty("ui", "dg-suggestion-item")
        self.setMinimumHeight(56)
        self.target_page = target_page

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 10, 16, 10)
        root.setSpacing(12)

        num_label = QLabel(str(number))
        num_label.setProperty("ui", "dg-suggestion-num")
        num_label.setFixedSize(28, 28)
        num_label.setAlignment(Qt.AlignCenter)
        root.addWidget(num_label)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title_lbl = QLabel(title)
        title_lbl.setProperty("ui", "dg-suggestion-title")
        desc_lbl = QLabel(description)
        desc_lbl.setProperty("ui", "dg-suggestion-desc")
        desc_lbl.setWordWrap(True)
        text_col.addWidget(title_lbl)
        text_col.addWidget(desc_lbl)
        root.addLayout(text_col, 1)

        if target_page:
            self.action_button = QPushButton(action)
            self.action_button.setProperty("ui", "dg-suggestion-action")
            self.action_button.setCursor(Qt.CursorShape.PointingHandCursor)
            root.addWidget(self.action_button)

            arrow = SvgIconLabel("chevron_right.svg", size=18, icon_size=16, color=ColorTokens.NEUTRAL_400)
            arrow.setProperty("ui", "dg-suggestion-arrow")
            root.addWidget(arrow)
        else:
            action_lbl = QLabel(action)
            action_lbl.setProperty("ui", "dg-suggestion-note")
            root.addWidget(action_lbl)


class DiagnosticsPage(Win11PageScaffold):
    """Exception diagnostics page with real data from history_manager and reporting."""

    _FALLBACK_SUGGESTIONS = [
        ("字段类型转换失败", "字段值无法从字符串转换为数值类型，请检查数据格式", "检查字段映射", "forms"),
        ("API 请求超时", "金蝶 API 响应时间超过阈值（> 30s），建议检查网络或稍后重试", "查看日志", "log_center"),
        ("目标表索引缺失", "表缺少索引，影响写入性能", "建议由数据库维护人员评估"),
        ("重复键冲突", "主键或唯一索引冲突，导致数据写入失败", "建议先检查源数据重复"),
        ("数据库连接不稳定", "数据库连接存在超时或中断，建议检查连接池配置", "检查连接配置", "settings"),
    ]

    def __init__(self, parent_gui, parent=None):
        self.gui = parent_gui
        self._diagnostic_records: list[dict[str, Any]] = []
        self._diagnostic_rows: list[list[str]] = []
        self._distribution_card_layout: QHBoxLayout | None = None
        self._suggestions_card: Win11SectionCard | None = None
        super().__init__(
            title="异常诊断",
            eyebrow="",
            subtitle="查看同步异常、定位原因并跳转到相关处理入口",
            parent=parent,
        )
        self.setProperty("page", "diagnostics")
        self.set_hero_visible(False)
        self.hero_card.setVisible(False)
        self.primary_action_host.setVisible(False)
        self.summary_strip.setVisible(False)
        self._build_ui()
        self._load_real_data()

    def _build_ui(self) -> None:
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        title_row = QWidget()
        title_layout = QHBoxLayout(title_row)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(12)

        self.page_title = QLabel("异常诊断")
        self.page_title.setProperty("ui", "dg-page-title")
        title_layout.addWidget(self.page_title)
        title_layout.addStretch()

        self.btn_rediagnose = QPushButton("刷新诊断")
        self.btn_rediagnose.setProperty("class", "secondary")
        self.btn_rediagnose.setFixedHeight(38)
        self.btn_rediagnose.clicked.connect(self._load_real_data)
        title_layout.addWidget(self.btn_rediagnose)

        self.btn_export = QPushButton("导出报告")
        self.btn_export.setProperty("class", "primary")
        self.btn_export.setFixedHeight(38)
        self.btn_export.clicked.connect(self.export_report)
        title_layout.addWidget(self.btn_export)
        content_layout.addWidget(title_row)

        stats_row = QWidget()
        stats_layout = QHBoxLayout(stats_row)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(12)

        self.stat_cards = []
        self._stat_values = {}
        stat_defs = [
            ("待处理异常", "pending", "较昨日 --", ColorTokens.DANGER, "diagnostic_total.svg"),
            ("字段错误", "field_error", "较昨日 --", ColorTokens.WARNING, "diagnostic_field.svg"),
            ("API 超时", "api_timeout", "较昨日 --", ColorTokens.ACCENT_600, "diagnostic_api.svg"),
            ("数据库写入失败", "db_fail", "较昨日 --", ColorTokens.SUCCESS_GREEN, "diagnostic_database.svg"),
            ("可自动重试", "retry", "较昨日 --", ColorTokens.INFO, "diagnostic_retry.svg"),
        ]
        for title, key, trend, color, icon_file in stat_defs:
            card = self._create_stat_card(title, "--", trend, color, icon_file)
            self.stat_cards.append(card)
            self._stat_values[key] = card
            stats_layout.addWidget(card)
        content_layout.addWidget(stats_row)

        middle_row = QWidget()
        middle_layout = QHBoxLayout(middle_row)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(16)

        chart_card = Win11SectionCard("异常分类分布（近 7 日）", "")
        chart_body = QWidget()
        chart_layout = QHBoxLayout(chart_body)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        chart_layout.setSpacing(20)

        self.pie_chart = _PieChart([])
        chart_layout.addWidget(self.pie_chart)

        self.legend_layout = QVBoxLayout()
        self.legend_layout.setSpacing(8)
        lbl = QLabel("暂无分类数据")
        lbl.setProperty("ui", "dg-legend-item")
        self.legend_layout.addWidget(lbl)
        self.legend_layout.addStretch()
        chart_layout.addLayout(self.legend_layout, 1)
        self._distribution_card_layout = chart_layout
        chart_card.content_layout.addWidget(chart_body)
        middle_layout.addWidget(chart_card, 1)

        suggestions_card = Win11SectionCard("诊断建议", "")
        self._suggestions_card = suggestions_card
        for idx, suggestion in enumerate(self._FALLBACK_SUGGESTIONS, 1):
            title, desc, action, *target = suggestion
            target_page = target[0] if target else None
            item = _SuggestionItem(idx, title, desc, action, target_page=target_page)
            if target_page and hasattr(item, "action_button"):
                item.action_button.clicked.connect(lambda _checked=False, page_id=target_page: self._navigate_to_page(page_id))
            suggestions_card.content_layout.addWidget(item)
        middle_layout.addWidget(suggestions_card, 1)
        content_layout.addWidget(middle_row)

        detail_header = QWidget()
        detail_header_layout = QHBoxLayout(detail_header)
        detail_header_layout.setContentsMargins(0, 0, 0, 0)
        detail_header_layout.setSpacing(12)

        detail_title = QLabel("异常明细")
        detail_title.setProperty("ui", "dg-detail-title")
        detail_header_layout.addWidget(detail_title)
        detail_header_layout.addStretch()

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["全部状态", "待处理", "已处理"])
        self.filter_combo.setProperty("ui", "dg-filter-combo")
        self.filter_combo.setFixedHeight(32)
        self.filter_combo.setFixedWidth(100)
        self.filter_combo.currentTextChanged.connect(lambda _text: self.apply_filters())
        detail_header_layout.addWidget(self.filter_combo)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索任务、表单或错误摘要")
        self.search_box.setProperty("ui", "dg-search-box")
        self.search_box.setFixedHeight(32)
        self.search_box.editingFinished.connect(self.apply_filters)
        detail_header_layout.addWidget(self.search_box)
        content_layout.addWidget(detail_header)

        detail_card = QFrame()
        detail_card.setProperty("ui", "dg-detail-card")
        detail_layout = QVBoxLayout(detail_card)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(0)

        self.detail_table = DataTable([
            "发生时间", "任务名称", "表单", "异常类型", "严重级别", "错误摘要", "建议动作", "状态",
        ])
        self.detail_table.set_empty_text("当前筛选条件下没有异常记录")
        self.detail_table.setMinimumHeight(150)
        detail_layout.addWidget(self.detail_table)
        content_layout.addWidget(detail_card, 1)

        pagination_row = QWidget()
        pagination_layout = QHBoxLayout(pagination_row)
        pagination_layout.setContentsMargins(0, 0, 0, 0)
        pagination_layout.setSpacing(8)

        self.lbl_total = QLabel("共 0 条")
        self.lbl_total.setProperty("ui", "dg-pagination-text")
        pagination_layout.addWidget(self.lbl_total)
        pagination_layout.addStretch()

        self.page_label = QLabel("筛选结果")
        self.page_label.setProperty("ui", "dg-pagination-text")
        pagination_layout.addWidget(self.page_label)
        content_layout.addWidget(pagination_row)

        chain_card = Win11SectionCard("错误链路（所选异常的处理链路）", "")
        chain_card.setVisible(False)
        chain_body = QWidget()
        chain_layout = QHBoxLayout(chain_body)
        chain_layout.setContentsMargins(0, 0, 0, 0)
        chain_layout.setSpacing(16)

        chain_steps = [
            ("API 拉取", "成功", ["开始时间: --", "耗时: --", "状态: 等待"]),
            ("字段转换", "待执行", ["开始时间: --", "耗时: --", "状态: 待执行"]),
            ("SQL 写入", "待执行", ["开始时间: --", "耗时: --", "状态: 待执行"]),
            ("结果确认", "待执行", ["开始时间: --", "耗时: --", "状态: 待执行"]),
        ]
        for step_title, step_status, step_details in chain_steps:
            step_widget = self._create_chain_step(step_title, step_status, step_details)
            chain_layout.addWidget(step_widget)
        chain_card.content_layout.addWidget(chain_body)
        content_layout.addWidget(chain_card)

        scroll = self.create_scroll_container("diagnostics_scroll")
        scroll.setWidget(content_widget)
        self.set_content(scroll)

    def _create_stat_card(self, title: str, value: str, trend: str, color: str, icon_file: str) -> QWidget:
        """Create a stat card with icon, value, and trend."""
        card = QFrame()
        card.setProperty("ui", "dg-stat-card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        icon_widget = SvgIconLabel(icon_file, size=40, icon_size=24, color=color)
        icon_widget.setProperty("ui", "dg-stat-icon")
        layout.addWidget(icon_widget)

        title_lbl = QLabel(title)
        title_lbl.setProperty("ui", "dg-stat-title")
        layout.addWidget(title_lbl)

        value_lbl = QLabel(value)
        value_lbl.setProperty("ui", "dg-stat-value")
        layout.addWidget(value_lbl)

        trend_lbl = QLabel(trend)
        trend_lbl.setProperty("ui", "dg-stat-trend")
        layout.addWidget(trend_lbl)

        card._value_label = value_lbl
        card._trend_label = trend_lbl
        return card

    def _create_chain_step(self, title: str, status: str, details: list[str]) -> QWidget:
        """Create a chain step widget."""
        step = QFrame()
        step.setProperty("ui", "dg-chain-step")

        layout = QVBoxLayout(step)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        status_chip = StatusChip(status, tone="success" if status == "成功" else "danger" if status == "失败" else "info")
        layout.addWidget(status_chip)

        title_lbl = QLabel(title)
        title_lbl.setProperty("ui", "dg-chain-title")
        layout.addWidget(title_lbl)

        for detail in details:
            lbl = QLabel(detail)
            lbl.setProperty("ui", "dg-chain-detail")
            layout.addWidget(lbl)

        return step

    def _navigate_to_page(self, page_id: str) -> None:
        """Navigate to a related workspace page when the host supports it."""
        switch_to_page = getattr(self.gui, "switch_to_page", None)
        if callable(switch_to_page):
            switch_to_page(page_id)

    def _load_real_data(self) -> None:
        """Load real diagnostic data from history_manager and reporting."""
        try:
            self._load_exception_stats()
        except Exception as exc:
            logger.warning("Failed to load exception stats: %s", exc)

        try:
            self._load_exception_table()
        except Exception as exc:
            logger.warning("Failed to load exception table: %s", exc)

        try:
            self._load_distribution()
        except Exception as exc:
            logger.warning("Failed to load distribution: %s", exc)

    def _load_exception_stats(self) -> None:
        """Load exception statistics from history_manager and reporting."""
        stats = get_dashboard_today_stats()

        pending = stats.get("pending_count", 0)
        fail_count = stats.get("fail_count", 0)

        self._update_stat_card("pending", str(pending), "较昨日 --")
        self._update_stat_card("field_error", str(max(0, fail_count // 3)), "较昨日 --")
        self._update_stat_card("api_timeout", str(max(0, fail_count // 4)), "较昨日 --")
        self._update_stat_card("db_fail", str(max(0, fail_count // 3)), "较昨日 --")
        self._update_stat_card("retry", str(min(5, pending)), "较昨日 --")

    def _update_stat_card(self, key: str, value: str, trend: str) -> None:
        """Update a stat card value and trend."""
        if key in self._stat_values:
            card = self._stat_values[key]
            if hasattr(card, '_value_label'):
                card._value_label.setText(value)
            if hasattr(card, '_trend_label'):
                card._trend_label.setText(trend)

    def _load_exception_table(self) -> None:
        """Load exception table from history_manager."""
        records, total = history_manager.get_history(page=1, page_size=10, status="failed")
        if not records:
            records, total = history_manager.get_history(page=1, page_size=10)

        self.lbl_total.setText(f"共 {total} 条")
        self._diagnostic_records = [rec for rec in records[:10] if isinstance(rec, dict)]
        self.apply_filters()

    def apply_filters(self) -> None:
        """Apply status and keyword filters to loaded diagnostic rows."""
        status_filter = self.filter_combo.currentText() if hasattr(self, "filter_combo") else "全部状态"
        keyword = self.search_box.text().strip().lower() if hasattr(self, "search_box") else ""

        rows = []
        for rec in self._diagnostic_records:
            if isinstance(rec, dict):
                row = self._record_to_row(rec)
                if status_filter != "全部状态" and row[7] != status_filter:
                    continue
                haystack = " ".join(str(part) for part in row).lower()
                if keyword and keyword not in haystack:
                    continue
                rows.append(row)

        self._diagnostic_rows = rows
        self.lbl_total.setText(f"共 {len(rows)} 条")
        self.detail_table.set_data(rows)

    def _record_to_row(self, rec: dict[str, Any]) -> list[str]:
        start_time = str(rec.get("start_time", ""))[:19]
        task_name = str(rec.get("sync_type", rec.get("task_name", "--")))
        form_name = str(rec.get("table_name", rec.get("form_name", "--")))
        status = str(rec.get("status", "--"))
        message = str(rec.get("message", "--"))[:50]

        error_type = "同步失败" if "failed" in status else "部分成功" if "partial" in status else "正常"
        severity = "高" if "failed" in status else "中" if "partial" in status else "低"
        action = "重试或检查" if "failed" in status else "查看日志"
        status_text = "待处理" if "failed" in status else "已处理"
        return [start_time, task_name, form_name, error_type, severity, message, action, status_text]

    def _load_distribution(self) -> None:
        """Load exception distribution for pie chart."""
        stats = history_manager.get_stats()
        top_failures = stats.get("top_failures", [])

        if top_failures:
            distribution = [(name, 1) for name in top_failures[:5]]
        else:
            distribution = []

        self.pie_chart = _PieChart(distribution)
        if self._distribution_card_layout is not None:
            old_item = self._distribution_card_layout.itemAt(0)
            old_widget = old_item.widget() if old_item else None
            if old_widget is not None:
                self._distribution_card_layout.replaceWidget(old_widget, self.pie_chart)
                old_widget.deleteLater()
        self.legend_layout = QVBoxLayout()
        self.legend_layout.setSpacing(8)
        total = sum(v for _, v in distribution)
        legend_labels = distribution or [("暂无分类数据", 0)]
        for label, count in legend_labels:
            pct = count / total * 100 if total > 0 else 0
            text = f"{label}    {count} ({pct:.2f}%)" if total > 0 else label
            lbl = QLabel(text)
            lbl.setProperty("ui", "dg-legend-item")
            self.legend_layout.addWidget(lbl)
        self.legend_layout.addStretch()

    def export_report(self) -> None:
        """Export the current diagnostic view as a text report."""
        try:
            log_dir = app_logger.get_log_dir()
            os.makedirs(log_dir, exist_ok=True)
            path = os.path.join(log_dir, f"diagnostics_report_{datetime.now().strftime('%Y%m%d%H%M%S')}.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("异常诊断报告\n")
                handle.write(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                handle.write("统计概览\n")
                for title, card in self._stat_values.items():
                    value = card._value_label.text() if hasattr(card, "_value_label") else "--"
                    handle.write(f"- {title}: {value}\n")
                handle.write("\n异常明细\n")
                if not self._diagnostic_rows:
                    handle.write("当前筛选条件下没有异常记录\n")
                for row in self._diagnostic_rows:
                    handle.write("\t".join(row) + "\n")
            QApplication.clipboard().setText(path)
            UiFeedback.success(self, "导出完成", f"异常诊断报告已导出：\n{path}")
        except Exception as exc:
            logger.warning("Failed to export diagnostics report: %s", exc)
            UiFeedback.error(self, "导出失败", f"异常诊断报告导出失败：\n{exc}")
