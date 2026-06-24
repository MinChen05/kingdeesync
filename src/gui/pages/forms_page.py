"""Form mapping page with real config reading."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.config.config_manager import config_manager
from src.gui.components.common import SvgIconLabel
from src.gui.components.data_table import DataTable
from src.gui.components.page_shell import Win11PageScaffold
from src.gui.design_tokens import ColorTokens
from src.gui.feedback import UiFeedback

logger = logging.getLogger(__name__)


def _latest_config_mtime() -> str:
    candidates: list[Path] = []
    try:
        config_file = Path(str(getattr(config_manager, "config_file", ""))).resolve()
        config_dir = config_file.parent
        candidates.extend([
            config_file,
            config_dir / "tables.json",
            config_dir / "field_mappings.json",
            config_dir / "src" / "config" / "tables.json",
            config_dir / "src" / "config" / "field_mappings.json",
        ])
    except Exception:
        pass

    base_dir = Path(__file__).resolve().parents[3]
    candidates.extend([
        base_dir / "src" / "config" / "tables.json",
        base_dir / "src" / "config" / "field_mappings.json",
    ])

    mtimes = [path.stat().st_mtime for path in candidates if path.exists()]
    if not mtimes:
        return "--"
    return datetime.fromtimestamp(max(mtimes)).strftime("%Y-%m-%d")


class _FormListItem(QFrame):
    """Form list item with icon, name, table name, and status."""

    def __init__(self, name: str, table_name: str, status: str, selected: bool = False, parent=None):
        super().__init__(parent)
        self.form_name = name
        self.table_name = table_name
        self.status = status
        self.setProperty("ui", "fm-form-item")
        if selected:
            self.setProperty("selected", True)
        self.setFixedHeight(54)

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(10)

        icon_color = ColorTokens.ACCENT_600 if status == "已映射" else ColorTokens.WARNING if status == "部分映射" else ColorTokens.NEUTRAL_400
        icon_widget = SvgIconLabel("forms_fields.svg", size=28, icon_size=18, color=icon_color)
        icon_widget.setProperty("ui", "fm-form-icon")
        root.addWidget(icon_widget)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        name_lbl = QLabel(name)
        name_lbl.setProperty("ui", "fm-item-name")
        table_lbl = QLabel(table_name)
        table_lbl.setProperty("ui", "fm-item-table")
        text_col.addWidget(name_lbl)
        text_col.addWidget(table_lbl)
        root.addLayout(text_col, 1)

        status_lbl = QLabel(status)
        status_color = ColorTokens.SUCCESS_GREEN if status == "已映射" else ColorTokens.WARNING if status == "部分映射" else ColorTokens.NEUTRAL_400
        status_lbl.setProperty("ui", "fm-item-status")
        status_p = status_lbl.palette()
        status_p.setColor(QPalette.WindowText, QColor(status_color))
        status_lbl.setPalette(status_p)
        root.addWidget(status_lbl)


class _FilterComboFrame(QFrame):
    """Framed combo wrapper so the border is painted by QFrame, not QComboBox."""

    def __init__(self, combo: QComboBox, width: int, parent=None):
        super().__init__(parent)
        self.setProperty("ui", "fm-filter-combo-frame")
        self.setFixedSize(width, 44)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        combo.setParent(self)
        combo.setFixedSize(width - 2, 40)
        layout.addWidget(combo)
        bottom_line = QFrame(self)
        bottom_line.setProperty("ui", "fm-filter-combo-bottom-line")
        bottom_line.setFixedHeight(1)
        layout.addWidget(bottom_line)


class FormConfigPage(Win11PageScaffold):
    """Form mapping page with real config reading."""

    def __init__(self, parent_gui, parent=None):
        self.gui = parent_gui
        super().__init__(
            title="表单映射",
            eyebrow="",
            subtitle="查看表单、目标表与字段映射配置",
            parent=parent,
        )
        self.setProperty("page", "forms")
        self.set_hero_visible(False)
        self.hero_card.setVisible(False)
        self.primary_action_host.setVisible(False)
        self.summary_strip.setVisible(False)
        self._all_forms: list[dict[str, str]] = []
        self._field_mappings: dict[str, dict[str, object]] = {}
        self._visible_form_items: list[_FormListItem] = []
        self._selected_form = ""
        self._build_ui()
        self._load_real_data()

    def _build_ui(self) -> None:
        content_widget = QWidget()
        content_widget.setObjectName("forms_content")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        title_row = QWidget()
        title_layout = QHBoxLayout(title_row)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(12)

        self.page_title = QLabel("表单映射")
        self.page_title.setProperty("ui", "fm-page-title")
        title_layout.addWidget(self.page_title)
        title_layout.addStretch()

        self.btn_refresh_config = QPushButton("刷新配置")
        self.btn_refresh_config.setProperty("class", "primary")
        self.btn_refresh_config.setFixedSize(112, 36)
        self.btn_refresh_config.clicked.connect(self.refresh_data)
        title_layout.addWidget(self.btn_refresh_config)
        content_layout.addWidget(title_row)

        filter_row = QFrame()
        filter_row.setProperty("ui", "fm-filter-bar")
        filter_layout = QHBoxLayout(filter_row)
        filter_layout.setContentsMargins(18, 16, 18, 16)
        filter_layout.setSpacing(16)

        self.combo_form = self._create_filter_combo()
        self.combo_form.setProperty("ui", "fm-filter-input")
        self.combo_form.addItems(["请选择表单"])
        self.combo_form.currentTextChanged.connect(self.apply_filters)
        self._add_filter_group(filter_layout, "表单名称：", _FilterComboFrame(self.combo_form, 240))

        self.combo_status = self._create_filter_combo()
        self.combo_status.setProperty("ui", "fm-filter-input")
        self.combo_status.addItems(["全部状态", "已映射", "部分映射", "未映射"])
        self.combo_status.currentTextChanged.connect(self.apply_filters)
        self._add_filter_group(filter_layout, "映射状态：", _FilterComboFrame(self.combo_status, 200))

        self.search_box = QLineEdit()
        self.search_box.setProperty("ui", "fm-filter-search")
        self.search_box.setPlaceholderText("搜索表单或字段")
        self.search_box.setFixedHeight(40)
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setMinimumWidth(260)
        self.search_box.setMaximumWidth(16777215)
        self.search_box.textChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.search_box, 1)

        self.btn_reset_filter = QPushButton("重置")
        self.btn_reset_filter.setProperty("class", "secondary")
        self.btn_reset_filter.setProperty("ui", "fm-filter-reset")
        self.btn_reset_filter.setFixedSize(64, 40)
        self.btn_reset_filter.clicked.connect(self.reset_filters)
        filter_layout.addWidget(self.btn_reset_filter)

        self.btn_apply_filter = QPushButton("筛选")
        self.btn_apply_filter.setProperty("ui", "fm-filter-apply")
        self.btn_apply_filter.setFixedSize(64, 40)
        self.btn_apply_filter.clicked.connect(self.apply_filters)
        filter_layout.addWidget(self.btn_apply_filter)

        filter_row.setFixedHeight(76)
        content_layout.addWidget(filter_row)

        stats_row = QWidget()
        stats_layout = QHBoxLayout(stats_row)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(12)

        self.stat_values: dict[str, QLabel] = {}
        stat_defs = [
            ("forms", "已配置表单", "--", "真实表单数量", ColorTokens.ACCENT_600),
            ("fields", "字段映射", "--", "真实字段映射数量", ColorTokens.SUCCESS_GREEN),
            ("missing", "缺失字段", "--", "待处理字段数量", ColorTokens.WARNING),
            ("updated", "最近更新", "--", "配置文件更新时间", ColorTokens.INFO),
        ]
        for index, (key, title, value, subtitle, color) in enumerate(stat_defs):
            icon_file = (
                "forms_configured.svg",
                "forms_fields.svg",
                "forms_missing.svg",
                "forms_updated.svg",
            )[index]
            card, value_label = self._create_stat_card(title, value, subtitle, color, icon_file)
            self.stat_values[key] = value_label
            card.setFixedHeight(102)
            stats_layout.addWidget(card)
        content_layout.addWidget(stats_row)

        body_splitter = QSplitter(Qt.Horizontal)
        body_splitter.setObjectName("forms_body_splitter")
        body_splitter.setHandleWidth(1)

        left_widget = QFrame()
        left_widget.setProperty("ui", "fm-panel-card")
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(16, 14, 16, 14)
        left_layout.setSpacing(8)

        form_header = QHBoxLayout()
        form_header.setContentsMargins(0, 0, 0, 4)
        form_header.setSpacing(8)
        form_title = QLabel("表单列表")
        form_title.setProperty("ui", "fm-section-title")
        form_header.addWidget(form_title)
        form_header.addStretch()
        left_layout.addLayout(form_header)

        self.form_search = QLineEdit()
        self.form_search.setPlaceholderText("搜索左侧表单")
        self.form_search.setFixedHeight(32)
        self.form_search.setClearButtonEnabled(True)
        self.form_search.textChanged.connect(self.apply_filters)
        left_layout.addWidget(self.form_search)

        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setFrameShape(QFrame.NoFrame)
        form_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.form_list_content = QWidget()
        self.form_list_layout = QVBoxLayout(self.form_list_content)
        self.form_list_layout.setContentsMargins(0, 0, 0, 0)
        self.form_list_layout.setSpacing(6)
        self.form_empty_label = QLabel("暂无表单映射配置，请检查配置文件。")
        self.form_empty_label.setProperty("ui", "fm-empty-text")
        self.form_empty_label.setAlignment(Qt.AlignCenter)
        self.form_list_layout.addWidget(self.form_empty_label)
        self.form_list_layout.addStretch()
        form_scroll.setWidget(self.form_list_content)
        left_layout.addWidget(form_scroll, 1)

        right_widget = QFrame()
        right_widget.setProperty("ui", "fm-panel-card")
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(16, 14, 16, 14)
        right_layout.setSpacing(10)

        self.detail_title = QLabel("字段映射详情")
        self.detail_title.setProperty("ui", "fm-section-title")
        right_layout.addWidget(self.detail_title)

        self.field_table = DataTable(["金蝶字段", "字段名称", "目标字段", "数据类型", "转换规则", "是否必填", "状态"])
        self.field_table.table.verticalHeader().setDefaultSectionSize(42)
        self.field_table.table.horizontalHeader().setFixedHeight(40)
        self.field_table.set_empty_text("当前表单还没有字段映射配置")
        self.field_table.clear()
        right_layout.addWidget(self.field_table, 1)

        body_splitter.addWidget(left_widget)
        body_splitter.addWidget(right_widget)
        body_splitter.setStretchFactor(0, 0)
        body_splitter.setStretchFactor(1, 1)
        body_splitter.setSizes([300, 880])
        content_layout.addWidget(body_splitter, 1)

        validation_card = QFrame()
        validation_card.setProperty("ui", "fm-validation-summary")
        validation_card.setFixedHeight(48)
        validation_layout = QHBoxLayout(validation_card)
        validation_layout.setContentsMargins(16, 6, 16, 6)
        validation_layout.setSpacing(12)
        summary_icon = SvgIconLabel("forms_validation_missing.svg", size=24, icon_size=16, color=ColorTokens.WARNING)
        summary_icon.setProperty("ui", "fm-validation-icon")
        validation_layout.addWidget(summary_icon)
        summary_title = QLabel("映射校验摘要")
        summary_title.setProperty("ui", "fm-validation-title")
        validation_layout.addWidget(summary_title)
        self.validation_summary_text = QLabel("字段缺失 0 · 类型不匹配 0 · 可自动修复 0")
        self.validation_summary_text.setProperty("ui", "fm-validation-desc")
        validation_layout.addWidget(self.validation_summary_text, 1)
        self.btn_view_diagnostics = QPushButton("查看诊断")
        self.btn_view_diagnostics.setProperty("ui", "fm-validation-action")
        self.btn_view_diagnostics.setFixedSize(88, 32)
        self.btn_view_diagnostics.clicked.connect(self.open_diagnostics_page)
        validation_layout.addWidget(self.btn_view_diagnostics)
        content_layout.addWidget(validation_card)

        self.set_content(content_widget)

    def _create_filter_combo(self) -> QComboBox:
        combo = QComboBox()
        combo.setFixedHeight(44)
        return combo

    def _add_filter_group(self, layout: QHBoxLayout, title: str, widget: QWidget) -> None:
        group = QWidget()
        group_layout = QHBoxLayout(group)
        group_layout.setContentsMargins(0, 0, 0, 0)
        group_layout.setSpacing(8)
        label = QLabel(title)
        label.setProperty("ui", "fm-filter-label")
        group_layout.addWidget(label)
        group_layout.addWidget(widget)
        layout.addWidget(group)

    def _create_stat_card(self, title: str, value: str, subtitle: str, color: str, icon_file: str) -> tuple[QWidget, QLabel]:
        card = QFrame()
        card.setProperty("ui", "fm-stat-card")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)

        icon_widget = SvgIconLabel(icon_file, size=52, icon_size=28, color=color)
        icon_widget.setProperty("ui", "fm-stat-icon")
        layout.addWidget(icon_widget)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title_lbl = QLabel(title)
        title_lbl.setProperty("ui", "fm-stat-title")
        value_lbl = QLabel(value)
        value_lbl.setProperty("ui", "fm-stat-value")
        sub_lbl = QLabel(subtitle)
        sub_lbl.setProperty("ui", "fm-stat-sub")
        text_col.addWidget(title_lbl)
        text_col.addWidget(value_lbl)
        text_col.addWidget(sub_lbl)
        layout.addLayout(text_col, 1)

        return card, value_lbl

    def _load_real_data(self) -> None:
        mapping: dict[str, str] = {}
        sync_cfg: dict = {}
        field_mappings: dict[str, dict[str, object]] = {}
        try:
            mapping = config_manager.get_table_mapping() or {}
        except Exception as exc:
            logger.warning("Failed to load table mapping: %s", exc)

        try:
            sync_cfg = config_manager.get_sync_config() or {}
        except Exception as exc:
            logger.warning("Failed to load sync config: %s", exc)

        try:
            field_mappings = config_manager.get_field_mappings() or {}
        except Exception as exc:
            logger.warning("Failed to load field mappings: %s", exc)

        defaults = set(sync_cfg.get("default_forms", []))
        if not defaults:
            defaults = set(mapping.keys())

        self._field_mappings = field_mappings
        self._update_real_stats(mapping, defaults, field_mappings)
        self._all_forms = []
        for form_name in sorted(mapping.keys()):
            table_name = mapping.get(form_name, form_name)
            has_fields = bool(field_mappings.get(table_name) or field_mappings.get(form_name))
            status = "已映射" if form_name in defaults and has_fields else "部分映射" if has_fields else "未映射"
            if form_name in defaults and not field_mappings:
                status = "已映射"
            self._all_forms.append({"name": form_name, "table": table_name, "status": status})

        self._populate_form_filter()
        self.apply_filters()

    def _update_real_stats(
        self,
        mapping: dict[str, str],
        defaults: set[str],
        field_mappings: dict[str, dict[str, object]],
    ) -> None:
        field_total = 0
        missing = 0
        type_mismatch = 0
        for fields in field_mappings.values():
            if not isinstance(fields, dict):
                continue
            field_total += len(fields)
            for field_info in fields.values():
                if not isinstance(field_info, dict):
                    continue
                sources = field_info.get("sources", [])
                has_source = bool(sources)
                field_type = str(field_info.get("type", "")).lower()
                if not has_source or field_info.get("default", "") == "":
                    missing += 1
                if field_type in {"unknown", ""}:
                    type_mismatch += 1

        enabled_count = len(defaults & set(mapping.keys())) if defaults else len(mapping)
        form_count = len(mapping)
        configured_rate = round(enabled_count / form_count * 100) if form_count else 0

        self.stat_values["forms"].setText(str(form_count))
        self.stat_values["fields"].setText(f"{field_total:,}")
        self.stat_values["missing"].setText(str(missing))
        self.stat_values["updated"].setText(_latest_config_mtime())

        form_card_sub = self.stat_values["forms"].parent().findChildren(QLabel)
        for label in form_card_sub:
            if label.property("ui") == "fm-stat-sub":
                label.setText(f"启用表单 {configured_rate}%")
                break

        self.validation_summary_text.setText(
            f"字段缺失 {missing} · 类型不匹配 {type_mismatch} · 可自动修复 0"
        )

    def _load_form_list(self) -> None:
        self.apply_filters()

    def _load_field_mappings(self) -> None:
        self.select_form(self._selected_form)

    def _populate_form_filter(self) -> None:
        current = self.combo_form.currentText()
        self.combo_form.blockSignals(True)
        self.combo_form.clear()
        self.combo_form.addItem("请选择表单")
        for form in self._all_forms:
            self.combo_form.addItem(form["name"])
        index = self.combo_form.findText(current)
        self.combo_form.setCurrentIndex(index if index >= 0 else 0)
        self.combo_form.blockSignals(False)

    def apply_filters(self, *_args) -> None:
        form_filter = self.combo_form.currentText().strip()
        if form_filter == "请选择表单":
            form_filter = ""
        status_filter = self.combo_status.currentText().strip()
        if status_filter == "全部状态":
            status_filter = ""
        keyword = self.search_box.text().strip().lower()
        list_keyword = self.form_search.text().strip().lower()

        visible = []
        for form in self._all_forms:
            haystack = f"{form['name']} {form['table']}".lower()
            if form_filter and form["name"] != form_filter:
                continue
            if status_filter and form["status"] != status_filter:
                continue
            if keyword and keyword not in haystack:
                continue
            if list_keyword and list_keyword not in haystack:
                continue
            visible.append(form)

        self._rebuild_form_items(visible)
        if visible:
            preferred = self._selected_form if any(form["name"] == self._selected_form for form in visible) else visible[0]["name"]
            self.select_form(preferred)
        else:
            self._selected_form = ""
            self.detail_title.setText("字段映射详情")
            self.field_table.clear()

    def reset_filters(self) -> None:
        self.combo_form.blockSignals(True)
        self.combo_status.blockSignals(True)
        self.search_box.blockSignals(True)
        try:
            self.combo_form.setCurrentIndex(0)
            self.combo_status.setCurrentIndex(0)
            self.search_box.clear()
        finally:
            self.combo_form.blockSignals(False)
            self.combo_status.blockSignals(False)
            self.search_box.blockSignals(False)
        self.apply_filters()

    def _rebuild_form_items(self, forms: list[dict[str, str]]) -> None:
        while self.form_list_layout.count() > 1:
            item = self.form_list_layout.takeAt(0)
            widget = item.widget() if item else None
            if widget is self.form_empty_label:
                continue
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        self._visible_form_items = []
        self.form_list_layout.insertWidget(0, self.form_empty_label)
        self.form_empty_label.setVisible(not forms)
        for form in forms:
            item = _FormListItem(
                form["name"],
                form["table"],
                form["status"],
                selected=(form["name"] == self._selected_form),
            )
            item.mousePressEvent = lambda _event, name=form["name"]: self.select_form(name)
            self.form_list_layout.insertWidget(self.form_list_layout.count() - 1, item)
            self._visible_form_items.append(item)

    def select_form(self, form_name: str) -> None:
        if not form_name:
            return
        form = next((item for item in self._all_forms if item["name"] == form_name), None)
        if not form:
            return
        self._selected_form = form_name
        for item in self._visible_form_items:
            item.setProperty("selected", item.form_name == form_name)
            item.style().unpolish(item)
            item.style().polish(item)
        self.detail_title.setText(f"字段映射详情（{form_name}）")
        self.field_table.set_data(self._rows_for_form(form_name, form["table"]))

    def _rows_for_form(self, form_name: str, table_name: str) -> list[list[str]]:
        fields = self._field_mappings.get(table_name) or self._field_mappings.get(form_name) or {}
        if not fields:
            return []
        rows = []
        for field_name, field_info in fields.items():
            sources = field_info.get("sources", []) if isinstance(field_info, dict) else []
            source_str = sources[0] if sources else field_name
            field_type = field_info.get("type", "unknown") if isinstance(field_info, dict) else "unknown"
            default_val = field_info.get("default", "") if isinstance(field_info, dict) else ""
            has_source = bool(sources)
            has_default = default_val != ""
            status = "已映射" if has_source and has_default else "缺失目标字段"
            rows.append([
                str(source_str),
                str(field_name),
                str(field_name),
                str(field_type).upper(),
                "直接映射" if has_source else "未配置",
                "是" if has_default else "否",
                status,
            ])
        return rows

    def refresh_data(self) -> None:
        self._load_real_data()
        UiFeedback.info(self, "刷新完成", "已重新加载最新表单映射配置。")

    def open_diagnostics_page(self) -> None:
        switch_to_page = getattr(self.gui, "switch_to_page", None)
        if callable(switch_to_page):
            switch_to_page("diagnostics")
