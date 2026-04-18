"""History page built on the shared Windows 11 page scaffold."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.history_manager import history_manager
from src.gui.components.page_shell import Win11PageScaffold, Win11SectionCard, Win11SummaryCard
from src.gui.feedback import UiFeedback
from src.gui.ui_text import ButtonText

logger = logging.getLogger(__name__)


class HistorySummaryCard(Win11SummaryCard):
    """Compact summary card used by the history overview row."""

    def __init__(self, title: str, value: str = "--", subtitle: str = "", parent=None):
        super().__init__(title=title, value=value, subtitle=subtitle, parent=parent)
        self.subtitle_label.setProperty("ui", "win11-helper-text")

    def set_data(self, value: str, subtitle: str | None = None) -> None:
        self.set_value(value)
        if subtitle is not None:
            self.set_subtitle(subtitle)


class HistoryPage(Win11PageScaffold):
    """Filterable history table for past sync activity."""

    def __init__(self, parent_gui, parent=None):
        self.gui = parent_gui
        self.current_page = 1
        self.page_size = 20
        self.total_records = 0
        self.current_records: list[dict] = []

        super().__init__(
            title="历史记录",
            eyebrow="历史中心",
            subtitle="查看过往同步执行记录，按条件筛选并分页浏览，支持导出当前结果视图。",
            parent=parent,
        )
        self.setProperty("page", "history")

        self.setup_ui()
        self.load_history(1)

    def setup_ui(self) -> None:
        self._init_filters()
        self._build_hero()
        self._build_summary_strip()
        self.add_primary_action(self.btn_query)
        self.add_primary_action(self.btn_export)
        self.set_content(self._create_content())
        self._apply_filter_layout()

    def _init_filters(self) -> None:
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("按表单名称或消息内容搜索")
        self.search_box.setProperty("td", "win11-input")
        self.search_box.returnPressed.connect(lambda: self.load_history(1))

        self.combo_time_range = QComboBox()
        self.combo_time_range.setProperty("td", "win11-input")
        self.combo_time_range.addItem("今天", 0)
        self.combo_time_range.addItem("近 7 天", 7)
        self.combo_time_range.addItem("近 30 天", 30)

        self.combo_status = QComboBox()
        self.combo_status.setProperty("td", "win11-input")
        self.combo_status.addItem("全部状态", None)
        self.combo_status.addItem("成功", "success")
        self.combo_status.addItem("部分成功", "partial")
        self.combo_status.addItem("失败", "failed")
        self.combo_status.addItem("异常退出", "failed_abnormal_exit")

        self.combo_type = QComboBox()
        self.combo_type.setProperty("td", "win11-input")
        self.combo_type.addItem("全部类型", None)
        self.combo_type.addItem("增量", "incremental")
        self.combo_type.addItem("全量", "full")
        self.combo_type.addItem("完整", "complete")

        self.btn_query = QPushButton(ButtonText.QUERY)
        self.btn_query.setProperty("class", "primary")
        self.btn_query.setFixedHeight(36)
        self.btn_query.clicked.connect(lambda: self.load_history(1))

    def _build_hero(self) -> None:
        meta_widget = QWidget()
        meta_layout = QVBoxLayout(meta_widget)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(6)

        self.hero_badge = QLabel("历史浏览")
        self.hero_badge.setProperty("ui", "win11-status-chip")
        self.hero_badge.setProperty("tone", "info")

        self.summary_hint = QLabel("当前筛选条件下共有 0 条记录。")
        self.summary_hint.setProperty("ui", "win11-meta-text")
        self.summary_hint.setWordWrap(True)

        meta_layout.addWidget(self.hero_badge, 0, Qt.AlignmentFlag.AlignLeft)
        meta_layout.addWidget(self.summary_hint)

        self.btn_export = QPushButton(ButtonText.EXPORT)
        self.btn_export.setProperty("class", "secondary")
        self.btn_export.setFixedHeight(36)
        self.btn_export.clicked.connect(self.export_data)

        self.add_hero_widget(meta_widget)

    def _build_summary_strip(self) -> None:
        self.card_rate = HistorySummaryCard("今日成功率", "--", "基于今天的执行记录统计。")
        self.card_duration = HistorySummaryCard("平均耗时", "--", "基于成功执行记录计算平均时长。")
        self.card_fail = HistorySummaryCard("高频失败对象", "--", "近 30 天最常见失败目标。")

        for card in (self.card_rate, self.card_duration, self.card_fail):
            self.add_summary_card(card)

    def _create_content(self) -> QWidget:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        layout.addWidget(self._create_filter_card())
        layout.addWidget(self._create_table_card(), 1)
        layout.addWidget(self._create_pagination_card())
        return root

    def _create_filter_card(self) -> Win11SectionCard:
        card = Win11SectionCard(
            "筛选条件",
            "可按关键词、时间范围、状态与同步类型筛选历史记录后再查看或导出。",
        )

        self.filter_grid = QWidget()
        self.filter_grid.setProperty("compact", False)
        self.filter_grid_layout = QGridLayout(self.filter_grid)
        self.filter_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.filter_grid_layout.setHorizontalSpacing(12)
        self.filter_grid_layout.setVerticalSpacing(12)
        self.filter_fields = [
            self._create_inline_field("鎼滅储", self.search_box),
            self._create_inline_field("鏃堕棿鑼冨洿", self.combo_time_range),
            self._create_inline_field("鐘舵€?", self.combo_status),
            self._create_inline_field("绫诲瀷", self.combo_type),
        ]
        card.content_layout.addWidget(self.filter_grid)
        return card

        form_row = QHBoxLayout()
        form_row.setSpacing(12)
        form_row.addWidget(self._create_inline_field("搜索", self.search_box), 2)
        form_row.addWidget(self._create_inline_field("时间范围", self.combo_time_range), 1)
        form_row.addWidget(self._create_inline_field("状态", self.combo_status), 1)
        form_row.addWidget(self._create_inline_field("类型", self.combo_type), 1)
        card.content_layout.addLayout(form_row)

        action_row = QHBoxLayout()
        action_row.addStretch(1)

        btn_query = QPushButton(ButtonText.QUERY)
        btn_query.setProperty("class", "primary")
        btn_query.setFixedHeight(36)
        btn_query.setFixedWidth(112)
        btn_query.clicked.connect(lambda: self.load_history(1))
        action_row.addWidget(btn_query)
        card.content_layout.addLayout(action_row)
        return card

    def _create_inline_field(self, title: str, widget: QWidget) -> QWidget:
        row = QWidget()
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel(title)
        label.setProperty("ui", "win11-row-title")

        layout.addWidget(label)
        layout.addWidget(widget)
        return row

    def _create_table_card(self) -> Win11SectionCard:
        card = Win11SectionCard(
            "同步记录表",
            "以下表格展示当前筛选结果，保留既有筛选、分页与导出行为。",
        )

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["ID", "开始时间", "表单", "同步类型", "记录数", "耗时", "状态", "消息"]
        )
        self.table.setProperty("ui", "win11-data-table")
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(48)
        card.content_layout.addWidget(self.table, 1)
        return card

    def _create_pagination_card(self) -> QFrame:
        card = QFrame()
        card.setProperty("ui", "win11-pagination-card")

        layout = QHBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)

        self.lbl_page_info = QLabel("共 0 条记录")
        self.lbl_page_info.setProperty("ui", "win11-helper-text")
        layout.addWidget(self.lbl_page_info)
        layout.addStretch(1)

        self.btn_prev = QPushButton("上一页")
        self.btn_prev.setProperty("class", "secondary")
        self.btn_prev.setFixedHeight(34)
        self.btn_prev.clicked.connect(self.prev_page)

        self.lbl_curr_page = QLabel("1")
        self.lbl_curr_page.setProperty("ui", "win11-page-badge")
        self.lbl_curr_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_curr_page.setFixedWidth(52)

        self.btn_next = QPushButton("下一页")
        self.btn_next.setProperty("class", "secondary")
        self.btn_next.setFixedHeight(34)
        self.btn_next.clicked.connect(self.next_page)

        jump_label = QLabel("跳转到")
        jump_label.setProperty("ui", "win11-row-title")

        self.jump_box = QSpinBox()
        self.jump_box.setProperty("td", "win11-input")
        self.jump_box.setMinimum(1)
        self.jump_box.setFixedWidth(86)
        self.jump_box.editingFinished.connect(lambda: self.load_history(self.jump_box.value()))

        layout.addWidget(self.btn_prev)
        layout.addWidget(self.lbl_curr_page)
        layout.addWidget(self.btn_next)
        layout.addSpacing(8)
        layout.addWidget(jump_label)
        layout.addWidget(self.jump_box)
        return card

    def _apply_filter_layout(self) -> None:
        compact = self.width() <= 1366
        self.filter_grid.setProperty("compact", compact)
        while self.filter_grid_layout.count():
            item = self.filter_grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

        positions = [(0, 0), (0, 1), (1, 0), (1, 1)] if compact else [(0, 0), (0, 1), (0, 2), (0, 3)]
        for (row, col), widget in zip(positions, self.filter_fields):
            self.filter_grid_layout.addWidget(widget, row, col)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._apply_filter_layout()
        super().resizeEvent(event)

    def load_history(self, page=None) -> None:
        if page:
            self.current_page = page

        self.lbl_curr_page.setText(str(self.current_page))
        self.jump_box.setValue(self.current_page)

        days = int(self.combo_time_range.currentData() or 0)
        today = datetime.now()
        start_anchor = today - timedelta(days=days)
        start_date = start_anchor.strftime("%Y-%m-%d") + " 00:00:00"
        end_date = today.strftime("%Y-%m-%d") + " 23:59:59"

        status = self.combo_status.currentData()
        sync_type = self.combo_type.currentData()
        form_name = self.search_box.text().strip()

        try:
            records, total = history_manager.get_history(
                page=self.current_page,
                page_size=self.page_size,
                start_date=start_date,
                end_date=end_date,
                status=status,
                sync_type=sync_type,
                form_name=form_name if form_name else None,
            )
            self.total_records = total
            self.current_records = records
            self.summary_hint.setText(f"当前筛选条件下共有 {total} 条记录。")
            self.update_table(records)
            self.update_pagination()

            stats = history_manager.get_stats()
            self.card_rate.set_data(stats.get("today_success_rate", "0%"), "基于今天的执行记录统计。")
            self.card_duration.set_data(stats.get("avg_duration", "0s"), "基于成功执行记录计算平均时长。")
            top_fails = stats.get("top_failures", [])
            self.card_fail.set_data(
                top_fails[0] if top_fails else "无",
                "近 30 天最常见失败目标。",
            )
        except Exception as exc:
            logger.error("加载历史记录失败：%s", exc)
            UiFeedback.error(self, "加载失败", f"无法加载同步历史记录：\n{exc}")
            self.total_records = 0
            self.current_records = []
            self.table.clearContents()
            self.table.setRowCount(0)
            self.summary_hint.setText("当前筛选条件下共有 0 条记录。")
            self.update_pagination()

    def update_table(self, records) -> None:
        type_map = {"incremental": "增量", "full": "全量", "complete": "完整"}
        self.table.clearSpans()
        self.table.clearContents()
        self.table.setRowCount(len(records))

        for row_index, row_data in enumerate(records):
            values = [
                str(row_data.get("id", "")),
                str(row_data.get("start_time_str", "")),
                str(row_data.get("form_name", "")),
                type_map.get(row_data.get("sync_type", ""), str(row_data.get("sync_type", ""))),
                str(row_data.get("record_count", row_data.get("records_synced", 0) or 0)),
                f"{float(row_data.get('duration_seconds', row_data.get('duration', 0)) or 0):.1f}s",
                "",
                str(row_data.get("message", ""))[:40] or "--",
            ]
            for col_index, value in enumerate(values):
                if col_index == 6:
                    continue

                item = QTableWidgetItem(value)
                if col_index in (0, 4, 5):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_index, col_index, item)

            status_text, tone = self._get_status_display(row_data.get("status"))
            self.table.setCellWidget(row_index, 6, self._build_tag(status_text, tone))

        if not records:
            self.table.setRowCount(1)
            self.table.setSpan(0, 0, 1, self.table.columnCount())
            item = QTableWidgetItem("当前筛选条件下没有匹配的历史记录。")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(0, 0, item)

    def _build_tag(self, text: str, tone: str) -> QWidget:
        wrap = QWidget()
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = QLabel(text)
        label.setProperty("ui", "win11-table-tag")
        label.setProperty("tone", tone)
        layout.addWidget(label)
        return wrap

    def _get_status_display(self, status: str | None):
        if status == "success":
            return "成功", "success"
        if status == "partial":
            return "部分成功", "info"
        if status == "failed":
            return "失败", "danger"
        if status == "failed_abnormal_exit":
            return "异常退出", "danger"
        return str(status or "--"), "info"

    def update_pagination(self) -> None:
        self.lbl_page_info.setText(f"共 {self.total_records} 条记录")
        total_pages = max(1, (self.total_records + self.page_size - 1) // self.page_size)
        self.btn_prev.setEnabled(self.current_page > 1)
        self.btn_next.setEnabled(self.current_page < total_pages)
        self.jump_box.setMaximum(total_pages)
        self.lbl_curr_page.setText(str(self.current_page))

    def _set_combo_by_data(self, combo: QComboBox, target_value) -> None:
        for idx in range(combo.count()):
            if combo.itemData(idx) == target_value:
                combo.setCurrentIndex(idx)
                return

    def apply_quick_filter(self, days: int = 7, status: str | None = None, form_name: str | None = None) -> None:
        """Apply a quick filter when jumping from another page."""

        normalized_days = 30 if int(days or 0) >= 30 else 7
        self._set_combo_by_data(self.combo_time_range, normalized_days)
        if status in ("success", "partial", "failed", "failed_abnormal_exit"):
            self._set_combo_by_data(self.combo_status, status)
        else:
            self._set_combo_by_data(self.combo_status, None)
        self.search_box.setText(form_name or "")
        self.load_history(1)

    def prev_page(self) -> None:
        if self.current_page > 1:
            self.load_history(self.current_page - 1)

    def next_page(self) -> None:
        total_pages = max(1, (self.total_records + self.page_size - 1) // self.page_size)
        if self.current_page < total_pages:
            self.load_history(self.current_page + 1)

    def export_data(self) -> None:
        try:
            if not self.current_records:
                UiFeedback.info(self, "暂无可导出内容", "当前视图没有可导出的历史记录。")
                return

            content = []
            for row_index in range(self.table.rowCount()):
                row_data = []
                for col_index in range(self.table.columnCount()):
                    if col_index == 6:
                        widget = self.table.cellWidget(row_index, col_index)
                        if widget and widget.layout() and widget.layout().count():
                            row_data.append(widget.layout().itemAt(0).widget().text())
                        else:
                            row_data.append("")
                    else:
                        item = self.table.item(row_index, col_index)
                        row_data.append(item.text() if item else "")
                content.append("\t".join(row_data))

            QApplication.clipboard().setText("\n".join(content))
            UiFeedback.success(self, "导出成功", "历史数据已复制到剪贴板。")
        except Exception as exc:
            UiFeedback.error(self, "导出失败", f"无法导出历史数据：\n{exc}")
