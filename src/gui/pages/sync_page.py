"""Sync execution page built on the shared Windows 11 page scaffold."""

from __future__ import annotations

import html
import logging
import os
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.config.config_manager import config_manager
from src.gui.components.buttons import LoadingButton
from src.gui.components.combobox import SearchableComboBox
from src.gui.components.page_shell import Win11PageScaffold, Win11SectionCard, Win11SummaryCard
from src.gui.design_tokens import ColorTokens
from src.gui.feedback import UiFeedback
from src.gui.ui_text import ButtonText, LoadingText
from src.gui.workers import SyncWorker, TestWorker
from src.services.sync_service import SyncType, sync_service
from src.utils import logger as app_logger

logger = logging.getLogger(__name__)

FORM_ALL_TEXT = "同步全部表单"
FORM_DEFAULT_TEXT = "使用默认表单集合..."
FORM_ALL_DATA = "__ALL__"
FORM_DEFAULT_DATA = "__DEFAULT__"
SYNC_UI_SCOPE_KEY = "ui_manual_scope"
SYNC_UI_FORM_KEY = "ui_manual_form"
SYNC_UI_MODE_KEY = "ui_manual_mode"


class SyncOverviewCard(Win11SummaryCard):
    """Compact overview card for the sync workspace."""

    def __init__(self, title: str, value: str = "--", subtitle: str = "", parent=None):
        super().__init__(title=title, value=value, subtitle=subtitle, parent=parent)
        self.subtitle_label.setProperty("ui", "win11-helper-text")

    def set_data(self, value: str, subtitle: str | None = None) -> None:
        self.set_value(value)
        if subtitle is not None:
            self.set_subtitle(subtitle)


class SyncExecutionMetricCard(QFrame):
    """Compact metric card for the execution-state panel."""

    def __init__(self, title: str, value: str = "--", note: str = "", parent=None):
        super().__init__(parent)
        self.setProperty("ui", "win11-execution-metric-card")
        self.setMinimumHeight(84)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setProperty("ui", "win11-inline-title")

        self.value_label = QLabel(value)
        self.value_label.setProperty("ui", "win11-inline-value")

        self.note_label = QLabel(note)
        self.note_label.setProperty("ui", "win11-helper-text")
        self.note_label.setWordWrap(True)
        self.note_label.setVisible(bool(note))

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.note_label)

    def set_data(self, value: str, note: str | None = None) -> None:
        self.value_label.setText(value)
        if note is not None:
            self.note_label.setText(note)
            self.note_label.setVisible(bool(note))


