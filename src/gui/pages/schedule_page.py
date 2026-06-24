"""Schedule page with real scheduler status integration."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.config.config_manager import config_manager
from src.core.scheduler import auto_scheduler
from src.gui.components.common import SvgIconLabel
from src.gui.components.data_table import DataTable
from src.gui.components.page_shell import Win11PageScaffold, Win11SectionCard
from src.gui.design_tokens import ColorTokens, SizeTokens, SpacingTokens
from src.gui.feedback import UiFeedback
from src.gui.logging_utils import GuiLogHandler, LogSignal
from src.utils import logger as app_logger

logger = logging.getLogger(__name__)

_SCHEDULE_LOG_KEYWORDS = ("scheduler", "调度", "定时同步")


class SchedulePage(Win11PageScaffold):
    """Scheduler configuration and runtime monitor page."""

    def __init__(self, parent_gui, parent=None):
        self.gui = parent_gui

        self.log_signal = LogSignal()
        self.log_signal.text_written.connect(lambda *_a: None)
        self.log_handler = GuiLogHandler(self.log_signal)
        self.log_handler.setFormatter(logging.Formatter("%(message)s"))
        self._log_rows: list[list[str]] = []
        self._filtered_log_rows: list[list[str]] = list(self._log_rows)
        self._stat_cards: dict[str, QFrame] = {}
        self._status_items: dict[str, QFrame] = {}
        self._settings_dirty = False

        super().__init__(
            title="调度管理",
            eyebrow="",
            subtitle="查看自动调度规则、运行状态与调度日志",
            parent=parent,
        )
        self.setProperty("page", "schedule")
        self.set_hero_visible(False)
        self.hero_card.setVisible(False)
        self.primary_action_host.setVisible(False)
        self.summary_strip.setVisible(False)
        self._build_ui()
        self._load_real_data()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._load_real_data)
        self.timer.start(5000)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        if hasattr(self, "timer") and self.timer.isActive():
            self.timer.stop()
        super().closeEvent(event)

    def _build_ui(self) -> None:
        content_widget = QWidget()
        content_widget.setObjectName("schedule_content")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)

        title_row = QWidget()
        title_layout = QHBoxLayout(title_row)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(12)

        self.page_title = QLabel("调度管理")
        self.page_title.setProperty("ui", "sc-page-title")
        title_text_col = QVBoxLayout()
        title_text_col.setContentsMargins(0, 0, 0, 0)
        title_text_col.setSpacing(3)
        title_text_col.addWidget(self.page_title)
        self.page_subtitle = QLabel("启动自动调度后会先执行一次增量同步，随后按间隔重复执行")
        self.page_subtitle.setProperty("ui", "sc-page-subtitle")
        title_text_col.addWidget(self.page_subtitle)
        title_layout.addLayout(title_text_col)
        title_layout.addStretch()

        self.btn_stop = QPushButton("停止调度")
        self.btn_stop.setProperty("class", "primary")
        self.btn_stop.setFixedSize(132, 36)
        self.btn_stop.clicked.connect(self.toggle_scheduler)
        title_layout.addWidget(self.btn_stop)

        self.btn_save = QPushButton("保存设置")
        self.btn_save.setProperty("class", "secondary")
        self.btn_save.setFixedSize(132, 36)
        self.btn_save.clicked.connect(self.save_settings)
        title_layout.addWidget(self.btn_save)
        content_layout.addWidget(title_row)

        stats_row = QWidget()
        stats_row.setObjectName("schedule_stats_row")
        stats_layout = QHBoxLayout(stats_row)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(12)

        stat_defs = [
            ("调度状态", "运行中", "调度服务正常运行", ColorTokens.SUCCESS_GREEN),
            ("执行间隔", "30 分钟", "固定间隔执行", ColorTokens.ACCENT_600),
            ("上次执行", "14:30", "2024-05-14 14:30:00", ColorTokens.INFO),
            ("下次执行", "15:00", "2024-05-14 15:00:00", ColorTokens.WARNING),
            ("今日成功", "26 次", "成功执行任务数", ColorTokens.SUCCESS_GREEN),
        ]
        for index, (title, value, subtitle, color) in enumerate(stat_defs):
            icon_file = (
                "schedule_status.svg",
                "schedule_interval.svg",
                "schedule_last.svg",
                "schedule_next.svg",
                "schedule_success.svg",
            )[index]
            card = self._create_stat_card(title, value, subtitle, color, icon_file)
            card.setFixedHeight(88)
            self._stat_cards[title] = card
            stats_layout.addWidget(card)
        content_layout.addWidget(stats_row)

        middle_row = QWidget()
        middle_row.setObjectName("schedule_middle_row")
        middle_row.setFixedHeight(292)
        middle_layout = QHBoxLayout(middle_row)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(16)

        left_col = QVBoxLayout()
        left_col.setSpacing(10)

        config_card = Win11SectionCard("生效规则", "当前自动调度实际使用的配置")
        config_card.setProperty("ui", "sc-config-card")
        self.auto_toggle = self._make_toggle(True)
        self.interval_spin = self._make_spinbox(30, 1, 1440)
        self.interval_spin.valueChanged.connect(self._mark_settings_dirty)
        self.scope_value = QLabel("--")
        self.scope_value.setProperty("ui", "sc-rule-value")
        self.mode_value = QLabel("增量同步")
        self.mode_value.setProperty("ui", "sc-rule-value")
        self.start_note_value = QLabel("启动后先执行一次同步")
        self.start_note_value.setProperty("ui", "sc-rule-value")
        config_rows = [
            self._create_setting_row("自动调度", "保存后作为调度开关配置", self.auto_toggle),
            self._create_setting_row("执行间隔", "每隔 N 分钟执行一次增量同步", self.interval_spin),
            self._create_setting_row("同步范围", "来自同步执行页默认表单配置", self.scope_value),
            self._create_setting_row("同步模式", "定时调度固定使用增量同步", self.mode_value),
            self._create_setting_row("启动说明", "启动调度时先执行一次", self.start_note_value),
        ]
        for row in config_rows:
            config_card.content_layout.addWidget(row)
        left_col.addWidget(config_card)
        left_col.addStretch()

        right_col = QVBoxLayout()
        right_col.setSpacing(10)

        status_card = Win11SectionCard("运行状态", "自动调度服务的当前状态")
        status_card.setProperty("ui", "sc-status-card")
        status_rows = [
            self._create_status_item("当前状态", "--", "查看任务管理", ColorTokens.ACCENT_600, "schedule_status.svg", "task_management"),
            self._create_status_item("当前任务", "暂无任务明细", "查看任务管理", ColorTokens.SUCCESS_GREEN, "schedule_running.svg", "task_management"),
            self._create_status_item("最近结果", "请查看同步历史", "查看同步历史", ColorTokens.INFO, "schedule_result.svg", "history"),
            self._create_status_item("服务日志", "读取日志中心", "查看日志", ColorTokens.SUCCESS_GREEN, "schedule_heartbeat.svg", "log_center"),
        ]
        for item in status_rows:
            self._status_items[item.title_label.text()] = item
            status_card.content_layout.addWidget(item)
        right_col.addWidget(status_card)
        right_col.addStretch()

        middle_layout.addLayout(left_col, 1)
        middle_layout.addLayout(right_col, 1)
        content_layout.addWidget(middle_row)

        log_card = Win11SectionCard("调度日志", "")
        log_card.setProperty("ui", "sc-log-card")
        log_header = QHBoxLayout()
        log_header.setContentsMargins(0, 0, 0, 8)
        log_header.setSpacing(8)
        log_header.addStretch()

        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["全部级别", "INFO", "WARN", "ERROR"])
        self.log_level_combo.setFixedHeight(30)
        self.log_level_combo.setMinimumWidth(100)
        self.log_level_combo.currentTextChanged.connect(self.apply_log_filter)
        log_header.addWidget(self.log_level_combo)

        self.btn_export_log = QPushButton("导出日志")
        self.btn_export_log.setProperty("class", "secondary")
        self.btn_export_log.setFixedHeight(30)
        self.btn_export_log.clicked.connect(self.export_log_view)
        log_header.addWidget(self.btn_export_log)
        log_card.content_layout.addLayout(log_header)

        self.log_table = DataTable(["时间", "级别", "任务", "消息"])
        self.log_table.set_empty_text("暂无调度日志，启动自动调度后将在此显示执行记录。")
        self.log_table.table.verticalHeader().setDefaultSectionSize(34)
        self.log_table.table.horizontalHeader().setFixedHeight(38)
        self.log_table.table.setFixedHeight(224)
        self.log_table.set_data(self._filtered_log_rows)
        log_card.content_layout.addWidget(self.log_table)

        self.pagination_row = QHBoxLayout()
        self.pagination_row.setContentsMargins(0, 8, 0, 0)
        self.pagination_row.setSpacing(8)
        self.pagination_row.addStretch()

        self.lbl_total = QLabel("共 0 条")
        self.lbl_total.setProperty("ui", "sc-pagination-text")
        self.pagination_row.addWidget(self.lbl_total)
        log_card.content_layout.addLayout(self.pagination_row)

        content_layout.addWidget(log_card, 1)

        self.set_content(content_widget)

    def _create_stat_card(self, title: str, value: str, subtitle: str, color: str, icon_file: str) -> QWidget:
        card = QFrame()
        card.setProperty("ui", "sc-stat-card")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        icon_widget = SvgIconLabel(icon_file, size=46, icon_size=26, color=color)
        icon_widget.setProperty("ui", "sc-stat-icon")
        layout.addWidget(icon_widget)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title_lbl = QLabel(title)
        title_lbl.setProperty("ui", "sc-stat-title")
        value_lbl = QLabel(value)
        value_lbl.setProperty("ui", "sc-stat-value")
        sub_lbl = QLabel(subtitle)
        sub_lbl.setProperty("ui", "sc-stat-sub")
        text_col.addWidget(title_lbl)
        text_col.addWidget(value_lbl)
        text_col.addWidget(sub_lbl)
        layout.addLayout(text_col, 1)
        card.title_label = title_lbl
        card.value_label = value_lbl
        card.subtitle_label = sub_lbl

        return card

    def _create_setting_row(self, title_text: str, note_text: str, editor: QWidget) -> QWidget:
        row = QWidget()
        row.setProperty("ui", "sc-setting-row")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(12)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title = QLabel(title_text)
        title.setProperty("ui", "sc-setting-title")
        note = QLabel(note_text)
        note.setProperty("ui", "sc-setting-note")
        text_col.addWidget(title)
        text_col.addWidget(note)
        layout.addLayout(text_col, 1)

        layout.addWidget(editor)
        return row

    def _create_status_item(self, title: str, value: str, action: str, color: str, icon_file: str, target_page: str) -> QWidget:
        item = QFrame()
        item.setProperty("ui", "sc-status-item")
        item.setFixedHeight(58)
        layout = QHBoxLayout(item)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)

        icon_widget = SvgIconLabel(icon_file, size=32, icon_size=20, color=color)
        icon_widget.setProperty("ui", "sc-status-icon")
        layout.addWidget(icon_widget)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title_lbl = QLabel(title)
        title_lbl.setProperty("ui", "sc-status-title")
        value_lbl = QLabel(value)
        value_lbl.setProperty("ui", "sc-status-value")
        text_col.addWidget(title_lbl)
        text_col.addWidget(value_lbl)
        layout.addLayout(text_col, 1)

        action_lbl = QLabel(action)
        action_lbl.setProperty("ui", "sc-status-action")
        action_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        action_lbl.mousePressEvent = lambda _event, page=target_page: self._navigate_to(page)
        layout.addWidget(action_lbl)
        item.title_label = title_lbl
        item.value_label = value_lbl
        item.action_label = action_lbl

        return item

    def _make_toggle(self, checked: bool) -> QPushButton:
        btn = QPushButton("开" if checked else "关")
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setFixedHeight(30)
        btn.setFixedWidth(50)
        btn.setProperty("ui", "sc-toggle")
        btn.clicked.connect(lambda: (self._set_toggle_text(btn), self._mark_settings_dirty()))
        return btn

    def _make_spinbox(self, value: int, min_val: int, max_val: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(value)
        spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spin.setFixedSize(96, 36)
        spin.setProperty("td", "win11-input")
        spin.setProperty("ui", "sc-spin-input")
        return spin

    def _load_real_data(self) -> None:
        try:
            self._load_scheduler_status()
        except Exception as exc:
            logger.warning("Failed to load scheduler status: %s", exc)
        try:
            self._load_scheduler_logs()
        except Exception as exc:
            logger.warning("Failed to load scheduler logs: %s", exc)

    def _load_scheduler_status(self) -> None:
        try:
            running = auto_scheduler.is_running()
        except Exception:
            running = False

        try:
            config = config_manager.get_sync_config()
        except Exception:
            config = {}

        interval = int(config.get("sync_interval", 30) or 30)
        auto_sync = bool(config.get("auto_sync", False))
        default_forms = config.get("default_forms") or []
        if isinstance(default_forms, str):
            default_forms = [item for item in default_forms.split(",") if item.strip()]
        if hasattr(self, "auto_toggle") and not self._settings_dirty:
            self.auto_toggle.setChecked(auto_sync)
            self._set_toggle_text(self.auto_toggle)
        if hasattr(self, "interval_spin") and not self._settings_dirty:
            self.interval_spin.blockSignals(True)
            self.interval_spin.setValue(interval)
            self.interval_spin.blockSignals(False)
        if hasattr(self, "scope_value"):
            self.scope_value.setText("全部表单" if not default_forms else f"{len(default_forms)} 个表单")
        if hasattr(self, "mode_value"):
            self.mode_value.setText("增量同步")
        if hasattr(self, "start_note_value"):
            self.start_note_value.setText("启动后先执行一次同步")

        self.btn_stop.setText("停止调度" if running else "启动调度")
        self.btn_stop.setProperty("class", "primary" if running else "secondary")
        self._refresh_widget_style(self.btn_stop)

        self._set_stat("调度状态", "运行中" if running else "已停止", "调度服务正常运行" if running else "自动调度未运行")
        self._set_stat("执行间隔", f"{interval} 分钟", "来自当前同步配置")

        last_time = self._safe_scheduler_time("get_last_exec_time")
        next_time = self._safe_scheduler_time("get_next_exec_time")
        self._set_stat("上次执行", self._format_time(last_time, short=True), self._format_time(last_time))
        self._set_stat("下次执行", self._format_time(next_time, short=True), self._format_time(next_time))
        self._set_stat("今日成功", "--", "暂无独立调度成功计数")

        self._set_status_item("当前状态", "运行中" if running else "未运行", "查看任务管理")
        self._set_status_item("当前任务", "运行中" if running else "暂无任务明细", "查看任务管理")
        self._set_status_item("最近结果", "请查看同步历史", "查看同步历史")
        self._set_status_item("服务日志", "读取日志中心", "查看日志")

    def _read_scheduler_log_rows(self, max_lines: int = 2000, limit: int = 30) -> list[list[str]]:
        log_file = os.path.join(app_logger.get_log_dir(), "app.jsonl")
        if not os.path.exists(log_file):
            return []

        rows: list[list[str]] = []
        try:
            with open(log_file, encoding="utf-8") as handle:
                for line_index, line in enumerate(handle):
                    if line_index >= max_lines or len(rows) >= limit:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    name = str(entry.get("name", ""))
                    message = str(entry.get("message", ""))
                    haystack = f"{name} {message}".lower()
                    if not any(keyword.lower() in haystack for keyword in _SCHEDULE_LOG_KEYWORDS):
                        continue
                    rows.append(
                        [
                            str(entry.get("asctime", "--"))[:19],
                            str(entry.get("levelname", "--")),
                            name.split(".")[-1] or "--",
                            message[:90],
                        ]
                    )
                    if len(rows) >= max_lines:
                        break
        except Exception as exc:
            logger.warning("Failed to read scheduler log rows: %s", exc)
            return []
        return rows

    def _load_scheduler_logs(self) -> None:
        self._log_rows = self._read_scheduler_log_rows()
        self.apply_log_filter()

    def _set_stat(self, key: str, value: str, subtitle: str) -> None:
        card = self._stat_cards.get(key)
        if not card:
            return
        card.value_label.setText(value)
        card.subtitle_label.setText(subtitle)

    def _set_status_item(self, key: str, value: str, action: str) -> None:
        item = self._status_items.get(key)
        if not item:
            return
        item.value_label.setText(value)
        item.action_label.setText(action)

    def _navigate_to(self, page_id: str) -> None:
        if hasattr(self.gui, "switch_to_page"):
            self.gui.switch_to_page(page_id)

    def _safe_scheduler_time(self, method_name: str):
        method = getattr(auto_scheduler, method_name, None)
        if method is None:
            return None
        try:
            return method()
        except Exception:
            return None

    def _format_time(self, value, *, short: bool = False) -> str:
        if not value:
            return "--"
        if isinstance(value, datetime):
            return value.strftime("%H:%M" if short else "%Y-%m-%d %H:%M:%S")
        return str(value)

    def _set_toggle_text(self, btn: QPushButton) -> None:
        btn.setText("开" if btn.isChecked() else "关")

    def _mark_settings_dirty(self) -> None:
        self._settings_dirty = True

    def _refresh_widget_style(self, widget: QWidget) -> None:
        style = widget.style()
        if style is not None:
            style.unpolish(widget)
            style.polish(widget)

    def save_settings(self) -> None:
        try:
            config_manager.update_config("SYNC", "auto_sync", "True" if self.auto_toggle.isChecked() else "False")
            config_manager.update_config("SYNC", "sync_interval", str(self.interval_spin.value()))
            UiFeedback.success(self, "保存成功", "自动调度配置已保存。")
            self._settings_dirty = False
            self._load_scheduler_status()
        except Exception as exc:
            logger.warning("Failed to save schedule settings: %s", exc)
            UiFeedback.error(self, "保存失败", f"自动调度配置保存失败：\n{exc}")

    def toggle_scheduler(self) -> None:
        try:
            if auto_scheduler.is_running():
                auto_scheduler.stop()
                UiFeedback.success(self, "已停止", "自动调度已停止。")
            else:
                auto_scheduler.start(self.interval_spin.value())
                UiFeedback.success(self, "已启动", "自动调度已启动，将先执行一次增量同步。")
            self._load_scheduler_status()
        except Exception as exc:
            logger.warning("Failed to toggle scheduler: %s", exc)
            UiFeedback.error(self, "操作失败", f"调度状态切换失败：\n{exc}")

    def apply_log_filter(self) -> None:
        level = self.log_level_combo.currentText()
        if level == "全部级别":
            rows = list(self._log_rows)
        else:
            rows = [row for row in self._log_rows if len(row) > 1 and row[1] == level]
        self._filtered_log_rows = rows
        self.log_table.set_data(rows)
        self.lbl_total.setText(f"共 {len(rows)} 条")

    def export_log_view(self) -> None:
        if not self._filtered_log_rows:
            UiFeedback.info(self, "暂无可导出日志", "当前筛选结果没有调度日志。")
            return
        try:
            log_dir = app_logger.get_log_dir()
            os.makedirs(log_dir, exist_ok=True)
            path = os.path.join(log_dir, f"schedule_log_export_{datetime.now().strftime('%Y%m%d%H%M%S')}.txt")
            with open(path, "w", encoding="utf-8") as handle:
                for row in self._filtered_log_rows:
                    handle.write("\t".join(row) + "\n")
            QApplication.clipboard().setText(path)
            UiFeedback.success(self, "导出完成", f"调度日志已导出：\n{path}")
        except Exception as exc:
            logger.warning("Failed to export schedule log: %s", exc)
            UiFeedback.error(self, "导出失败", f"调度日志导出失败：\n{exc}")
