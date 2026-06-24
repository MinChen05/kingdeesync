"""Sync execution page built on the shared Windows 11 page scaffold."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from types import MethodType

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.config.config_manager import config_manager
from src.gui.components.buttons import LoadingButton
from src.gui.components.combobox import SearchableComboBox
from src.gui.components.common import SvgIconLabel
from src.gui.components.data_table import DataTable
from src.gui.components.page_shell import Win11PageScaffold, Win11SectionCard, Win11SummaryCard
from src.gui.design_tokens import ColorTokens, SizeTokens, SpacingTokens
from src.gui.feedback import UiFeedback
from src.gui.pages._sync_progress_card import SyncProgressCard
from src.gui.ui_text import ButtonText, LoadingText
from src.gui.workers import SyncWorker, TestWorker
from src.services.sync_service import SyncType, sync_service
from src.utils import logger as app_logger

logger = logging.getLogger(__name__)

FORM_ALL_TEXT = "同步全部表单"
FORM_DEFAULT_TEXT = "默认表单集合"
FORM_ALL_DATA = "__ALL__"
FORM_DEFAULT_DATA = "__DEFAULT__"
SYNC_UI_SCOPE_KEY = "ui_manual_scope"
SYNC_UI_FORM_KEY = "ui_manual_form"
SYNC_UI_MODE_KEY = "ui_manual_mode"
SYNC_TONE_COLORS = {
    "blue": ColorTokens.SYNC_TONE_BLUE,
    "green": ColorTokens.SYNC_TONE_GREEN,
    "slate": ColorTokens.SYNC_TONE_SLATE,
}


class SyncOverviewCard(Win11SummaryCard):
    """Compact overview card for the sync workspace."""

    def __init__(
        self,
        title: str,
        value: str = "--",
        subtitle: str = "",
        *,
        icon_file: str,
        tone: str,
        parent=None,
    ):
        QFrame.__init__(self, parent)
        self.setProperty("ui", "win11-summary-card")
        self.setProperty("sync-summary-tone", tone)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(16)

        self.icon_wrap = QFrame(self)
        self.icon_wrap.setProperty("ui", "sync-summary-icon-wrap")
        self.icon_wrap.setProperty("tone", tone)
        self.icon_wrap.setFixedSize(52, 52)
        icon_layout = QHBoxLayout(self.icon_wrap)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label = SvgIconLabel(icon_file, size=28, icon_size=24, color=SYNC_TONE_COLORS.get(tone, SYNC_TONE_COLORS["blue"]))
        icon_layout.addWidget(self.icon_label)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(6)

        self.title_label = QLabel(title)
        self.title_label.setProperty("ui", "win11-summary-title")
        self.value_label = QLabel(value)
        self.value_label.setProperty("ui", "win11-summary-value")
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setProperty("ui", "win11-helper-text")
        self.subtitle_label.setVisible(False)

        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.value_label)
        layout.addWidget(self.icon_wrap, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(text_layout, 1)

    def set_data(self, value: str, subtitle: str | None = None) -> None:
        self.set_value(value)
        if subtitle is not None:
            self.set_subtitle(subtitle)


class SyncPage(Win11PageScaffold):
    def __init__(self, parent_gui, parent=None):
        self.gui = parent_gui
        self.start_time = None
        self.synced_count = 0
        self.success_count = 0
        self.fail_count = 0
        self.sync_worker = None
        self.test_worker = None
        self._last_test_message = ""
        self._loading_defaults = False
        self.log_entries: list[str] = []
        super().__init__(
            title="同步执行",
            eyebrow="同步",
            subtitle="选择同步范围，检查连接后手动发起本次同步。",
            parent=parent,
        )
        self.setProperty("page", "sync")
        self.setObjectName("sync_execution_page")
        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self._update_time_elapsed)
        self.setup_ui()
        self.load_smart_defaults()

    def setup_ui(self) -> None:
        self._build_hero()
        self.set_hero_visible(True)
        self.hero_card.setMinimumHeight(82)
        self.hero_card.setMaximumHeight(88)
        self.hero_title.setMinimumHeight(42)
        self._build_summary_strip()
        self.primary_action_layout.addStretch(1)
        self.add_primary_action(self.test_conn_btn)
        self.add_primary_action(self.start_sync_btn)
        self.add_primary_action(self.cancel_sync_btn)
        self.primary_action_layout.setContentsMargins(0, 0, 0, 12)
        self.primary_action_host.setMinimumHeight(58)
        self.primary_action_host.setMaximumHeight(60)
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
        meta_layout = QHBoxLayout(meta_widget)
        meta_layout.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        meta_layout.setSpacing(SpacingTokens.SM)

        status_title = QLabel("状态：")
        status_title.setProperty("ui", "sync-hero-status-title")
        self.hero_status = QLabel("空闲")
        self.hero_status.setProperty("ui", "sync-hero-status-value")
        self.hero_status.setProperty("tone", "neutral")

        self.hero_hint = QLabel("准备一次从金蝶到 SQL Server 的手动同步。")
        self.hero_hint.setProperty("ui", "win11-meta-text")
        self.hero_hint.setProperty("tone", "neutral")
        self.hero_hint.setWordWrap(True)
        self.hero_hint.setVisible(False)

        meta_layout.addWidget(status_title)
        meta_layout.addWidget(self.hero_status)

        self.start_sync_btn = LoadingButton(ButtonText.START_SYNC)
        self.start_sync_btn.setProperty("class", "primary")
        self.start_sync_btn.setFixedWidth(136)
        self.start_sync_btn.setFixedHeight(38)
        self.start_sync_btn.clicked.connect(self.start_sync)
        self.gui.start_sync_btn = self.start_sync_btn

        self.test_conn_btn = LoadingButton(ButtonText.TEST_CONNECTION)
        self.test_conn_btn.setProperty("class", "secondary")
        self.test_conn_btn.setFixedWidth(136)
        self.test_conn_btn.setFixedHeight(38)
        self.test_conn_btn.clicked.connect(self.test_connection)
        self.gui.test_conn_btn = self.test_conn_btn

        self.cancel_sync_btn = QPushButton("取消说明")
        self.cancel_sync_btn.setProperty("class", "secondary")
        self.cancel_sync_btn.setFixedWidth(136)
        self.cancel_sync_btn.setFixedHeight(38)
        self.cancel_sync_btn.setEnabled(False)
        self.cancel_sync_btn.clicked.connect(self.cancel_sync)

        self.add_hero_widget(meta_widget)

    def _build_summary_strip(self) -> None:
        self.summary_mode = SyncOverviewCard("同步模式", "--", "日常运行建议使用增量同步。", icon_file="sync_mode.svg", tone="blue")
        self.summary_target = SyncOverviewCard("目标范围", "--", "可选择全部表单、单个表单或默认表单集合。", icon_file="sync_target.svg", tone="green")
        self.summary_progress = SyncOverviewCard("进度", "0%", "任务尚未开始。", icon_file="sync_progress.svg", tone="blue")
        self.summary_result = SyncOverviewCard("最近结果", "--", "同步完成后将汇总插入与更新数量。", icon_file="sync_result.svg", tone="slate")

        for idx, card in enumerate((self.summary_mode, self.summary_target, self.summary_progress, self.summary_result), start=1):
            card.setProperty("sync-card-index", idx)
            card.setMinimumHeight(136)
            card.setMaximumHeight(140)
            self.add_summary_card(card)
        self.summary_strip.setMinimumHeight(138)
        self.summary_strip.setMaximumHeight(142)

    def _create_workspace(self) -> QWidget:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        root_layout.setSpacing(SpacingTokens.MD)

        self.stepper_strip = self._create_stepper_strip()
        root_layout.addWidget(self.stepper_strip)

        self.launchpad_core = QFrame()
        self.launchpad_core.setProperty("ui", "sync-launchpad-core")
        self.launchpad_core.setMaximumHeight(376)
        core_layout = QHBoxLayout(self.launchpad_core)
        core_layout.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        core_layout.setSpacing(SpacingTokens.MD)
        root_layout.addWidget(self.launchpad_core)

        self.config_container = QWidget()
        self.config_container.setProperty("ui", "win11-workspace-column")
        self.config_container.setObjectName("sync_config_column")
        self.config_container.setMinimumWidth(300)
        config_layout = QVBoxLayout(self.config_container)
        config_layout.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        config_layout.setSpacing(SpacingTokens.MD)
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
                        "增量适合日常；完全同步更适合修复或重建场景。",
                        self._create_mode_selector(),
                        last=True,
                    ),
                ],
            )
        )

        self.ops_strip = QLabel("流程：选择范围 -> 检查连接 -> 开始同步")
        self.ops_strip.setProperty("ui", "win11-inline-banner")
        self.ops_strip.setWordWrap(True)
        config_layout.addWidget(self.ops_strip)

        self.test_status_lbl = QLabel("")
        self.test_status_lbl.setProperty("ui", "win11-helper-text")
        self.test_status_lbl.setWordWrap(True)
        config_layout.addWidget(self.test_status_lbl)

        config_layout.addStretch(1)
        core_layout.addWidget(self.config_container, 1)

        self.monitor_container = QWidget()
        self.monitor_container.setProperty("ui", "win11-workspace-column")
        self.monitor_container.setObjectName("sync_monitor_column")
        monitor_layout = QVBoxLayout(self.monitor_container)
        monitor_layout.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        monitor_layout.setSpacing(SpacingTokens.MD)
        self.execution_card = self._create_execution_card()
        monitor_layout.addWidget(self.execution_card)
        monitor_layout.addStretch(1)
        core_layout.addWidget(self.monitor_container, 2)

        self.preflight_card = self._create_preflight_card()
        core_layout.addWidget(self.preflight_card, 1)

        root_layout.addStretch(1)

        return root

    def _create_stepper_strip(self) -> QFrame:
        strip = QFrame()
        strip.setObjectName("sync_launchpad_steps")
        strip.setProperty("ui", "sync-stepper-strip")
        layout = QHBoxLayout(strip)
        layout.setContentsMargins(90, 16, 90, 16)
        layout.setSpacing(0)

        steps = [
            ("1", "选择范围"),
            ("2", "连接预检"),
            ("3", "执行同步"),
            ("4", "完成结果"),
        ]
        self.step_labels = []
        for index, (number, label) in enumerate(steps):
            item = QFrame()
            item.setProperty("ui", "sync-step-item")
            item.setProperty("active", index == 0)
            item_layout = QHBoxLayout(item)
            item_layout.setContentsMargins(SpacingTokens.MD, SpacingTokens.XS, SpacingTokens.MD, SpacingTokens.XS)
            item_layout.setSpacing(SpacingTokens.SM)

            badge = QLabel(number)
            badge.setProperty("ui", "sync-step-badge")
            badge.setProperty("active", index == 0)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFixedSize(22, 22)
            text = QLabel(label)
            text.setProperty("ui", "sync-step-text")
            text.setProperty("active", index == 0)
            item_layout.addWidget(badge)
            item_layout.addWidget(text)
            layout.addWidget(item, 1)
            self.step_labels.append((item, badge, text))
            if index < len(steps) - 1:
                arrow = QLabel("›")
                arrow.setProperty("ui", "sync-step-arrow")
                arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(arrow)

        return strip

    def _create_preflight_card(self) -> Win11SectionCard:
        card = Win11SectionCard("运行前检查", "")
        card.setProperty("sync-section", "preflight")
        card.setMinimumHeight(376)
        card.setMaximumHeight(376)
        self.preflight_api_value = self._add_preflight_item(card.content_layout, "金蝶 API", "未检测", "neutral")
        self.preflight_db_value = self._add_preflight_item(card.content_layout, "SQL Server", "未检测", "neutral")
        self.preflight_test_time_value = self._add_preflight_item(card.content_layout, "最近检测", "--", "neutral")
        self.preflight_scope_value = self._add_preflight_item(card.content_layout, "表单范围", "--", "neutral")
        self.preflight_mode_value = self._add_preflight_item(card.content_layout, "同步模式", "--", "neutral")
        return card

    def _add_preflight_item(self, layout, title: str, value: str, tone: str) -> QLabel:
        item = QFrame()
        item.setProperty("ui", "sync-preflight-item")
        item_layout = QHBoxLayout(item)
        item_layout.setContentsMargins(SpacingTokens.MD, SpacingTokens.SM, SpacingTokens.MD, SpacingTokens.SM)
        item_layout.setSpacing(SpacingTokens.SM)

        title_label = QLabel(title)
        title_label.setProperty("ui", "sync-preflight-title")
        value_label = QLabel(value)
        value_label.setProperty("ui", "sync-preflight-value")
        value_label.setProperty("tone", tone)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        value_label.setMinimumWidth(84)

        item_layout.addWidget(title_label)
        item_layout.addStretch(1)
        item_layout.addWidget(value_label)
        layout.addWidget(item)
        return value_label

    def _create_group_card(self, title_text: str, subtitle_text: str, rows: list[QWidget]) -> Win11SectionCard:
        card = Win11SectionCard(title_text, "")
        card.setProperty("sync-section", "config")
        card.setMinimumHeight(376)
        card.setMaximumHeight(376)
        for row in rows:
            card.content_layout.addWidget(row)
        return card

    def _create_setting_row(self, title_text: str, note_text: str, editor: QWidget, *, last: bool = False) -> QFrame:
        editor.setMinimumWidth(220)
        editor.setProperty("td", "win11-input")
        row = QFrame()
        row.setProperty("ui", "win11-setting-row")
        row.setProperty("last", last)
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 14, 0, 14)
        layout.setSpacing(14)
        title = QLabel(title_text)
        title.setProperty("ui", "win11-row-title")
        layout.addWidget(title)
        layout.addWidget(editor)
        return row

    def _create_strategy_card(self) -> Win11SectionCard:
        card = Win11SectionCard(
            "运行建议",
            "通过明确配置与可观测日志降低运行风险。",
        )

        tips = [
            "日常建议使用增量同步，避免 API 压力与数据库写入峰值过高。",
            "完整同步建议在低峰时段执行，详细日志可在日志中心查看。",
            "若连接测试失败，请先修正配置，再发起新的同步尝试。",
        ]
        for idx, text in enumerate(tips, start=1):
            item = QFrame()
            item.setProperty("ui", "win11-inline-card")
            row = QHBoxLayout(item)
            row.setContentsMargins(SpacingTokens.MD, SpacingTokens.MD, SpacingTokens.MD, SpacingTokens.MD)
            row.setSpacing(SpacingTokens.ACTION_BAR_GAP)

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
        card = Win11SectionCard("执行状态", "")
        card.setProperty("sync-section", "execution")
        card.setMinimumHeight(376)
        card.setMaximumHeight(376)

        header = QHBoxLayout()
        header.addStretch(1)

        self.run_state_badge = QLabel("空闲")
        self.run_state_badge.setProperty("ui", "win11-status-chip")
        self.run_state_badge.setProperty("tone", "neutral")
        header.addWidget(self.run_state_badge)
        card.content_layout.addLayout(header)
        card.content_layout.addStretch(1)

        metrics = QHBoxLayout()
        metrics.setSpacing(36)
        self.exec_count_card = self._create_execution_metric("已同步记录", "0", "sync_record.svg", "blue")
        self.exec_time_card = self._create_execution_metric("已用时间", "00:00:00", "sync_runtime.svg", "green")
        self.exec_rate_card = self._create_execution_metric("运行状态", "空闲", "sync_status.svg", "blue")
        for card_item in (self.exec_count_card, self.exec_time_card, self.exec_rate_card):
            metrics.addWidget(card_item)
        card.content_layout.addLayout(metrics)
        card.content_layout.addStretch(1)

        self._progress_card = SyncProgressCard()
        self.progress_bar = self._progress_card.progress_bar
        self.progress_status_lbl = self._progress_card.progress_status_lbl
        card.content_layout.addWidget(self._progress_card)
        return card

    def _create_execution_metric(self, title: str, value: str, icon_file: str, tone: str) -> QFrame:
        card = QFrame()
        card.setProperty("ui", "win11-metric-card")
        card.setProperty("tone", tone)
        card.setMinimumHeight(126)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)

        icon_wrap = QFrame(card)
        icon_wrap.setProperty("ui", "sync-exec-icon-wrap")
        icon_wrap.setProperty("tone", tone)
        icon_wrap.setFixedSize(52, 52)
        icon_layout = QHBoxLayout(icon_wrap)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_layout.addWidget(
            SvgIconLabel(icon_file, size=28, icon_size=24, color=SYNC_TONE_COLORS.get(tone, SYNC_TONE_COLORS["blue"]))
        )

        card.title_label = QLabel(title)
        card.title_label.setProperty("ui", "win11-inline-title")
        card.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card.value_label = QLabel(value)
        card.value_label.setProperty("ui", "win11-inline-value")
        card.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card.note_label = QLabel("", card)
        card.note_label.setVisible(False)

        layout.addWidget(icon_wrap, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(card.title_label)
        layout.addWidget(card.value_label)

        def set_data(metric_card, metric_value: str, note: str | None = None) -> None:
            metric_card.value_label.setText(metric_value)
            if note is not None:
                metric_card.note_label.setText(note)
                metric_card.note_label.setVisible(False)

        card.set_data = MethodType(set_data, card)
        return card

    def _create_form_selector(self) -> SearchableComboBox:
        available = list(sync_service.get_available_forms() or [])
        items = [(FORM_ALL_TEXT, "", FORM_ALL_DATA)]
        items.extend((name, "", name) for name in available)
        items.append((FORM_DEFAULT_TEXT, "", FORM_DEFAULT_DATA))
        self.form_selector = SearchableComboBox(placeholder="请选择同步范围", searchable=True, items=items)
        self.form_selector.setMinimumHeight(SizeTokens.CONTROL_HEIGHT)
        self.form_selector.setCurrentIndex(0)
        self.form_selector.currentIndexChanged.connect(self._on_manual_selection_changed)
        self.gui.form_selector = self.form_selector
        return self.form_selector

    def _create_mode_selector(self) -> SearchableComboBox:
        mode_items = [
            ("增量（推荐）", "", "incremental"),
            ("完全同步", "", "complete"),
        ]
        self.sync_type_combo = SearchableComboBox(placeholder="请选择同步模式", searchable=False, items=mode_items)
        self.sync_type_combo.setMinimumHeight(SizeTokens.CONTROL_HEIGHT)
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
        if normalized_mode == "full":
            normalized_mode = "complete"
        if normalized_mode not in {"incremental", "complete"}:
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
        if hasattr(self, "preflight_scope_value"):
            self.preflight_scope_value.setText(form_text)
        if hasattr(self, "preflight_mode_value"):
            self.preflight_mode_value.setText("完全同步" if self._combo_selected_data(self.sync_type_combo) == "complete" else "增量同步")

    def _on_manual_selection_changed(self, *_args) -> None:
        if self._loading_defaults:
            return
        self._persist_manual_selection()
        self._refresh_selection_summary()

    def start_sync(self) -> None:
        if self.sync_worker is not None and self.sync_worker.isRunning():
            UiFeedback.warning(self, "任务正在运行", "请等待当前同步完成后再启动新的任务。")
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
                    "请先在“表单映射”页确认默认表单范围，再使用该快捷方式。",
                )
                return
            forms = default_forms
        elif form_data != FORM_ALL_DATA:
            forms = [str(form_data)]

        if mode_data in {"full", "complete"}:
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
        self.cancel_sync_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self._set_run_state("info", "运行中")
        self._set_hero_hint("同步任务已提交，正在运行。", "info")
        self.reset_stats()
        self.clear_log()
        self.append_log("开始同步任务。", "INFO")
        self.append_log(f"目标范围：{form_selection}", "INFO")
        self.append_log(f"同步模式：{sync_mode_text}", "INFO")
        self.append_log("-" * 40, "INFO")

        self.sync_worker = SyncWorker(forms, sync_type, service=sync_service)
        self.sync_worker.progress.connect(self.on_sync_progress)
        self.sync_worker.finished.connect(self.on_sync_finished)
        self.sync_worker.start()

    def cancel_sync(self) -> None:
        message = "当前同步任务暂不支持中途取消"
        self.append_log(message, "WARNING")
        self._set_hero_hint(message, "info")
        UiFeedback.info(self, "取消说明", "当前同步任务暂不支持中途取消，请等待本次运行完成。")

    def on_sync_progress(self, msg, val) -> None:
        self.append_log(msg)
        if val >= 0:
            self.progress_bar.setValue(val)
            self.summary_progress.set_data(f"{val}%", "实时执行进度。")
            self.progress_status_lbl.setText(f"{val}%")
            self._set_hero_hint(f"同步正在运行，当前进度：{val}%。", "info")

    def on_sync_finished(self, result) -> None:
        self.start_sync_btn.set_loading(False)
        self.cancel_sync_btn.setEnabled(False)
        self.sync_timer.stop()
        QTimer.singleShot(3000, lambda: self.start_sync_btn.setText(ButtonText.START_SYNC))
        self.append_log("-" * 40, "INFO")

        status = result.get("status")
        details = result.get("details", {})
        success_forms = 0
        failed_forms = []
        total_inserted = 0
        total_updated = 0
        total_records_fallback = int(result.get("total_records", 0) or 0)
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
        if self.synced_count <= 0 and total_records_fallback > 0:
            self.synced_count = total_records_fallback
        self.exec_count_card.set_data(str(self.synced_count), "最终插入与更新的记录总数。")
        result_message = result.get("message") or "执行结束。"
        if total_inserted or total_updated:
            result_value = f"插入 {total_inserted} / 更新 {total_updated}"
        elif total_records_fallback > 0:
            result_value = f"共 {total_records_fallback} 条"
        else:
            result_value = "--"
        self.summary_result.set_data(result_value, result_message)
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
            self._set_hero_hint("同步任务失败，请查看日志中心获取详情。", "danger")
            self.exec_rate_card.set_data("失败", "请查看日志中心与返回的错误信息。")

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
        self._last_test_message = msg or ""
        self._update_preflight_connection_status(api_ok, db_ok)
        if api_ok and db_ok:
            self._set_hero_hint("连接测试通过，工作区已就绪。", "success")
            self.update_test_status("连接正常，可以开始同步。", False)
        else:
            self._set_hero_hint("连接测试失败，请先修正配置再运行同步。", "danger")
            detail = f"连接测试失败，请检查 API 与数据库配置。{msg}" if msg else "连接测试失败，请检查 API 与数据库配置。"
            self.update_test_status(detail, True)
            if msg:
                UiFeedback.warning(self, "连接测试未通过", f"请检查金蝶 API 与 SQL Server 配置：\n{msg}")

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
            if sync_type == "full":
                sync_type = "complete"
            if sync_type not in ("incremental", "complete"):
                sync_type = "incremental"
            self._set_combo_selected_by_data(self.sync_type_combo, sync_type)
        finally:
            self._loading_defaults = False

        self._set_run_state("neutral", "空闲")
        self._set_hero_hint("已加载保存的同步默认值，可直接启动任务。", "neutral")
        self._refresh_selection_summary()
        self.summary_result.set_data("--", "等待下一次同步结果。")
        self._persist_manual_selection()
        self._refresh_selection_summary()

    def _update_preflight_connection_status(self, api_ok: bool, db_ok: bool) -> None:
        if not hasattr(self, "preflight_api_value"):
            return
        self._set_preflight_value(self.preflight_api_value, "正常" if api_ok else "异常", "success" if api_ok else "danger")
        self._set_preflight_value(self.preflight_db_value, "正常" if db_ok else "异常", "success" if db_ok else "danger")
        self._set_preflight_value(self.preflight_test_time_value, datetime.now().strftime("%H:%M:%S"), "neutral")

    def _set_preflight_value(self, label: QLabel, text: str, tone: str) -> None:
        label.setText(text)
        label.setProperty("tone", tone)
        style = label.style()
        if style is not None:
            style.unpolish(label)
            style.polish(label)

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
        if not hasattr(self, "launchpad_core"):
            return

        layout = self.launchpad_core.layout()
        if layout is None:
            return

        if self.width() < 960:
            layout.setDirection(QHBoxLayout.Direction.TopToBottom)
            self.config_container.setMinimumWidth(0)
            self.monitor_container.setMinimumWidth(0)
            self.preflight_card.setMinimumWidth(0)
            if hasattr(self, "execution_card"):
                self.execution_card.setMaximumHeight(SizeTokens.SYNC_EXECUTION_CARD_MAX_HEIGHT_COMPACT)
        else:
            layout.setDirection(QHBoxLayout.Direction.LeftToRight)
            self.config_container.setMinimumWidth(300)
            self.monitor_container.setMinimumWidth(460)
            self.preflight_card.setMinimumWidth(320)
            if hasattr(self, "execution_card"):
                self.execution_card.setMaximumHeight(376)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._apply_workspace_layout()
        super().resizeEvent(event)

    def clear_log(self) -> None:
        self.log_entries.clear()

    def copy_log(self) -> None:
        content = "\n".join(self.log_entries).strip()
        if not content:
            UiFeedback.info(self, "暂无可复制内容", "本次同步还没有可复制的日志。")
            return
        QApplication.clipboard().setText(content)
        UiFeedback.success(self, "复制完成", "本次同步日志已复制到剪贴板。")

    def export_log(self) -> None:
        content = "\n".join(self.log_entries)
        if not content:
            UiFeedback.info(self, "暂无可导出日志", "本次同步还没有可导出的日志。")
            return
        try:
            log_dir = app_logger.get_log_dir()
            path = os.path.join(log_dir, f"sync_export_{datetime.now().strftime('%Y%m%d%H%M%S')}.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(content)
            UiFeedback.success(self, "导出完成", f"本次同步日志已导出：\n{path}")
        except Exception as exc:  # pragma: no cover - filesystem guard
            UiFeedback.error(self, "导出失败", f"本次同步日志导出失败：\n{exc}")

    def append_log(self, msg, level="INFO") -> None:
        message = str(msg)
        upper_msg = message.upper()
        if level == "ERROR":
            self.fail_count += 1
        elif level == "WARNING":
            pass
        elif level == "SUCCESS":
            self.success_count += 1
        elif "FAILED" in upper_msg:
            self.fail_count += 1
        elif "ERROR" in upper_msg or "EXCEPTION" in upper_msg:
            pass
        elif "SUCCESS" in upper_msg:
            self.success_count += 1

        time_str = datetime.now().strftime("%H:%M:%S")
        self.log_entries.append(f"[{time_str}] [{level}] {message}")