class SyncPage(Win11PageScaffold):
    def __init__(self, parent_gui, parent=None):
        self.gui = parent_gui
        self.start_time = None
        self.synced_count = 0
        self.success_count = 0
        self.fail_count = 0
        self.sync_worker = None
        self.test_worker = None
        self._loading_defaults = False
        super().__init__(
            title="同步执行",
            eyebrow="同步",
            subtitle="选择范围、测试连接，并在同一工作区内监控执行进度。",
            parent=parent,
        )
        self.setProperty("page", "sync")
        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self._update_time_elapsed)
        self.setup_ui()
        self.load_smart_defaults()

    def setup_ui(self) -> None:
        self._build_hero()
        self._build_summary_strip()
        self.add_primary_action(self.test_conn_btn)
        self.add_primary_action(self.start_sync_btn)
        self.set_content(self._create_workspace())
        self._apply_workspace_layout()

    def _combo_selected_data(self, combo: SearchableComboBox, *, default=None):
        """
        Resolve selected stable data via payload/index, never by display-text matching.
        """
        current_data = getattr(combo, "_current_data", None)
        if current_data is not None:
            return current_data

        items = getattr(combo, "items_data", []) or []
        current_index = combo.currentIndex()
        if 0 <= current_index < len(items):
            return items[current_index][2]
        return default

    def _set_combo_selected_by_data(self, combo: SearchableComboBox, target_data) -> bool:
        """Select an item by stable data value; returns True if matched."""
        for idx, (_text, _icon, data) in enumerate(getattr(combo, "items_data", []) or []):
            if data == target_data:
                combo.setCurrentIndex(idx)
                return True
        return False

    def _build_hero(self) -> None:
        meta_widget = QWidget()
        meta_layout = QVBoxLayout(meta_widget)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(6)

        self.hero_status = QLabel("空闲")
        self.hero_status.setProperty("ui", "win11-status-chip")
        self.hero_status.setProperty("tone", "neutral")

        self.hero_hint = QLabel("尚未开始同步。可先测试连接，确认后再开始同步。")
        self.hero_hint.setProperty("ui", "win11-meta-text")
        self.hero_hint.setProperty("tone", "neutral")
        self.hero_hint.setWordWrap(True)

        meta_layout.addWidget(self.hero_status, 0, Qt.AlignmentFlag.AlignLeft)
        meta_layout.addWidget(self.hero_hint)

        self.start_sync_btn = LoadingButton(ButtonText.START_SYNC)
        self.start_sync_btn.setProperty("class", "primary")
        self.start_sync_btn.setFixedHeight(36)
        self.start_sync_btn.clicked.connect(self.start_sync)
        self.gui.start_sync_btn = self.start_sync_btn

        self.test_conn_btn = LoadingButton(ButtonText.TEST_CONNECTION)
        self.test_conn_btn.setProperty("class", "secondary")
        self.test_conn_btn.setFixedHeight(36)
        self.test_conn_btn.clicked.connect(self.test_connection)
        self.gui.test_conn_btn = self.test_conn_btn

        self.add_hero_widget(meta_widget)

    def _build_summary_strip(self) -> None:
        self.summary_mode = SyncOverviewCard("同步模式", "--", "日常运行建议使用增量同步。")
        self.summary_target = SyncOverviewCard("目标范围", "--", "可选择全部表单、单个表单或默认表单集合。")
        self.summary_progress = SyncOverviewCard("进度", "0%", "任务尚未开始。")
        self.summary_result = SyncOverviewCard("最近结果", "--", "同步完成后将汇总插入与更新数量。")

        for card in (self.summary_mode, self.summary_target, self.summary_progress, self.summary_result):
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

        self.config_container = QWidget()
        self.config_container.setProperty("ui", "win11-workspace-column")
        self.config_container.setMinimumWidth(420)
        self.config_container.setMaximumWidth(420)
        config_layout = QVBoxLayout(self.config_container)
        config_layout.setContentsMargins(0, 0, 0, 0)
        config_layout.setSpacing(14)
        config_layout.addWidget(
            self._create_group_card(
                "同步配置",
                "选择要同步的表单范围与执行模式，然后再开始运行。",
                [
                    self._create_setting_row(
                        "表单范围",
                        "可对全部表单、单个表单或默认表单集合执行同步。",
                        self._create_form_selector(),
                    ),
                    self._create_setting_row(
                        "同步模式",
                        "增量适合日常；全量与完整同步更适合修复或重建场景。",
                        self._create_mode_selector(),
                        last=True,
                    ),
                ],
            )
        )

        self.ops_strip = QLabel("流程：选择范围 -> 测试连接 -> 开始同步")
        self.ops_strip.setProperty("ui", "win11-inline-banner")
        self.ops_strip.setWordWrap(True)
        config_layout.addWidget(self.ops_strip)

        self.test_status_lbl = QLabel("连接状态将在测试后显示。")
        self.test_status_lbl.setProperty("ui", "win11-helper-text")
        self.test_status_lbl.setWordWrap(True)
        config_layout.addWidget(self.test_status_lbl)

        config_layout.addStretch(1)
        self.workspace_splitter.addWidget(self.config_container)

        self.monitor_container = QWidget()
        self.monitor_container.setProperty("ui", "win11-workspace-column")
        monitor_layout = QVBoxLayout(self.monitor_container)
        monitor_layout.setContentsMargins(0, 0, 0, 0)
        monitor_layout.setSpacing(14)
        self.execution_card = self._create_execution_card()
        self.log_card = self._create_log_card()
        monitor_layout.addWidget(self.execution_card)
        monitor_layout.addWidget(self.log_card, 1)
        self.workspace_splitter.addWidget(self.monitor_container)
        self.workspace_splitter.setStretchFactor(0, 2)
        self.workspace_splitter.setStretchFactor(1, 3)
        self.workspace_splitter.setSizes([540, 980])

        return root

    def _create_group_card(self, title_text: str, subtitle_text: str, rows: list[QWidget]) -> Win11SectionCard:
        card = Win11SectionCard(title_text, subtitle_text)
        for row in rows:
            card.content_layout.addWidget(row)
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
        editor.setMinimumWidth(320)
        editor.setProperty("td", "win11-input")
        layout.addWidget(editor, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return row

    def _create_strategy_card(self) -> Win11SectionCard:
        card = Win11SectionCard(
            "运行建议",
            "通过明确配置与可观测日志降低运行风险。",
        )

        tips = [
            "日常建议使用增量同步，避免 API 压力与数据库写入峰值过高。",
            "完整同步建议在低峰时段执行，并保持实时日志可见以便观察。",
            "若连接测试失败，请先修正配置，再发起新的同步尝试。",
        ]
        for idx, text in enumerate(tips, start=1):
            item = QFrame()
            item.setProperty("ui", "win11-inline-card")
            row = QHBoxLayout(item)
            row.setContentsMargins(12, 12, 12, 12)
            row.setSpacing(10)

            badge = QLabel(str(idx))
            badge.setProperty("ui", "win11-inline-badge")
            body = QLabel(text)
            body.setWordWrap(True)
            body.setProperty("ui", "win11-helper-text")

            row.addWidget(badge)
            row.addWidget(body, 1)
            card.content_layout.addWidget(item)
        return card

    def _create_execution_card(self) -> Win11SectionCard:
        card = Win11SectionCard("执行状态", "同步任务运行时会在此更新实时指标。")

        header = QHBoxLayout()
        header.addStretch(1)

        self.run_state_badge = QLabel("空闲")
        self.run_state_badge.setProperty("ui", "win11-status-chip")
        self.run_state_badge.setProperty("tone", "neutral")
        header.addWidget(self.run_state_badge)
        card.content_layout.addLayout(header)

        metrics = QHBoxLayout()
        metrics.setSpacing(12)
        self.exec_count_card = SyncOverviewCard("已同步记录", "0", "累计插入与更新的行数。")
        self.exec_time_card = SyncOverviewCard("已用时间", "00:00:00", "本次运行的实时计时。")
        self.exec_rate_card = SyncOverviewCard("运行状态", "空闲", "任务状态会随工作线程事件自动更新。")
        for card_item in (self.exec_count_card, self.exec_time_card, self.exec_rate_card):
            metrics.addWidget(card_item)
        card.content_layout.addLayout(metrics)

        progress_wrap = QFrame()
        progress_wrap.setProperty("ui", "win11-progress-card")
        progress_layout = QVBoxLayout(progress_wrap)
        progress_layout.setContentsMargins(14, 14, 14, 14)
        progress_layout.setSpacing(8)

        row = QHBoxLayout()
        label = QLabel("任务进度")
        label.setProperty("ui", "win11-row-title")
        row.addWidget(label)
        row.addStretch(1)

        self.progress_status_lbl = QLabel("等待中")
        self.progress_status_lbl.setProperty("ui", "win11-inline-title")
        row.addWidget(self.progress_status_lbl)

        progress_layout.addLayout(row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(10)
        progress_layout.addWidget(self.progress_bar)

        card.content_layout.addWidget(progress_wrap)
        return card

    def _create_log_card(self) -> Win11SectionCard:
        card = Win11SectionCard("实时日志", "终端风格日志会持续更新，但不会占满整个页面。")

        toolbar_host = QFrame()
        toolbar_host.setProperty("ui", "win11-log-toolbar")
        toolbar = QHBoxLayout(toolbar_host)
        toolbar.setContentsMargins(10, 8, 10, 8)
        toolbar.setSpacing(8)

        self.auto_scroll_cb = QCheckBox("自动滚动")
        self.auto_scroll_cb.setChecked(True)
        toolbar.addWidget(self.auto_scroll_cb)
        toolbar.addStretch(1)

        clear_btn = LoadingButton(ButtonText.CLEAR)
        clear_btn.setProperty("class", "secondary")
        clear_btn.clicked.connect(self.clear_log)

        copy_btn = LoadingButton(ButtonText.COPY)
        copy_btn.setProperty("class", "secondary")
        copy_btn.clicked.connect(self.copy_log)

        export_btn = LoadingButton(ButtonText.EXPORT)
        export_btn.setProperty("class", "secondary")
        export_btn.clicked.connect(self.export_log)

        toolbar.addWidget(clear_btn)
        toolbar.addWidget(copy_btn)
        toolbar.addWidget(export_btn)
        card.content_layout.addWidget(toolbar_host)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setProperty("class", "win11-log")
        self.log_text.setMinimumHeight(220)
        card.content_layout.addWidget(self.log_text, 1)
        return card

    def _create_execution_card(self) -> Win11SectionCard:
        card = Win11SectionCard("执行状态", "同步任务运行时会在此更新实时指标。")

        header = QHBoxLayout()
        header.addStretch(1)

        self.run_state_badge = QLabel("空闲")
        self.run_state_badge.setProperty("ui", "win11-status-chip")
        self.run_state_badge.setProperty("tone", "neutral")
        header.addWidget(self.run_state_badge)
        card.content_layout.addLayout(header)

        metrics = QHBoxLayout()
        metrics.setSpacing(12)
        self.exec_count_card = SyncExecutionMetricCard("已同步记录", "0", "累计插入与更新的行数。")
        self.exec_time_card = SyncExecutionMetricCard("已用时间", "00:00:00", "本次运行的实时计时。")
        self.exec_rate_card = SyncExecutionMetricCard("运行状态", "空闲", "任务状态会随工作线程事件自动更新。")
        for card_item in (self.exec_count_card, self.exec_time_card, self.exec_rate_card):
            metrics.addWidget(card_item)
        card.content_layout.addLayout(metrics)

        progress_wrap = QFrame()
        progress_wrap.setProperty("ui", "win11-progress-card")
        progress_layout = QVBoxLayout(progress_wrap)
        progress_layout.setContentsMargins(14, 14, 14, 14)
        progress_layout.setSpacing(8)

        row = QHBoxLayout()
        label = QLabel("任务进度")
        label.setProperty("ui", "win11-row-title")
        row.addWidget(label)
        row.addStretch(1)

        self.progress_status_lbl = QLabel("等待中")
        self.progress_status_lbl.setProperty("ui", "win11-inline-title")
        row.addWidget(self.progress_status_lbl)

        progress_layout.addLayout(row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(10)
        progress_layout.addWidget(self.progress_bar)

        card.content_layout.addWidget(progress_wrap)
        return card

    def _create_form_selector(self) -> SearchableComboBox:
        available = list(sync_service.get_available_forms() or [])
        items = [(FORM_ALL_TEXT, "", FORM_ALL_DATA)]
        items.extend((name, "", name) for name in available)
        items.append((FORM_DEFAULT_TEXT, "", FORM_DEFAULT_DATA))
        self.form_selector = SearchableComboBox(placeholder="请选择同步范围", searchable=True, items=items)
        self.form_selector.setMinimumHeight(40)
        self.form_selector.setCurrentIndex(0)
        self.form_selector.currentIndexChanged.connect(self._on_manual_selection_changed)
        self.gui.form_selector = self.form_selector
        return self.form_selector

    def _create_mode_selector(self) -> SearchableComboBox:
        mode_items = [
            ("增量（推荐）", "", "incremental"),
            ("全量", "", "full"),
            ("完整同步", "", "complete"),
        ]
        self.sync_type_combo = SearchableComboBox(placeholder="请选择同步模式", searchable=False, items=mode_items)
        self.sync_type_combo.setMinimumHeight(40)
        self.sync_type_combo.setCurrentIndex(0)
        self.sync_type_combo.currentIndexChanged.connect(self._on_manual_selection_changed)
        self.gui.sync_type_combo = self.sync_type_combo
        return self.sync_type_combo

    def _current_manual_selection_payload(self) -> tuple[str, str, str]:
        form_data = self._combo_selected_data(self.form_selector, default=FORM_ALL_DATA)
        mode_data = self._combo_selected_data(self.sync_type_combo, default="incremental")

        if form_data == FORM_DEFAULT_DATA:
            scope = "default"
            selected_form = ""
        elif form_data == FORM_ALL_DATA or not form_data:
            scope = "all"
            selected_form = ""
        else:
            scope = "single"
            selected_form = str(form_data)

        normalized_mode = str(mode_data or "incremental").strip().lower()
        if normalized_mode not in {"incremental", "full", "complete"}:
            normalized_mode = "incremental"
        return scope, selected_form, normalized_mode

    def _persist_manual_selection(self) -> None:
        if self._loading_defaults:
            return

        try:
            scope, selected_form, mode = self._current_manual_selection_payload()
            config_manager.update_config("SYNC", SYNC_UI_SCOPE_KEY, scope)
            config_manager.update_config("SYNC", SYNC_UI_FORM_KEY, selected_form)
            config_manager.update_config("SYNC", SYNC_UI_MODE_KEY, mode)
        except Exception as exc:  # pragma: no cover - persistence failure shouldn't block UI
            logger.warning("Failed to persist sync UI selection: %s", exc)

    def _refresh_selection_summary(self) -> None:
        mode_text = self.sync_type_combo.currentText() or "增量（推荐）"
        form_text = self.form_selector.currentText() or FORM_ALL_TEXT
        self.summary_mode.set_data(mode_text, "当前保存的同步模式。")
        self.summary_target.set_data(form_text, "当前保存的同步范围。")

    def _on_manual_selection_changed(self, *_args) -> None:
        if self._loading_defaults:
            return
        self._persist_manual_selection()
        self._refresh_selection_summary()

    def start_sync(self) -> None:
        if self.sync_worker is not None and self.sync_worker.isRunning():
            UiFeedback.warning(self, "任务正在运行", "请等待当前同步结束后再启动新的任务。")
            return

        form_selection = self.form_selector.currentText() or FORM_ALL_TEXT
        form_data = self._combo_selected_data(self.form_selector, default=FORM_ALL_DATA)
        sync_mode_text = self.sync_type_combo.currentText() or "增量（推荐）"
        mode_data = self._combo_selected_data(self.sync_type_combo, default="incremental")
        forms = None
        if form_data == FORM_DEFAULT_DATA:
            default_forms = sync_service.get_sync_config().get("default_forms", [])
            if not default_forms:
                UiFeedback.info(
                    self,
                    "未配置默认表单",
                    "请先在“表单配置”页设置默认表单列表后再使用该快捷方式。",
                )
                return
            forms = default_forms
        elif form_data != FORM_ALL_DATA:
            forms = [str(form_data)]

        if mode_data == "full":
            sync_type = SyncType.FULL
        elif mode_data == "complete":
            sync_type = SyncType.COMPLETE
        else:
            sync_type = SyncType.INCREMENTAL

        try:
            sync_service.save_sync_preferences(forms, sync_type)
        except Exception as exc:  # pragma: no cover - preferences are non-critical
            logger.warning("Failed to save sync preferences: %s", exc)

        self.summary_mode.set_data(sync_mode_text, "本次运行将使用所选同步模式。")
        self.summary_target.set_data(form_selection, "可选择全部表单、单个表单或默认表单集合。")
        self.summary_progress.set_data("0%", "任务已创建，等待开始执行。")
        self.summary_result.set_data("--", "工作线程完成后将汇总插入与更新数量。")

        self.start_sync_btn.set_loading(True, LoadingText.SYNC)
        self.progress_bar.setValue(0)
        self._set_run_state("info", "运行中")
        self._set_hero_hint("同步任务已提交，正在运行。", "info")
        self.reset_stats()
        self.log_text.clear()
        self.append_log("开始同步任务。", "INFO")
        self.append_log(f"目标范围：{form_selection}", "INFO")
        self.append_log(f"同步模式：{sync_mode_text}", "INFO")
        self.append_log("-" * 40, "INFO")

        self.sync_worker = SyncWorker(forms, sync_type, service=sync_service)
        self.sync_worker.progress.connect(self.on_sync_progress)
        self.sync_worker.finished.connect(self.on_sync_finished)
        self.sync_worker.start()

    def on_sync_progress(self, msg, val) -> None:
        self.append_log(msg)
        if val >= 0:
            self.progress_bar.setValue(val)
            self.summary_progress.set_data(f"{val}%", "实时执行进度。")
            self.progress_status_lbl.setText(f"{val}%")
            self._set_hero_hint(f"同步正在运行，当前进度：{val}%。", "info")

    def on_sync_finished(self, result) -> None:
        self.start_sync_btn.set_loading(False)
        self.sync_timer.stop()
        QTimer.singleShot(3000, lambda: self.start_sync_btn.setText(ButtonText.START_SYNC))
        self.append_log("-" * 40, "INFO")

        status = result.get("status")
        details = result.get("details", {})
        success_forms = 0
        failed_forms = []
        total_inserted = 0
        total_updated = 0
        if isinstance(details, dict):
            for form_name, stats in details.items():
                if isinstance(stats, dict):
                    total_inserted += int(stats.get("inserted", 0) or 0)
                    total_updated += int(stats.get("updated", 0) or 0)
                    if stats.get("status") == "success":
                        success_forms += 1
                    else:
                        failed_forms.append(form_name)

        self.synced_count = total_inserted + total_updated
        self.exec_count_card.set_data(str(self.synced_count), "最终插入与更新的记录总数。")
        result_message = result.get("message") or "执行结束。"
        self.summary_result.set_data(f"插入 {total_inserted} / 更新 {total_updated}", result_message)
        self.summary_progress.set_data("100%", "同步工作线程已完成。")
        self.progress_bar.setValue(100)
        button_text = "同步完成"

        if status == "success":
            button_text = "同步成功"
            self.append_log(f"同步任务成功完成：{result_message}", "SUCCESS")
            self._set_run_state("success", "成功")
            self._set_hero_hint("同步任务已成功完成。", "success")
            self.exec_rate_card.set_data("成功", "所有目标表单均已完成且无错误。")
        elif status == "partial":
            button_text = "部分成功"
            self.append_log(f"同步任务部分成功：{result_message}", "WARNING")
            if failed_forms:
                self.append_log(f"异常表单：{', '.join(failed_forms)}", "WARNING")
            self._set_run_state("info", "部分成功")
            self._set_hero_hint("同步已完成，但仍有部分表单需要复核。", "info")
            subtitle = f"成功表单：{success_forms}。异常表单：{len(failed_forms)}。"
            self.exec_rate_card.set_data("部分成功", subtitle)
        else:
            button_text = "同步失败"
            self.append_log(f"同步任务失败：{result_message}", "ERROR")
            if failed_forms:
                self.append_log(f"失败表单：{', '.join(failed_forms)}", "ERROR")
            self._set_run_state("danger", "失败")
            self._set_hero_hint("同步任务失败，请查看实时日志获取详情。", "danger")
            self.exec_rate_card.set_data("失败", "请查看实时日志与返回的错误信息。")

        self.start_sync_btn.setText(button_text)

        self.append_log("同步汇总：", "INFO")
        self.append_log(f"插入 {total_inserted} 条记录，更新 {total_updated} 条记录。", "INFO")
        if isinstance(details, dict):
            for form in sorted(details.keys()):
                stats = details[form]
                if isinstance(stats, dict):
                    self.append_log(
                        f"{form}：插入 {stats.get('inserted', 0)}，更新 {stats.get('updated', 0)}。",
                        "INFO",
                    )

        if hasattr(self.gui, "refresh_dashboard"):
            self.gui.refresh_dashboard()

    def test_connection(self) -> None:
        if self.test_worker and self.test_worker.isRunning():
            return
        self.test_conn_btn.set_loading(True, LoadingText.TEST)
        self._set_hero_hint("正在执行连接检查。", "info")
        self.update_test_status("正在执行连接检查...", False)
        self.test_worker = TestWorker(service=sync_service)
        self.test_worker.finished.connect(self.on_test_finished)
        self.test_worker.start()

    def on_test_finished(self, api_ok, db_ok, msg) -> None:
        self.test_conn_btn.set_loading(False)
        if api_ok and db_ok:
            self._set_hero_hint("连接测试通过，工作区已就绪。", "success")
            self.update_test_status("连接正常，可以开始同步。", False)
        else:
            self._set_hero_hint("连接测试失败，请先修正配置再运行同步。", "danger")
            self.update_test_status("连接测试失败，请检查 API 与数据库配置。", True)
            if msg:
                UiFeedback.warning(self, "连接测试失败", f"连接测试未通过：\n{msg}")

    def load_smart_defaults(self) -> None:
        config = sync_service.get_sync_config()
        self._loading_defaults = True
        try:
            scope = str(config.get(SYNC_UI_SCOPE_KEY, "") or "").strip().lower()
            selected_form = str(config.get(SYNC_UI_FORM_KEY, "") or "").strip()

            default_forms = config.get("default_forms", [])
            if scope == "default":
                self._set_combo_selected_by_data(self.form_selector, FORM_DEFAULT_DATA)
            elif scope == "single" and selected_form:
                if not self._set_combo_selected_by_data(self.form_selector, selected_form):
                    if len(default_forms) == 1:
                        self._set_combo_selected_by_data(self.form_selector, default_forms[0])
                    elif default_forms:
                        self._set_combo_selected_by_data(self.form_selector, FORM_DEFAULT_DATA)
            elif scope == "all":
                self._set_combo_selected_by_data(self.form_selector, FORM_ALL_DATA)
            elif default_forms:
                if len(default_forms) == 1:
                    self._set_combo_selected_by_data(self.form_selector, default_forms[0])
                else:
                    self._set_combo_selected_by_data(self.form_selector, FORM_DEFAULT_DATA)
            else:
                self._set_combo_selected_by_data(self.form_selector, FORM_ALL_DATA)

            sync_type = str(config.get(SYNC_UI_MODE_KEY, config.get("sync_type", "incremental"))).strip().lower()
            if sync_type not in ("incremental", "full", "complete"):
                sync_type = "incremental"
            self._set_combo_selected_by_data(self.sync_type_combo, sync_type)
        finally:
            self._loading_defaults = False

        self._set_run_state("neutral", "空闲")
        self._set_hero_hint("已加载保存的同步默认值，可直接启动任务。", "neutral")
        self._refresh_selection_summary()
        self.summary_result.set_data("--", "等待下一次同步结果。")
        self._persist_manual_selection()

    def reset_stats(self) -> None:
        self.synced_count = 0
        self.success_count = 0
        self.fail_count = 0
        self.start_time = datetime.now()
        self.exec_count_card.set_data("0", "本次运行累计插入与更新的行数。")
        self.exec_time_card.set_data("00:00:00", "本次运行的实时用时。")
        self.exec_rate_card.set_data("运行中", "任务正在执行。")
        self.progress_status_lbl.setText("启动中")
        self.sync_timer.start(1000)

    def _update_time_elapsed(self) -> None:
        if self.start_time:
            delta = datetime.now() - self.start_time
            seconds = int(delta.total_seconds())
            h = seconds // 3600
            m = (seconds % 3600) // 60
            s = seconds % 60
            self.exec_time_card.set_data(f"{h:02}:{m:02}:{s:02}", "本次运行的实时用时。")

    def _set_run_state(self, tone, text) -> None:
        normalized_tone = "neutral" if tone == "neutral" else tone
        for widget in (self.run_state_badge, self.hero_status):
            widget.setText(text)
            widget.setProperty("tone", normalized_tone)
            style = widget.style()
            if style is not None:
                style.unpolish(widget)
                style.polish(widget)
        self.progress_status_lbl.setText(text)

    def _set_hero_hint(self, text: str, tone: str) -> None:
        self.hero_hint.setText(text)
        self.hero_hint.setProperty("tone", tone)
        style = self.hero_hint.style()
        if style is not None:
            style.unpolish(self.hero_hint)
            style.polish(self.hero_hint)

    def update_test_status(self, msg, is_error=False) -> None:
        self.test_status_lbl.setText(msg)
        self.test_status_lbl.setProperty("ui", "win11-helper-text-danger" if is_error else "win11-helper-text-success")
        style = self.test_status_lbl.style()
        if style is not None:
            style.unpolish(self.test_status_lbl)
            style.polish(self.test_status_lbl)

    def _apply_workspace_layout(self) -> None:
        if hasattr(self, "workspace_splitter") and self.workspace_splitter is not None:
            if self.width() <= 1366:
                self.workspace_splitter.setOrientation(Qt.Orientation.Vertical)
                self.config_container.setMinimumWidth(0)
                self.config_container.setMaximumWidth(16777215)
                if hasattr(self, "execution_card"):
                    self.execution_card.setMaximumHeight(320)
                self.log_text.setMinimumHeight(180)
                top_height = max(320, int(self.height() * 0.44))
                bottom_height = max(360, self.height() - top_height)
                self.workspace_splitter.setSizes([top_height, bottom_height])
            else:
                self.workspace_splitter.setOrientation(Qt.Orientation.Horizontal)
                self.config_container.setMinimumWidth(420)
                self.config_container.setMaximumWidth(420)
                if hasattr(self, "execution_card"):
                    self.execution_card.setMaximumHeight(16777215)
                self.log_text.setMinimumHeight(220)
                self.workspace_splitter.setSizes([540, 980])

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._apply_workspace_layout()
        super().resizeEvent(event)

    def clear_log(self) -> None:
        self.log_text.clear()

    def copy_log(self) -> None:
        content = self.log_text.toPlainText().strip()
        if not content:
            UiFeedback.info(self, "无内容可复制", "实时日志当前为空。")
            return
        QApplication.clipboard().setText(content)
        UiFeedback.success(self, "已复制", "已将实时日志复制到剪贴板。")

    def export_log(self) -> None:
        content = self.log_text.toPlainText()
        if not content:
            UiFeedback.info(self, "无日志可导出", "实时日志当前为空。")
            return
        try:
            log_dir = app_logger.get_log_dir()
            path = os.path.join(log_dir, f"sync_export_{datetime.now().strftime('%Y%m%d%H%M%S')}.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(content)
            UiFeedback.success(self, "导出完成", f"日志已导出到：\n{path}")
        except Exception as exc:  # pragma: no cover - filesystem guard
            UiFeedback.error(self, "导出失败", f"无法导出实时日志：\n{exc}")

    def append_log(self, msg, level="INFO") -> None:
        color = ColorTokens.TEXT_SECONDARY
        message = str(msg)
        upper_msg = message.upper()
        if level == "ERROR":
            color = ColorTokens.DANGER
            self.fail_count += 1
        elif level == "WARNING":
            color = ColorTokens.WARNING
        elif level == "SUCCESS":
            color = ColorTokens.SUCCESS
            self.success_count += 1
        elif "FAILED" in upper_msg:
            color = ColorTokens.DANGER
            self.fail_count += 1
        elif "ERROR" in upper_msg or "EXCEPTION" in upper_msg:
            color = ColorTokens.WARNING
        elif "SUCCESS" in upper_msg:
            color = ColorTokens.SUCCESS
            self.success_count += 1

        time_str = datetime.now().strftime("%H:%M:%S")
        html_text = (
            f'<span style="color: {ColorTokens.TEXT_DISABLED};">[{time_str}]</span> '
            f'<span style="color: {color};">{html.escape(message)}</span>'
        )
        self.log_text.append(html_text)
        if self.auto_scroll_cb.isChecked():
            sb = self.log_text.verticalScrollBar()
            sb.setValue(sb.maximum())
