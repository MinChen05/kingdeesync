"""Sync execution page — compact, single-flow layout."""

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
    QTextEdit,
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


# ---------------------------------------------------------------------------
# Compact metric card reused for summary + execution
# ---------------------------------------------------------------------------

class _CompactMetric(QFrame):
    """Single-line metric: icon + value + label, used in summary and execution cards."""

    def __init__(self, icon_file: str, label: str, value: str, tone: str = "blue", parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(8)
        icon = SvgIconLabel(icon_file, size=22, icon_size=18, color=SYNC_TONE_COLORS.get(tone, SYNC_TONE_COLORS["blue"]))
        layout.addWidget(icon)
        text_wrap = QVBoxLayout()
        text_wrap.setSpacing(0)
        self._value = QLabel(value)
        self._value.setStyleSheet("font-size: 14px; font-weight: 700; color: #14263A;")
        self._label = QLabel(label)
        self._label.setStyleSheet("font-size: 11px; color: #8CA3B6;")
        text_wrap.addWidget(self._value)
        text_wrap.addWidget(self._label)
        layout.addLayout(text_wrap, 1)

    def set_data(self, value: str, _note: str | None = None) -> None:
        self._value.setText(value)


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

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
            subtitle="",
            parent=parent,
        )
        self.setProperty("page", "sync")
        self.setObjectName("sync_execution_page")
        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self._update_time_elapsed)
        self._build_page()
        self.load_smart_defaults()

    # -- UI build ---------------------------------------------------------------

    def _build_page(self) -> None:
        """Full custom layout — scaffold hero/summary/action host are hidden."""
        self.set_hero_visible(False)
        self.hero_card.setVisible(False)
        self.primary_action_host.setVisible(False)
        self.summary_strip.setVisible(False)

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(SpacingTokens.LG, SpacingTokens.SM, SpacingTokens.LG, SpacingTokens.SM)
        layout.setSpacing(SpacingTokens.SM)

        # -- Toolbar: just status + cancel ---------------------------------------
        toolbar = QFrame()
        toolbar.setFixedHeight(32)
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(0, 0, 0, 0)

        self.hero_status = QLabel("空闲")
        self.hero_status.setStyleSheet("color: #8CA3B6; font-size: 13px; font-weight: 500;")
        self.hero_status.setProperty("tone", "neutral")
        tb.addWidget(QLabel("状态："))
        tb.addWidget(self.hero_status)
        tb.addStretch(1)

        self.cancel_sync_btn = QPushButton("取消")
        self.cancel_sync_btn.setStyleSheet(
            "QPushButton { background: #fff; border: 1px solid #D4E5F3; border-radius: 6px; "
            "padding: 4px 12px; font-size: 12px; color: #999; } "
            "QPushButton:hover { background: #F6FAFD; }"
        )
        self.cancel_sync_btn.setFixedHeight(28)
        self.cancel_sync_btn.setEnabled(False)
        self.cancel_sync_btn.clicked.connect(self.cancel_sync)
        tb.addWidget(self.cancel_sync_btn)

        layout.addWidget(toolbar)

        # -- Config + 开始同步 ----------------------------------------------------
        config_row = QFrame()
        config_row.setStyleSheet("QFrame { background: #F6FAFD; border-radius: 8px; }")
        config_row.setFixedHeight(52)
        cr = QHBoxLayout(config_row)
        cr.setContentsMargins(12, 0, 12, 0)
        cr.setSpacing(12)

        cr.addWidget(QLabel("表单范围"))
        available = list(sync_service.get_available_forms() or [])
        form_items = [(FORM_ALL_TEXT, "", FORM_ALL_DATA)]
        form_items.extend((name, "", name) for name in available)
        form_items.append((FORM_DEFAULT_TEXT, "", FORM_DEFAULT_DATA))
        self.form_selector = self._make_combo(SearchableComboBox(
            placeholder="", searchable=True,
            items=form_items,
        ))
        self.form_selector.setMinimumWidth(200)
        cr.addWidget(self.form_selector, 1)

        sep = QLabel("|")
        sep.setStyleSheet("color: #D4E5F3;")
        cr.addWidget(sep)

        cr.addWidget(QLabel("同步模式"))
        self.sync_type_combo = self._make_combo(SearchableComboBox(
            placeholder="", searchable=False,
            items=[("增量（推荐）", "", "incremental"), ("完全同步", "", "complete")],
        ))
        self.sync_type_combo.setMinimumWidth(140)
        cr.addWidget(self.sync_type_combo)

        cr.addSpacing(8)
        self.start_sync_btn = LoadingButton(ButtonText.START_SYNC)
        self.start_sync_btn.setStyleSheet(
            "LoadingButton { background: #4CA8F8; border: none; border-radius: 6px; "
            "padding: 6px 20px; font-size: 13px; font-weight: 600; color: #fff; } "
            "LoadingButton:hover { background: #2578DA; }"
        )
        self.start_sync_btn.setFixedHeight(34)
        self.start_sync_btn.clicked.connect(self.start_sync)
        self.gui.start_sync_btn = self.start_sync_btn
        cr.addWidget(self.start_sync_btn)

        layout.addWidget(config_row)

        # -- Preflight chips + 测试连接 --------------------------------------------
        preflight_row = QFrame()
        pr = QHBoxLayout(preflight_row)
        pr.setContentsMargins(0, 0, 0, 0)
        pr.setSpacing(8)
        labels = ["金蝶 API", "SQL Server", "最近检测", "表单范围"]
        values = ["未检测", "未检测", "--", "--"]
        attrs = ["preflight_api", "preflight_db", "preflight_test_time", "preflight_scope"]
        self._preflight_labels = {}
        for lbl, val, attr in zip(labels, values, attrs, strict=True):
            chip = QFrame()
            chip.setStyleSheet("QFrame { background: #EEF6FD; border-radius: 4px; }")
            chip.setFixedHeight(28)
            cl = QHBoxLayout(chip)
            cl.setContentsMargins(8, 0, 8, 0)
            cl.setSpacing(4)
            cl.addWidget(QLabel(lbl + ":"))
            vl = QLabel(val)
            vl.setStyleSheet("color: #8CA3B6; font-weight: 500;")
            cl.addWidget(vl)
            pr.addWidget(chip)
            setattr(self, attr + "_value", vl)
            self._preflight_labels[attr] = vl
        pr.addStretch(1)

        self.test_conn_btn = LoadingButton(ButtonText.TEST_CONNECTION)
        self.test_conn_btn.setStyleSheet(
            "LoadingButton { background: #fff; border: 1px solid #D4E5F3; border-radius: 6px; "
            "padding: 4px 14px; font-size: 12px; color: #284157; } "
            "LoadingButton:hover { background: #F6FAFD; border-color: #8CA3B6; }"
        )
        self.test_conn_btn.setFixedHeight(28)
        self.test_conn_btn.clicked.connect(self.test_connection)
        self.gui.test_conn_btn = self.test_conn_btn
        pr.addWidget(self.test_conn_btn)

        layout.addWidget(preflight_row)

        # -- Compact summary: 4 tiny metrics ------------------------------------
        summary_row = QFrame()
        sr = QHBoxLayout(summary_row)
        sr.setContentsMargins(0, 0, 0, 0)
        sr.setSpacing(8)
        self.summary_mode = _CompactMetric("sync_mode.svg", "同步模式", "--", "blue")
        self.summary_target = _CompactMetric("sync_target.svg", "目标范围", "--", "green")
        self.summary_progress = _CompactMetric("sync_progress.svg", "进度", "0%", "blue")
        self.summary_result = _CompactMetric("sync_result.svg", "最近结果", "--", "slate")
        for m in (self.summary_mode, self.summary_target, self.summary_progress, self.summary_result):
            m.setStyleSheet("_CompactMetric { background: #fff; border: 1px solid #E5F0F8; border-radius: 6px; }")
            sr.addWidget(m)
        layout.addWidget(summary_row)

        # -- Execution + log side by side ---------------------------------------
        body_row = QWidget()
        br = QHBoxLayout(body_row)
        br.setContentsMargins(0, 0, 0, 0)
        br.setSpacing(SpacingTokens.SM)

        # Left: execution status
        exec_card = Win11SectionCard("执行状态", "")
        self.run_state_badge = QLabel("空闲")
        self.run_state_badge.setStyleSheet("color: #8CA3B6; font-size: 12px;")
        exec_card.content_layout.addWidget(self.run_state_badge)
        exec_card.content_layout.setSpacing(4)

        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(12)
        self.exec_count_card = _CompactMetric("sync_record.svg", "已同步记录", "0", "blue")
        self.exec_time_card = _CompactMetric("sync_runtime.svg", "已用时间", "00:00", "green")
        self.exec_rate_card = _CompactMetric("sync_status.svg", "运行状态", "空闲", "blue")
        for m in (self.exec_count_card, self.exec_time_card, self.exec_rate_card):
            metrics_row.addWidget(m)
        exec_card.content_layout.addLayout(metrics_row)

        self._progress_card = SyncProgressCard()
        self.progress_bar = self._progress_card.progress_bar
        self.progress_status_lbl = self._progress_card.progress_status_lbl
        self._progress_card.setFixedHeight(40)
        exec_card.content_layout.addWidget(self._progress_card)
        br.addWidget(exec_card, 2)

        # Right: log
        log_card = Win11SectionCard("运行日志", "")
        log_actions = QHBoxLayout()
        log_actions.setSpacing(6)
        for text, handler in [("复制", self.copy_log), ("导出", self.export_log), ("清空", self.clear_log)]:
            btn = QPushButton(text)
            btn.setStyleSheet(
                "QPushButton { background: #fff; border: 1px solid #D4E5F3; border-radius: 4px; "
                "padding: 3px 10px; font-size: 11px; color: #284157; }"
                "QPushButton:hover { background: #F6FAFD; }"
            )
            btn.setFixedHeight(24)
            btn.clicked.connect(handler)
            log_actions.addWidget(btn)
        log_actions.addStretch(1)
        log_card.content_layout.addLayout(log_actions)
        self.log_panel = QTextEdit()
        self.log_panel.setReadOnly(True)
        self.log_panel.setStyleSheet(
            "QTextEdit { background-color: #14263A; color: #D7E3ED; border: none; border-radius: 6px; "
            "padding: 8px 10px; font-family: Consolas,monospace; font-size: 11px; }"
        )
        self.log_panel.setMinimumHeight(160)
        log_card.content_layout.addWidget(self.log_panel, 1)
        br.addWidget(log_card, 3)

        layout.addWidget(body_row, 1)

        scroll = self.create_scroll_container("sync_workspace_scroll")
        scroll.setWidget(root)
        self.set_content(scroll)

    # -- Helpers ----------------------------------------------------------------

    def _make_combo(self, combo: SearchableComboBox) -> SearchableComboBox:
        combo.setMinimumHeight(32)
        combo.btn.setStyleSheet(
            "QPushButton { background: #fff; border: 1px solid #D4E5F3; border-radius: 6px; "
            "padding: 4px 28px 4px 10px; font-size: 13px; color: #14263A; text-align: left; }"
            "QPushButton:hover { border-color: #8CA3B6; }"
            "QPushButton::down-arrow { image: none; }"
        )
        combo.currentIndexChanged.connect(self._on_manual_selection_changed)
        return combo

    def _combo_selected_data(self, combo: SearchableComboBox, *, default=None):
        current_data = getattr(combo, "_current_data", None)
        if current_data is not None:
            return current_data
        items = getattr(combo, "items_data", []) or []
        current_index = combo.currentIndex()
        if 0 <= current_index < len(items):
            return items[current_index][2]
        return default

    def _set_combo_selected_by_data(self, combo: SearchableComboBox, target_data) -> bool:
        for idx, (_text, _icon, data) in enumerate(getattr(combo, "items_data", []) or []):
            if data == target_data:
                combo.setCurrentIndex(idx)
                return True
        return False

    def _refresh_selection_summary(self) -> None:
        mode_text = self.sync_type_combo.currentText() or "增量（推荐）"
        form_text = self.form_selector.currentText() or FORM_ALL_TEXT
        self.summary_mode.set_data(mode_text)
        self.summary_target.set_data(form_text)
        vl = self._preflight_labels.get("preflight_scope")
        if vl:
            vl.setText(form_text)

    def _on_manual_selection_changed(self, *_args) -> None:
        if self._loading_defaults:
            return
        self._persist_manual_selection()
        self._refresh_selection_summary()

    def _persist_manual_selection(self) -> None:
        if self._loading_defaults:
            return
        try:
            scope, selected_form, mode = self._current_manual_selection_payload()
            config_manager.update_config("SYNC", SYNC_UI_SCOPE_KEY, scope)
            config_manager.update_config("SYNC", SYNC_UI_FORM_KEY, selected_form)
            config_manager.update_config("SYNC", SYNC_UI_MODE_KEY, mode)
        except Exception as exc:
            logger.warning("Failed to persist sync UI selection: %s", exc)

    def _current_manual_selection_payload(self) -> tuple[str, str, str]:
        form_data = self._combo_selected_data(self.form_selector, default=FORM_ALL_DATA)
        mode_data = self._combo_selected_data(self.sync_type_combo, default="incremental")
        if form_data == FORM_DEFAULT_DATA:
            return "default", "", str(mode_data or "incremental")
        if form_data == FORM_ALL_DATA or not form_data:
            return "all", "", str(mode_data or "incremental")
        return "single", str(form_data), str(mode_data or "incremental")

    # -- Data / Logic methods (unchanged from original) -------------------------

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
                UiFeedback.info(self, "未配置默认表单", "请先在“表单映射”页确认默认表单范围，再使用该快捷方式。")
                return
            forms = default_forms
        elif form_data != FORM_ALL_DATA:
            forms = [str(form_data)]
        sync_type = SyncType.COMPLETE if mode_data in {"full", "complete"} else SyncType.INCREMENTAL

        try:
            sync_service.save_sync_preferences(forms, sync_type)
        except Exception as exc:
            logger.warning("Failed to save sync preferences: %s", exc)

        self.summary_mode.set_data(sync_mode_text)
        self.summary_target.set_data(form_selection)
        self.summary_progress.set_data("0%")
        self.summary_result.set_data("--")

        self.start_sync_btn.set_loading(True, LoadingText.SYNC)
        self.cancel_sync_btn.setEnabled(True)
        self.progress_bar.setValue(0)
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
        UiFeedback.info(self, "取消说明", "当前同步任务暂不支持中途取消，请等待本次运行完成。")

    def on_sync_progress(self, msg, val) -> None:
        self.append_log(msg)
        if val >= 0:
            self.progress_bar.setValue(val)
            self.summary_progress.set_data(f"{val}%")
            self.progress_status_lbl.setText(f"{val}%")

    def on_sync_finished(self, result) -> None:
        self.start_sync_btn.set_loading(False)
        self.cancel_sync_btn.setEnabled(False)
        self.sync_timer.stop()
        QTimer.singleShot(3000, lambda: self.start_sync_btn.setText(ButtonText.START_SYNC))
        self.append_log("-" * 40, "INFO")

        status = result.get("status")
        details = result.get("details", {})
        total_inserted = 0
        total_updated = 0
        failed_forms = []
        success_forms = 0
        if isinstance(details, dict):
            for form_name, stats in details.items():
                if isinstance(stats, dict):
                    total_inserted += int(stats.get("inserted", 0) or 0)
                    total_updated += int(stats.get("updated", 0) or 0)
                    if stats.get("status") == "success":
                        success_forms += 1
                    else:
                        failed_forms.append(form_name)

        total_records_fallback = int(result.get("total_records", 0) or 0)
        self.synced_count = total_inserted + total_updated
        if self.synced_count <= 0 and total_records_fallback > 0:
            self.synced_count = total_records_fallback
        self.exec_count_card.set_data(str(self.synced_count))

        if total_inserted or total_updated:
            result_value = f"插入 {total_inserted} / 更新 {total_updated}"
        elif total_records_fallback > 0:
            result_value = f"共 {total_records_fallback} 条"
        else:
            result_value = "--"
        self.summary_result.set_data(result_value)
        self.summary_progress.set_data("100%")
        self.progress_bar.setValue(100)

        if status == "success":
            self.append_log("同步任务成功完成", "SUCCESS")
            self.hero_status.setText("成功")
            self.progress_status_lbl.setText("成功")
            self.exec_rate_card.set_data("成功")
            self.start_sync_btn.setText("同步成功")
        elif status == "partial":
            self.append_log("同步任务部分成功", "WARNING")
            if failed_forms:
                self.append_log(f"异常表单：{', '.join(failed_forms)}", "WARNING")
            self.progress_status_lbl.setText("部分成功")
            self.exec_rate_card.set_data("部分成功")
            self.start_sync_btn.setText("部分成功")
        else:
            self.append_log("同步任务失败", "ERROR")
            if failed_forms:
                self.append_log(f"失败表单：{', '.join(failed_forms)}", "ERROR")
            self.progress_status_lbl.setText("失败")
            self.exec_rate_card.set_data("失败")
            self.start_sync_btn.setText("同步失败")

        self.append_log("同步汇总：", "INFO")
        self.append_log(f"插入 {total_inserted} 条记录，更新 {total_updated} 条记录。", "INFO")
        if isinstance(details, dict):
            for form in sorted(details.keys()):
                stats = details[form]
                if isinstance(stats, dict):
                    self.append_log(f"{form}：插入 {stats.get('inserted', 0)}，更新 {stats.get('updated', 0)}。", "INFO")
        if hasattr(self.gui, "refresh_dashboard"):
            self.gui.refresh_dashboard()

    def test_connection(self) -> None:
        if self.test_worker and self.test_worker.isRunning():
            return
        self.test_conn_btn.set_loading(True, LoadingText.TEST)
        self.test_worker = TestWorker(service=sync_service)
        self.test_worker.finished.connect(self.on_test_finished)
        self.test_worker.start()

    def on_test_finished(self, api_ok, db_ok, msg) -> None:
        self.test_conn_btn.set_loading(False)
        self._last_test_message = msg or ""
        api_v = self._preflight_labels.get("preflight_api")
        db_v = self._preflight_labels.get("preflight_db")
        tm_v = self._preflight_labels.get("preflight_test_time")
        if api_v:
            api_v.setText("正常" if api_ok else "异常")
            api_v.setStyleSheet(f"color: {'#16A67D' if api_ok else '#C24D4D'}; font-weight: 500;")
        if db_v:
            db_v.setText("正常" if db_ok else "异常")
            db_v.setStyleSheet(f"color: {'#16A67D' if db_ok else '#C24D4D'}; font-weight: 500;")
        if tm_v:
            tm_v.setText(datetime.now().strftime("%H:%M"))
        if api_ok and db_ok:
            self.update_test_status("连接正常，可以开始同步。", False)
        else:
            self.update_test_status(f"连接测试失败。{msg}" if msg else "连接测试失败，请检查 API 与数据库配置。", True)

    def update_test_status(self, msg, is_error=False) -> None:
        pass  # Compact page shows status through preflight chips

    def reset_stats(self) -> None:
        self.synced_count = 0
        self.success_count = 0
        self.fail_count = 0
        self.start_time = datetime.now()
        self.exec_count_card.set_data("0")
        self.exec_time_card.set_data("00:00")
        self.exec_rate_card.set_data("运行中")
        self.progress_status_lbl.setText("启动中")
        self.sync_timer.start(1000)

    def _update_time_elapsed(self) -> None:
        if self.start_time:
            delta = datetime.now() - self.start_time
            seconds = int(delta.total_seconds())
            h = seconds // 3600
            m = (seconds % 3600) // 60
            s = seconds % 60
            self.exec_time_card.set_data(f"{h:02}:{m:02}:{s:02}")

    def clear_log(self) -> None:
        self.log_entries.clear()
        if hasattr(self, "log_panel"):
            self.log_panel.clear()

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
        except Exception as exc:
            UiFeedback.error(self, "导出失败", f"本次同步日志导出失败：\n{exc}")

    def append_log(self, msg, level="INFO") -> None:
        message = str(msg)
        upper_msg = message.upper()
        if level == "ERROR":
            self.fail_count += 1
        elif level == "SUCCESS":
            self.success_count += 1
        elif "FAILED" in upper_msg:
            self.fail_count += 1
        elif "SUCCESS" in upper_msg:
            self.success_count += 1
        time_str = datetime.now().strftime("%H:%M:%S")
        self.log_entries.append(f"[{time_str}] [{level}] {message}")
        if hasattr(self, "log_panel"):
            self.log_panel.append(f"[{time_str}] [{level}] {message}")
