"""Schedule page built on the shared Windows 11 page scaffold."""

from __future__ import annotations

import html
import logging
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.config.config_manager import config_manager
from src.core.scheduler import auto_scheduler
from src.gui.components.buttons import LoadingButton, SwitchButton
from src.gui.components.page_shell import Win11PageScaffold, Win11SectionCard, Win11SummaryCard
from src.gui.design_tokens import ColorTokens
from src.gui.feedback import UiFeedback
from src.gui.logging_utils import GuiLogHandler, LogSignal
from src.gui.ui_text import ButtonText, LoadingText
from src.utils import logger as app_logger

logger = logging.getLogger(__name__)


class ScheduleSummaryCard(Win11SummaryCard):
    """Compact summary card for schedule overview values."""

    def __init__(self, title: str, value: str = "--", subtitle: str = "", parent=None):
        super().__init__(title=title, value=value, subtitle=subtitle, parent=parent)
        self.subtitle_label.setProperty("ui", "win11-helper-text")

    def set_data(self, value: str, subtitle: str | None = None) -> None:
        self.set_value(value)
        if subtitle is not None:
            self.set_subtitle(subtitle)


class SchedulePage(Win11PageScaffold):
    """Scheduler configuration and runtime monitor page."""

    def __init__(self, parent_gui, parent=None):
        self.gui = parent_gui
        self.original_auto = False
        self.original_interval = 60
        self.all_logs: list[dict[str, str]] = []
        self._loading_config = False
        self.interval_presets: list[tuple[int, QPushButton]] = []

        self.log_signal = LogSignal()
        self.log_signal.text_written.connect(self.append_log)
        self.log_handler = GuiLogHandler(self.log_signal)
        self.log_handler.setFormatter(logging.Formatter("%(message)s"))
        app_logger.add_log_handler(self.log_handler)
        self._log_handler_attached = True

        super().__init__(
            title="调度管理",
            eyebrow="调度中心",
            subtitle="在统一的 Windows 11 工作区中集中查看调度状态、执行间隔配置与实时日志。",
            parent=parent,
        )
        self.setProperty("page", "schedule")

        self.setup_ui()
        self.load_config()
        self.check_status()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_status)
        self.destroyed.connect(self._on_destroyed)

    def setup_ui(self) -> None:
        self._init_editors()
        self._build_hero()
        self._build_summary_strip()
        self.add_primary_action(self.btn_toggle_task)
        self.add_primary_action(self.btn_save)
        self.set_content(self._create_workspace())
        self._apply_workspace_layout()

    def _init_editors(self) -> None:
        self.switch_auto = SwitchButton()
        self.switch_auto.toggled.connect(self.on_config_changed)

        self.spin_interval = QSpinBox()
        self.spin_interval.setProperty("td", "win11-input")
        self.spin_interval.setRange(1, 1440)
        self.spin_interval.setSuffix(" 分钟")
        self.spin_interval.setFixedWidth(160)
        self.spin_interval.valueChanged.connect(self.on_config_changed)

    def _build_hero(self) -> None:
        meta_widget = QWidget()
        meta_layout = QVBoxLayout(meta_widget)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(6)

        self.status_badge = QLabel("空闲")
        self.status_badge.setProperty("ui", "win11-status-chip")
        self.status_badge.setProperty("tone", "neutral")

        self.quick_info = QLabel("调度器当前空闲。可先保存间隔配置，或直接启动任务。")
        self.quick_info.setProperty("ui", "win11-meta-text")
        self.quick_info.setProperty("tone", "neutral")
        self.quick_info.setWordWrap(True)

        meta_layout.addWidget(self.status_badge, 0, Qt.AlignmentFlag.AlignLeft)
        meta_layout.addWidget(self.quick_info)

        self.btn_toggle_task = LoadingButton(ButtonText.START_TASK)
        self.btn_toggle_task.setProperty("class", "primary")
        self.btn_toggle_task.setFixedHeight(36)
        self.btn_toggle_task.clicked.connect(self.on_toggle_task)

        self.btn_save = LoadingButton(ButtonText.SAVE_SETTINGS)
        self.btn_save.setProperty("class", "secondary")
        self.btn_save.setEnabled(False)
        self.btn_save.setFixedHeight(36)
        self.btn_save.clicked.connect(self.save_config)

        self.add_hero_widget(meta_widget)

    def _build_summary_strip(self) -> None:
        self.card_auto = ScheduleSummaryCard("自动调度", "--", "当前是否启用自动调度。")
        self.card_interval = ScheduleSummaryCard("执行间隔", "--", "已保存的调度执行间隔。")
        self.card_last = ScheduleSummaryCard("最近执行", "--", "最近一次执行时间。")
        self.card_next = ScheduleSummaryCard("下次执行", "--", "下一次计划执行时间。")

        for card in (self.card_auto, self.card_interval, self.card_last, self.card_next):
            self.add_summary_card(card)

    def _create_workspace(self) -> QWidget:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.workspace_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.workspace_splitter.setProperty("ui", "win11-page-splitter")
        self.workspace_splitter.setChildrenCollapsible(False)
        self.workspace_splitter.setHandleWidth(6)
        root_layout.addWidget(self.workspace_splitter, 1)

        self.left_panel = QWidget()
        self.left_panel.setProperty("ui", "win11-workspace-column")
        self.left_panel.setMinimumWidth(420)
        self.left_panel.setMaximumWidth(560)
        left_panel_layout = QVBoxLayout(self.left_panel)
        left_panel_layout.setContentsMargins(0, 0, 0, 0)
        left_panel_layout.setSpacing(14)

        self.status_card = self._create_status_card()
        self.status_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.status_card.setMinimumHeight(max(220, self.status_card.sizeHint().height()))
        left_panel_layout.addWidget(self.status_card)

        self.left_container = QWidget()
        left_layout = QVBoxLayout(self.left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(14)
        left_layout.addWidget(self._create_config_card())
        left_layout.addStretch(1)

        self.left_scroll = QScrollArea()
        self.left_scroll.setWidgetResizable(True)
        self.left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.left_scroll.setWidget(self.left_container)
        left_panel_layout.addWidget(self.left_scroll, 1)

        self.right_container = QWidget()
        self.right_container.setProperty("ui", "win11-workspace-column")
        right_layout = QVBoxLayout(self.right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(14)
        self.log_card = self._create_log_card()
        right_layout.addWidget(self.log_card, 1)

        self.workspace_splitter.addWidget(self.left_panel)
        self.workspace_splitter.addWidget(self.right_container)
        self.workspace_splitter.setStretchFactor(0, 2)
        self.workspace_splitter.setStretchFactor(1, 3)
        self.workspace_splitter.setSizes([560, 920])
        return root

    def _create_status_card(self) -> Win11SectionCard:
        card = Win11SectionCard(
            "调度状态",
            "查看任务是否运行中，以及最近一次和下一次调度执行时间。",
        )

        panel = QFrame()
        panel.setProperty("ui", "win11-progress-card")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(14, 14, 14, 14)
        panel_layout.setSpacing(8)

        self.status_text = QLabel("空闲")
        self.status_text.setProperty("ui", "win11-inline-value")
        self.status_text.setMinimumHeight(38)
        self.status_text.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.lbl_last_exec = QLabel("最近执行：--")
        self.lbl_last_exec.setProperty("ui", "win11-inline-title")

        self.lbl_next_exec = QLabel("下次执行：--")
        self.lbl_next_exec.setProperty("ui", "win11-inline-title")

        panel_layout.addWidget(self.status_text)
        panel_layout.addWidget(self.lbl_last_exec)
        panel_layout.addWidget(self.lbl_next_exec)
        card.content_layout.addWidget(panel)

        self.runtime_strip = QLabel("调度器尚未运行。")
        self.runtime_strip.setProperty("ui", "win11-helper-text")
        self.runtime_strip.setWordWrap(True)
        card.content_layout.addWidget(self.runtime_strip)
        return card

    def _create_config_card(self) -> Win11SectionCard:
        card = Win11SectionCard(
            "调度设置",
            "可在此启用自动调度并调整执行间隔，用于后台同步任务。",
        )
        card.content_layout.addWidget(
            self._create_setting_row(
                "启用自动调度",
                "启用后，同步任务会按已保存间隔自动执行，无需手动触发。",
                self.switch_auto,
            )
        )
        card.content_layout.addWidget(
            self._create_setting_row(
                "执行间隔",
                "常规生产建议保持在 30 到 120 分钟之间。",
                self.spin_interval,
                last=True,
            )
        )

        preset_box = QFrame()
        preset_box.setProperty("ui", "win11-inline-card")
        preset_layout = QHBoxLayout(preset_box)
        preset_layout.setContentsMargins(12, 12, 12, 12)
        preset_layout.setSpacing(8)

        preset_title = QLabel("快捷预设")
        preset_title.setProperty("ui", "win11-inline-title")
        preset_layout.addWidget(preset_title)
        preset_layout.addStretch(1)

        self.interval_presets = []
        for minutes in (15, 30, 60, 120):
            btn = QPushButton(f"{minutes} 分钟")
            btn.setProperty("class", "secondary")
            btn.setFixedHeight(32)
            btn.clicked.connect(lambda _checked=False, value=minutes: self._apply_interval_preset(value))
            self.interval_presets.append((minutes, btn))
            preset_layout.addWidget(btn)

        card.content_layout.addWidget(preset_box)

        self.lbl_interval_strategy = QLabel("常规运行建议间隔为 30 到 120 分钟。")
        self.lbl_interval_strategy.setProperty("ui", "win11-helper-text")
        self.lbl_interval_strategy.setWordWrap(True)
        card.content_layout.addWidget(self.lbl_interval_strategy)
        return card

    def _create_setting_row(self, title_text: str, note_text: str, editor: QWidget, *, last: bool = False) -> QFrame:
        row = QFrame()
        row.setProperty("ui", "win11-setting-row")
        row.setProperty("last", last)

        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(14)

        text_wrap = QVBoxLayout()
        text_wrap.setSpacing(3)

        title = QLabel(title_text)
        title.setProperty("ui", "win11-row-title")

        note = QLabel(note_text)
        note.setProperty("ui", "win11-row-note")
        note.setWordWrap(True)

        text_wrap.addWidget(title)
        text_wrap.addWidget(note)

        layout.addLayout(text_wrap, 1)
        layout.addWidget(editor, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return row

    def _create_ops_hint_card(self) -> Win11SectionCard:
        card = Win11SectionCard(
            "操作建议",
            "建议先保存间隔，再启动或停止调度任务，保证执行策略生效。",
        )

        tips = [
            "除非正在排障，常规间隔建议保持在 30 到 60 分钟。",
            "设置较短间隔前，先确认 API 与数据库连接状态正常。",
            "修改调度配置后请先保存，确保下一次运行使用最新参数。",
        ]
        for index, text in enumerate(tips, start=1):
            item = QFrame()
            item.setProperty("ui", "win11-inline-card")
            row = QHBoxLayout(item)
            row.setContentsMargins(12, 12, 12, 12)
            row.setSpacing(10)

            badge = QLabel(str(index))
            badge.setProperty("ui", "win11-inline-badge")

            body = QLabel(text)
            body.setProperty("ui", "win11-helper-text")
            body.setWordWrap(True)

            row.addWidget(badge)
            row.addWidget(body, 1)
            card.content_layout.addWidget(item)

        return card

    def _create_log_card(self) -> Win11SectionCard:
        card = Win11SectionCard(
            "调度日志",
            "可按级别或关键词筛选日志，并在需要时清空或复制当前视图。",
        )

        toolbar_host = QFrame()
        toolbar_host.setProperty("ui", "win11-log-toolbar")
        toolbar = QHBoxLayout(toolbar_host)
        toolbar.setContentsMargins(10, 8, 10, 8)
        toolbar.setSpacing(8)

        level_label = QLabel("级别")
        level_label.setProperty("ui", "win11-row-title")
        toolbar.addWidget(level_label)

        self.combo_log_level = QComboBox()
        self.combo_log_level.setProperty("td", "win11-input")
        self.combo_log_level.addItem("全部级别", None)
        self.combo_log_level.addItem("成功", "SUCCESS")
        self.combo_log_level.addItem("警告", "WARNING")
        self.combo_log_level.addItem("错误", "ERROR")
        self.combo_log_level.currentIndexChanged.connect(self.refresh_log_view)
        toolbar.addWidget(self.combo_log_level)

        keyword_label = QLabel("关键词")
        keyword_label.setProperty("ui", "win11-row-title")
        toolbar.addWidget(keyword_label)

        self.combo_log_keyword = QComboBox()
        self.combo_log_keyword.setProperty("td", "win11-input")
        self.combo_log_keyword.addItem("全部日志", None)
        self.combo_log_keyword.addItem("任务启动", "start")
        self.combo_log_keyword.addItem("任务完成", "complete")
        self.combo_log_keyword.addItem("任务失败", "fail")
        self.combo_log_keyword.currentIndexChanged.connect(self.refresh_log_view)
        toolbar.addWidget(self.combo_log_keyword)

        toolbar.addStretch(1)

        btn_clear = QPushButton(ButtonText.CLEAR)
        btn_clear.setProperty("class", "secondary")
        btn_clear.setFixedHeight(32)
        btn_clear.clicked.connect(self.clear_log)

        btn_copy = QPushButton(ButtonText.COPY)
        btn_copy.setProperty("class", "secondary")
        btn_copy.setFixedHeight(32)
        btn_copy.clicked.connect(self.copy_logs)

        toolbar.addWidget(btn_clear)
        toolbar.addWidget(btn_copy)
        card.content_layout.addWidget(toolbar_host)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setProperty("class", "win11-log")
        self.log_text.setMinimumHeight(220)
        card.content_layout.addWidget(self.log_text, 1)
        return card

    def _apply_workspace_layout(self) -> None:
        if hasattr(self, "workspace_splitter") and self.workspace_splitter is not None:
            if self.width() <= 1366:
                self.workspace_splitter.setOrientation(Qt.Orientation.Vertical)
                self.left_panel.setMinimumWidth(0)
                self.left_panel.setMaximumWidth(16777215)
                self.log_text.setMinimumHeight(180)
                status_card_min = max(220, self.status_card.minimumHeight())
                top_height = max(status_card_min + 180, int(self.height() * 0.58))
                bottom_height = max(260, self.height() - top_height)
                self.workspace_splitter.setSizes([top_height, bottom_height])
            else:
                self.workspace_splitter.setOrientation(Qt.Orientation.Horizontal)
                self.left_panel.setMinimumWidth(420)
                self.left_panel.setMaximumWidth(560)
                self.log_text.setMinimumHeight(220)
                self.workspace_splitter.setSizes([560, 920])

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._apply_workspace_layout()
        super().resizeEvent(event)

    def load_config(self) -> None:
        self._loading_config = True
        try:
            config = config_manager.get_sync_config()
            is_auto = bool(config.get("auto_sync", False))
            try:
                interval = int(config.get("sync_interval", 60))
            except Exception:
                interval = 60

            self.switch_auto.setChecked(is_auto)
            self.spin_interval.setValue(interval)
            self.original_auto = is_auto
            self.original_interval = interval
            self.btn_save.setEnabled(False)
            self.btn_save.setText(ButtonText.SAVE_SETTINGS)
            self.card_auto.set_data("已启用" if is_auto else "未启用", "当前是否启用自动调度。")
            self.card_interval.set_data(f"{interval} 分钟", "已保存的调度执行间隔。")
            self._refresh_interval_presets()
            self._refresh_interval_strategy()
            self._update_quick_info("配置已加载完成，可继续调整参数或直接启动任务。", "neutral")
        finally:
            self._loading_config = False

    def on_config_changed(self) -> None:
        if self._loading_config:
            return

        curr_auto = self.switch_auto.isChecked()
        curr_interval = self.spin_interval.value()
        has_changes = (curr_auto != self.original_auto) or (curr_interval != self.original_interval)
        self.btn_save.setEnabled(has_changes)
        self.btn_save.setText("保存设置 *" if has_changes else ButtonText.SAVE_SETTINGS)
        self._refresh_interval_presets()
        self._refresh_interval_strategy()

        if has_changes:
            self._update_quick_info("配置已变更，请在下一次调度前保存。", "info")
        else:
            self._update_quick_info("当前配置与已保存设置一致。", "neutral")

    def save_config(self) -> None:
        try:
            is_auto = self.switch_auto.isChecked()
            interval = self.spin_interval.value()
            config_manager.update_config("SYNC", "auto_sync", str(is_auto))
            config_manager.update_config("SYNC", "sync_interval", str(interval))
            self.original_auto = is_auto
            self.original_interval = interval
            self.btn_save.setEnabled(False)
            self.btn_save.setText(ButtonText.SAVE_SETTINGS)
            self.card_auto.set_data("已启用" if is_auto else "未启用", "当前是否启用自动调度。")
            self.card_interval.set_data(f"{interval} 分钟", "已保存的调度执行间隔。")
            self._refresh_interval_presets()
            self._refresh_interval_strategy()
            logger.info("调度配置已保存。")
            self._update_quick_info("调度设置保存成功。", "success")
            UiFeedback.success(self, "保存成功", "调度设置已成功保存。")
        except Exception as exc:
            self._update_quick_info("调度设置保存失败，请查看日志后重试。", "danger")
            UiFeedback.error(self, "保存失败", f"无法保存调度设置：\n{exc}")

    def on_toggle_task(self) -> None:
        if auto_scheduler.is_running():
            self._do_stop()
        else:
            self._do_start()

    def _do_start(self) -> None:
        self.btn_toggle_task.set_loading(True, LoadingText.START)
        try:
            interval = self.spin_interval.value()
            auto_scheduler.start(interval_minutes=interval)
            logger.info("调度器已启动，执行间隔 %s 分钟。", interval)
        except Exception as exc:
            UiFeedback.error(self, "启动失败", f"无法启动调度器：\n{exc}")
        finally:
            self.btn_toggle_task.set_loading(False)
            self.check_status()

    def _do_stop(self) -> None:
        self.btn_toggle_task.set_loading(True, LoadingText.STOP)
        try:
            auto_scheduler.stop()
            logger.info("调度器已停止。")
        except Exception as exc:
            UiFeedback.error(self, "停止失败", f"无法停止调度器：\n{exc}")
        finally:
            self.btn_toggle_task.set_loading(False)
            self.check_status()

    def check_status(self) -> None:
        running = auto_scheduler.is_running()
        status_text = "运行中" if running else "空闲"
        tone = "success" if running else "neutral"

        self.status_text.setText(status_text)
        self.status_badge.setText(status_text)
        self.status_badge.setProperty("tone", tone)
        badge_style = self.status_badge.style()
        if badge_style is not None:
            badge_style.unpolish(self.status_badge)
            badge_style.polish(self.status_badge)

        self.btn_toggle_task.setProperty("class", "secondary" if running else "primary")
        self.btn_toggle_task.setText(ButtonText.STOP_TASK if running else ButtonText.START_TASK)
        button_style = self.btn_toggle_task.style()
        if button_style is not None:
            button_style.unpolish(self.btn_toggle_task)
            button_style.polish(self.btn_toggle_task)

        last_exec = auto_scheduler.get_last_exec_time()
        next_exec = auto_scheduler.get_next_exec_time()
        last_text = last_exec.strftime("%H:%M:%S") if last_exec else "--"
        next_text = next_exec.strftime("%H:%M:%S") if next_exec else "--"
        self.lbl_last_exec.setText(f"最近执行：{last_text}")
        self.lbl_next_exec.setText(f"下次执行：{next_text}")
        self.card_last.set_data(last_text, "最近一次执行时间。")
        self.card_next.set_data(next_text, "下一次计划执行时间。")
        self.card_auto.set_data(
            "已启用" if self.switch_auto.isChecked() else "未启用",
            "当前是否启用自动调度。",
        )
        self.card_interval.set_data(f"{self.spin_interval.value()} 分钟", "已保存的调度执行间隔。")

        if running:
            runtime_text = f"调度器正在运行，预计下次执行时间：{next_text}。"
            runtime_ui = "win11-helper-text-success"
        else:
            runtime_text = "调度器当前未运行，启动任务后将恢复自动执行。"
            runtime_ui = "win11-helper-text"
        self.runtime_strip.setText(runtime_text)
        self.runtime_strip.setProperty("ui", runtime_ui)
        runtime_style = self.runtime_strip.style()
        if runtime_style is not None:
            runtime_style.unpolish(self.runtime_strip)
            runtime_style.polish(self.runtime_strip)

        if not self.btn_save.isEnabled():
            self._update_quick_info(
                "调度器正在运行，当前配置已保存。"
                if running
                else "调度器当前空闲，可先调整并保存设置后再执行。",
                "success" if running else "neutral",
            )

        self._refresh_interval_presets()
        self._refresh_interval_strategy()

    def _apply_interval_preset(self, minutes: int) -> None:
        self.spin_interval.setValue(minutes)
        self.on_config_changed()

    def _refresh_interval_presets(self) -> None:
        current = self.spin_interval.value()
        for minutes, btn in self.interval_presets:
            btn.setProperty("class", "primary" if minutes == current else "secondary")
            style = btn.style()
            if style is not None:
                style.unpolish(btn)
                style.polish(btn)

    def _refresh_interval_strategy(self) -> None:
        interval = self.spin_interval.value()
        if interval < 15:
            text = "间隔过短，建议仅用于短时排障。"
            ui_value = "win11-helper-text-danger"
        elif interval <= 120:
            text = "当前间隔处于常规生产调度推荐范围。"
            ui_value = "win11-helper-text-success"
        else:
            text = "较长间隔更适用于低优先级或非高峰时段任务。"
            ui_value = "win11-helper-text"

        self.lbl_interval_strategy.setText(text)
        self.lbl_interval_strategy.setProperty("ui", ui_value)
        style = self.lbl_interval_strategy.style()
        if style is not None:
            style.unpolish(self.lbl_interval_strategy)
            style.polish(self.lbl_interval_strategy)

    def _update_quick_info(self, text: str, tone: str) -> None:
        self.quick_info.setText(text)
        self.quick_info.setProperty("tone", tone)
        style = self.quick_info.style()
        if style is not None:
            style.unpolish(self.quick_info)
            style.polish(self.quick_info)

    def _set_polling_active(self, active: bool) -> None:
        if active:
            if not self.timer.isActive():
                self.timer.start(2000)
        elif self.timer.isActive():
            self.timer.stop()

    def _detach_log_handler(self) -> None:
        if not self._log_handler_attached:
            return
        logging.getLogger().removeHandler(self.log_handler)
        self.log_handler.close()
        self._log_handler_attached = False

    def _on_destroyed(self, *_args) -> None:
        self._set_polling_active(False)
        self._detach_log_handler()

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().showEvent(event)
        self.check_status()
        self._set_polling_active(True)

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._set_polling_active(False)
        super().hideEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._set_polling_active(False)
        self._detach_log_handler()
        super().closeEvent(event)

    def append_log(self, msg, level) -> None:
        time_str = datetime.now().strftime("%H:%M:%S")
        normalized_level = str(level or "INFO").upper()
        if normalized_level not in {"INFO", "WARNING", "ERROR", "SUCCESS"}:
            normalized_level = "INFO"

        entry = {"msg": str(msg), "level": normalized_level, "time": time_str}
        self.all_logs.append(entry)
        if self._match_filter(entry):
            self._append_to_view(entry)

    def _match_filter(self, entry: dict[str, str]) -> bool:
        level_filter = self.combo_log_level.currentData()
        keyword_filter = self.combo_log_keyword.currentData()

        if level_filter and entry["level"] != level_filter:
            return False

        if keyword_filter and keyword_filter not in entry["msg"].lower():
            return False

        return True

    def _append_to_view(self, entry: dict[str, str]) -> None:
        msg = entry["msg"]
        time_str = entry["time"]
        color = ColorTokens.TEXT_SECONDARY
        if entry["level"] == "ERROR":
            color = ColorTokens.DANGER
        elif entry["level"] == "WARNING":
            color = ColorTokens.WARNING
        elif entry["level"] == "SUCCESS":
            color = ColorTokens.SUCCESS

        html_text = (
            f'<span style="color: {ColorTokens.TEXT_DISABLED};">[{time_str}]</span> '
            f'<span style="color: {color};">{html.escape(msg)}</span>'
        )
        self.log_text.append(html_text)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def refresh_log_view(self) -> None:
        self.log_text.clear()
        for entry in [log for log in self.all_logs if self._match_filter(log)]:
            self._append_to_view(entry)

    def clear_log(self) -> None:
        self.all_logs.clear()
        self.log_text.clear()

    def copy_logs(self) -> None:
        content = self.log_text.toPlainText().strip()
        if not content:
            UiFeedback.info(self, "暂无可复制内容", "当前调度日志为空。")
            return
        QApplication.clipboard().setText(content)
        UiFeedback.success(self, "复制成功", "调度日志已复制到剪贴板。")
