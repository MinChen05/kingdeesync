"""Form configuration page built on the shared Windows 11 page scaffold."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.config.config_manager import config_manager
from src.gui.components.page_shell import Win11PageScaffold, Win11SectionCard, Win11SummaryCard
from src.gui.feedback import UiFeedback
from src.gui.ui_text import ButtonText

logger = logging.getLogger(__name__)


class FormSummaryCard(Win11SummaryCard):
    """Compact summary card for the default-form workspace."""

    def __init__(self, title: str, value: str = "--", subtitle: str = "", parent=None):
        super().__init__(title=title, value=value, subtitle=subtitle, parent=parent)
        self.subtitle_label.setProperty("ui", "win11-helper-text")

    def set_data(self, value: str, subtitle: str | None = None) -> None:
        self.set_value(value)
        if subtitle is not None:
            self.set_subtitle(subtitle)


class FormConfigPage(Win11PageScaffold):
    """Manage default sync form selection."""

    def __init__(self, parent_gui, parent=None):
        self.gui = parent_gui
        self.form_widgets: list[tuple[str, QFrame, QCheckBox]] = []
        self.original_selection: set[str] = set()
        super().__init__(
            title="默认表单集",
            eyebrow="表单",
            subtitle="在统一的 Windows 11 页面流程中维护默认同步表单范围。",
            parent=parent,
        )
        self.setProperty("page", "forms")
        self.setup_ui()
        self.load_forms()

    def setup_ui(self) -> None:
        self._init_action_controls()
        self._build_hero()
        self._build_summary_strip()
        self.add_primary_action(self.search_box)
        self.add_primary_action(self.btn_select_all)
        self.add_primary_action(self.btn_reset)
        self.add_primary_action(self.btn_save)
        self.set_content(self._create_scroll_content())
        self._apply_action_sizing()

    def _init_action_controls(self) -> None:
        self.search_box = QLineEdit()
        self.search_box.setProperty("td", "win11-input")
        self.search_box.setPlaceholderText("鎸夎〃鍗曞悕绉扮瓫閫?")
        self.search_box.textChanged.connect(self.filter_cards)

        self.top_status_lbl = QLabel("姝ｅ湪鍔犺浇琛ㄥ崟...")
        self.top_status_lbl.setProperty("ui", "win11-meta-text")
        self.top_status_lbl.setProperty("tone", "neutral")
        self.top_status_lbl.setWordWrap(True)

        self.btn_select_all = QPushButton("鍏ㄩ€?")
        self.btn_select_all.setProperty("class", "secondary")
        self.btn_select_all.setFixedHeight(36)
        self.btn_select_all.clicked.connect(self.toggle_all)

    def _build_hero(self) -> None:
        meta_widget = QWidget()
        meta_layout = QVBoxLayout(meta_widget)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(6)

        self.hero_badge = QLabel("默认同步集")
        self.hero_badge.setProperty("ui", "win11-status-chip")
        self.hero_badge.setProperty("tone", "info")

        self.hero_status = QLabel("选择在使用“默认范围”执行同步时需要预选的表单。")
        self.hero_status.setProperty("ui", "win11-meta-text")
        self.hero_status.setWordWrap(True)

        meta_layout.addWidget(self.hero_badge, 0, Qt.AlignmentFlag.AlignLeft)
        meta_layout.addWidget(self.hero_status)


        self.btn_reset = QPushButton("重置")
        self.btn_reset.setProperty("class", "secondary")
        self.btn_reset.setFixedHeight(36)
        self.btn_reset.clicked.connect(self.reset_selection)

        self.btn_save = QPushButton(ButtonText.SAVE_CONFIG)
        self.btn_save.setProperty("class", "primary")
        self.btn_save.setFixedHeight(36)
        self.btn_save.clicked.connect(self.save_config)

        self.add_hero_widget(meta_widget)

    def _build_summary_strip(self) -> None:
        self.summary_selected = FormSummaryCard("已选表单", "0", "这些表单将作为默认同步范围保存。")
        self.summary_visible = FormSummaryCard("可见结果", "0", "当前筛选后可见的表单数量。")
        self.summary_scope = FormSummaryCard("选择范围", "--", "可进行全选、清空可见项或恢复最近保存结果。")

        for card in (self.summary_selected, self.summary_visible, self.summary_scope):
            self.add_summary_card(card)

    def _create_scroll_content(self) -> QScrollArea:
        scroll = self.create_scroll_container("forms_page_scroll")

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        layout.addWidget(self._create_filter_card())
        layout.addWidget(self._create_form_list_card(), 1)
        layout.addWidget(self._create_footer_card())

        scroll.setWidget(page)
        return scroll

    def _create_filter_card(self) -> Win11SectionCard:
        card = Win11SectionCard(
            "筛选与批量操作",
            "先搜索，再对当前结果中可见的表单执行批量选择。",
        )

        card.content_layout.addWidget(self.top_status_lbl)
        return card

        row = QHBoxLayout()
        row.setSpacing(12)

        self.search_box = QLineEdit()
        self.search_box.setProperty("td", "win11-input")
        self.search_box.setPlaceholderText("按表单名称筛选")
        self.search_box.setFixedWidth(280)
        self.search_box.textChanged.connect(self.filter_cards)

        self.top_status_lbl = QLabel("正在加载表单...")
        self.top_status_lbl.setProperty("ui", "win11-meta-text")
        self.top_status_lbl.setProperty("tone", "neutral")
        self.top_status_lbl.setWordWrap(True)

        self.btn_select_all = QPushButton("全选")
        self.btn_select_all.setProperty("class", "secondary")
        self.btn_select_all.setFixedHeight(36)
        self.btn_select_all.setFixedWidth(112)
        self.btn_select_all.clicked.connect(self.toggle_all)

        row.addWidget(self.search_box)
        row.addWidget(self.top_status_lbl, 1)
        row.addWidget(self.btn_select_all)
        card.content_layout.addLayout(row)
        return card

    def _create_form_list_card(self) -> Win11SectionCard:
        card = Win11SectionCard(
            "默认表单列表",
            "勾选后将保存为默认同步范围，可在“同步”页直接复用。",
        )

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        card.content_layout.addWidget(self.scroll, 1)

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 4, 0, 4)
        self.scroll_layout.setSpacing(0)
        self.scroll_layout.addStretch(1)
        self.scroll.setWidget(self.scroll_content)
        return card

    def _create_footer_card(self) -> Win11SectionCard:
        card = Win11SectionCard(
            "选择摘要",
            "在此整理默认集合后，可返回“同步”页面直接执行任务。",
        )

        self.status_lbl = QLabel("已选择 0 / 0")
        self.status_lbl.setProperty("ui", "win11-meta-text")
        card.content_layout.addWidget(self.status_lbl)
        return card

    def _apply_action_sizing(self) -> None:
        compact = self.width() <= 1366
        self.search_box.setMinimumWidth(180 if compact else 260)
        self.search_box.setMaximumWidth(260 if compact else 320)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._apply_action_sizing()
        super().resizeEvent(event)

    def _build_form_row(self, form_name: str, checked: bool) -> tuple[QFrame, QCheckBox]:
        row = QFrame()
        row.setProperty("ui", "win11-setting-row")

        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 14, 0, 14)
        layout.setSpacing(12)

        cb = QCheckBox()
        cb.setChecked(checked)
        cb.stateChanged.connect(self._on_selection_changed)

        text_wrap = QVBoxLayout()
        text_wrap.setSpacing(3)

        name_lbl = QLabel(form_name)
        name_lbl.setProperty("ui", "win11-row-title")

        note_lbl = QLabel("将纳入已保存的默认同步范围。")
        note_lbl.setProperty("ui", "win11-row-note")

        text_wrap.addWidget(name_lbl)
        text_wrap.addWidget(note_lbl)

        layout.addWidget(cb, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(text_wrap, 1)

        self._sync_form_row_state(row, cb)
        return row, cb

    def load_forms(self) -> None:
        self._clear_form_rows()

        form_names = sorted(config_manager.get_table_mapping().keys())
        sync_cfg = config_manager.get_sync_config()
        defaults = set(sync_cfg.get("default_forms", []))

        if not defaults:
            defaults = set(form_names)

        self.original_selection = set(defaults)

        for index, form_name in enumerate(form_names):
            row, cb = self._build_form_row(form_name, form_name in defaults)
            self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, row)
            self.form_widgets.append((form_name, row, cb))
        self._refresh_row_edge_states()

        self.filter_cards(self.search_box.text())

    def load_config(self) -> None:
        """Called by main shell when switching page."""
        self.load_forms()

    def _clear_form_rows(self) -> None:
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item is None:
                continue

            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
                continue

            child_layout = item.layout()
            if child_layout is not None:
                while child_layout.count():
                    child_layout.takeAt(0)
                child_layout.setParent(None)
                child_layout.deleteLater()
        self.form_widgets.clear()
        self.scroll_layout.addStretch(1)

    def _refresh_row_edge_states(self) -> None:
        last_index = len(self.form_widgets) - 1
        for index, (_name, row, _cb) in enumerate(self.form_widgets):
            is_last = index == last_index
            row.setProperty("last", is_last)
            style = row.style()
            if style is not None:
                style.unpolish(row)
                style.polish(row)

    def _selected_forms(self) -> list[str]:
        return [name for name, _, cb in self.form_widgets if cb.isChecked()]

    def _visible_form_widgets(self) -> list[tuple[str, QFrame, QCheckBox]]:
        return [(name, row, cb) for name, row, cb in self.form_widgets if row.isVisible()]

    def _set_status_tone(self, tone: str) -> None:
        if self.top_status_lbl.property("tone") == tone:
            return
        self.top_status_lbl.setProperty("tone", tone)
        style = self.top_status_lbl.style()
        if style is not None:
            style.unpolish(self.top_status_lbl)
            style.polish(self.top_status_lbl)

    def _sync_form_row_state(self, row: QFrame, checkbox: QCheckBox) -> None:
        row.setProperty("selected", checkbox.isChecked())
        style = row.style()
        if style is not None:
            style.unpolish(row)
            style.polish(row)

    def _on_selection_changed(self, *_args) -> None:
        for _, row, cb in self.form_widgets:
            self._sync_form_row_state(row, cb)

        selected = self._selected_forms()
        total = len(self.form_widgets)
        visible_total = len(self._visible_form_widgets())

        self.status_lbl.setText(f"已选择 {len(selected)} / {total}")
        self.hero_badge.setText(f"默认集合：{len(selected)} 个表单")
        self.summary_selected.set_data(str(len(selected)), "这些表单将作为默认同步集合保存。")
        self.summary_visible.set_data(str(visible_total), "筛选后当前可见的表单数量。")

        if total == 0:
            self.summary_scope.set_data("--", "正在等待表单加载。")
            self.top_status_lbl.setText("当前没有可配置的表单。")
            self._set_status_tone("neutral")
        elif len(selected) == total:
            self.summary_scope.set_data("全部表单", "当前默认集合已包含所有表单。")
            self.top_status_lbl.setText("已选中全部表单。")
            self._set_status_tone("success")
        elif len(selected) == 0:
            self.summary_scope.set_data("空集合", "当前默认集合中未选择任何表单。")
            self.top_status_lbl.setText("默认集合未选择任何表单。")
            self._set_status_tone("danger")
        else:
            self.summary_scope.set_data(f"{len(selected)} 个表单", "如有需要，可对可见表单执行批量调整。")
            self.top_status_lbl.setText("当前视图中的默认集合已更新。")
            self._set_status_tone("info")

        visible_rows = self._visible_form_widgets()
        if visible_rows and all(cb.isChecked() for _, _, cb in visible_rows):
            self.btn_select_all.setText("清空可见")
        else:
            self.btn_select_all.setText("全选")

    def filter_cards(self, keyword: str) -> None:
        keyword = (keyword or "").strip().lower()
        for name, row, _ in self.form_widgets:
            row.setVisible(keyword in name.lower() if keyword else True)
        self._on_selection_changed()

    def toggle_all(self) -> None:
        visible_rows = self._visible_form_widgets()
        if not visible_rows:
            return

        should_check = not all(cb.isChecked() for _, _, cb in visible_rows)
        for _, row, cb in visible_rows:
            cb.blockSignals(True)
            cb.setChecked(should_check)
            cb.blockSignals(False)
            self._sync_form_row_state(row, cb)
        self._on_selection_changed()

    def reset_selection(self) -> None:
        for name, row, cb in self.form_widgets:
            cb.blockSignals(True)
            cb.setChecked(name in self.original_selection)
            cb.blockSignals(False)
            self._sync_form_row_state(row, cb)
        self._on_selection_changed()
        UiFeedback.info(self, "已恢复", "已恢复为最近一次保存的默认表单集合。")

    def save_config(self) -> None:
        try:
            selected = self._selected_forms()
            config_manager.update_config("SYNC", "default_forms", ",".join(selected))
            self.original_selection = set(selected)
            self._on_selection_changed()
            UiFeedback.success(self, "保存成功", "默认表单配置已成功保存。")
        except Exception as exc:
            logger.error("Save form config failed: %s", exc)
            UiFeedback.error(self, "保存失败", f"无法保存默认表单配置：\n{exc}")
