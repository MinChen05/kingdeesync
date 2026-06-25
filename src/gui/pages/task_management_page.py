"""Task management page aligned with the Windows 11 target design."""

from __future__ import annotations

import inspect
import math
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPalette, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.gui.components.common import SvgIconLabel
from src.gui.components.data_table import DataTable
from src.gui.components.page_shell import Win11PageScaffold
from src.gui.design_tokens import ColorTokens, SizeTokens, SpacingTokens
from src.gui.feedback import UiFeedback
from src.services.task_service import task_service as default_task_service


def confirm_task_action(parent: QWidget | None, title: str, message: str) -> bool:
    return UiFeedback.confirm(parent, title, message) == QMessageBox.Yes


def _set_label_color(label: QLabel, color: str) -> None:
    palette = label.palette()
    palette.setColor(QPalette.ColorRole.WindowText, QColor(color))
    label.setPalette(palette)


def _set_font(label: QLabel, point_size: int, bold: bool = False) -> None:
    font = label.font()
    font.setPointSize(point_size)
    font.setBold(bold)
    label.setFont(font)


def _format_count(value: Any) -> str:
    if value in (None, ""):
        return "--"
    try:
        return f"{int(float(str(value).replace(',', ''))):,}"
    except (TypeError, ValueError):
        return str(value)


def _format_seconds(value: Any) -> str:
    if value in (None, ""):
        return "--"
    try:
        seconds = float(str(value).replace("秒", "").strip())
    except (TypeError, ValueError):
        return str(value)
    return f"{seconds:g} 秒"


def _first_value(record: Mapping[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return default


def _refresh_style(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _status_display(status: Any) -> tuple[str, str]:
    normalized = str(status or "").strip().lower()
    if normalized in {"running", "运行中"}:
        return "运行中", "info"
    if normalized in {"enabled", "active", "success", "ok", "启用中"}:
        return "启用中", "success"
    if normalized in {"paused", "disabled", "stopped", "pause", "已暂停"}:
        return "已暂停", "warning"
    if normalized in {"failed", "error", "failure", "danger", "失败"}:
        return "失败", "danger"
    if normalized in {"pending", "queued", "waiting", "待执行"}:
        return "待执行", "info"
    return str(status or "--"), "info"


def _result_status_text(status: Any) -> str:
    normalized = str(status or "").strip().lower()
    if normalized in {"success", "ok", "succeeded", "成功"}:
        return "成功"
    if normalized in {"failed", "error", "failure", "danger", "失败"}:
        return "失败"
    return _status_display(status)[0]


class TaskMetricIcon(QLabel):
    """Asset-backed icon for task metric cards."""

    _ICON_FILES = {
        "play": "icons/schedule_running.svg",
        "pause": "icons/schedule_status.svg",
        "chart": "icons/data_source_database.svg",
        "warning": "icons/metric_pending_warning.svg",
    }
    _ASSETS_DIR = Path(__file__).resolve().parents[3] / "assets"

    def __init__(self, icon_type: str, tone: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.icon_type = icon_type
        self.tone = tone
        self.setFixedSize(52, 52)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_file = self._ICON_FILES[icon_type]
        self.setProperty("icon-source", icon_file)
        pixmap = QIcon(str(self._ASSETS_DIR / icon_file)).pixmap(QSize(52, 52))
        if pixmap.isNull():
            pixmap = QPixmap(52, 52)
            pixmap.fill(Qt.GlobalColor.transparent)
        self.setPixmap(pixmap)


class TaskMetricCard(QFrame):
    """Task summary card with icon, value, and trend text."""

    def __init__(self, title: str, icon_type: str, tone: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("ui", "task-metric-card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(112)

        root = QHBoxLayout(self)
        root.setContentsMargins(SpacingTokens.MD, SpacingTokens.MD, SpacingTokens.MD, SpacingTokens.MD)
        root.setSpacing(SpacingTokens.SM)

        self.icon = TaskMetricIcon(icon_type, tone, self)
        root.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignVCenter)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        text_col.setSpacing(SpacingTokens.XS)

        self.title_label = QLabel(title)
        self.title_label.setProperty("ui", "task-metric-title")
        _set_font(self.title_label, 12, False)

        self.value_label = QLabel("--")
        self.value_label.setProperty("ui", "task-metric-value")
        _set_font(self.value_label, 22, True)

        self.subtitle_label = QLabel("--")
        self.subtitle_label.setProperty("ui", "task-metric-subtitle")
        _set_font(self.subtitle_label, 11, False)

        text_col.addWidget(self.title_label)
        text_col.addWidget(self.value_label)
        text_col.addWidget(self.subtitle_label)
        root.addLayout(text_col, 1)

    def set_data(self, value: Any, subtitle: str) -> None:
        self.value_label.setText(_format_count(value))
        self.subtitle_label.setText(subtitle or "--")


class TaskStatusMark(QWidget):
    """Painter mark used by task status tags."""

    def __init__(self, tone: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tone = tone
        self.setFixedSize(12, 12)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        color_map = {
            "success": ColorTokens.SUCCESS_GREEN,
            "warning": ColorTokens.WARNING,
            "danger": ColorTokens.DANGER,
            "info": ColorTokens.ACCENT_600,
        }
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color_map.get(self.tone, ColorTokens.ACCENT_600)))
        painter.drawEllipse(self.rect().adjusted(2, 2, -2, -2))
        painter.end()


class TaskStatusTag(QWidget):
    """Status widget for the task table."""

    def __init__(self, text: str, tone: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("ui", "task-status-tag")
        self.setProperty("tone", tone)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        layout.setSpacing(SpacingTokens.XS)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(TaskStatusMark(tone, self))

        self.label = QLabel(text)
        _set_font(self.label, 12, True)
        color_map = {
            "success": ColorTokens.SUCCESS_GREEN,
            "warning": ColorTokens.WARNING,
            "danger": ColorTokens.DANGER,
            "info": ColorTokens.ACCENT_600,
        }
        _set_label_color(self.label, color_map.get(tone, ColorTokens.ACCENT_600))
        layout.addWidget(self.label)


class TaskActionButton(QPushButton):
    """Small painter-only action button used in the task table."""

    _ICON_FILES = {
        "run": "icons/schedule_running.svg",
        "pause": "icons/schedule_status.svg",
        "edit": "icons/settings.svg",
        "more": "icons/more_horizontal.svg",
    }
    _ASSETS_DIR = Path(__file__).resolve().parents[3] / "assets"

    def __init__(self, action_type: str, tooltip: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.action_type = action_type
        self.action_label = tooltip
        self.setProperty("ui", "task-action-icon-btn")
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(18, 18)
        self.setIconSize(QSize(16, 16))
        icon_file = self._ICON_FILES.get(action_type)
        if icon_file:
            self.setProperty("icon-source", icon_file)
            self.setIcon(QIcon(str(self._ASSETS_DIR / icon_file)))

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().paintEvent(event)
        if self.action_type in self._ICON_FILES:
            return
        color = QColor(ColorTokens.INTERACTIVE_SURFACE)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(color, 1.7)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        rect = self.rect()
        cx = rect.center().x()
        cy = rect.center().y()
        if self.action_type == "run":
            path = QPainterPath()
            path.moveTo(cx - 4, cy - 6)
            path.lineTo(cx + 5, cy)
            path.lineTo(cx - 4, cy + 6)
            path.closeSubpath()
            painter.setBrush(color)
            painter.drawPath(path)
        elif self.action_type == "pause":
            painter.setBrush(color)
            painter.drawRoundedRect(cx - 5, cy - 6, 3, 12, 1, 1)
            painter.drawRoundedRect(cx + 2, cy - 6, 3, 12, 1, 1)
        elif self.action_type == "edit":
            painter.drawLine(cx - 6, cy + 5, cx + 5, cy - 6)
            painter.drawLine(cx + 2, cy - 8, cx + 7, cy - 3)
            painter.drawLine(cx - 7, cy + 7, cx - 2, cy + 6)
        else:
            painter.setBrush(color)
            for offset in (-5, 0, 5):
                painter.drawEllipse(cx + offset - 1, cy - 1, 2, 2)
        painter.end()


class TaskActionCell(QWidget):
    """Compact icon action group for each task row."""

    def __init__(self, task_name: str, on_action, parent: QWidget | None = None, *, is_running: bool = False) -> None:
        super().__init__(parent)
        self.task_name = task_name
        self._on_action = on_action
        self.setProperty("ui", "task-action-cell")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        layout.setSpacing(SpacingTokens.XXS)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_run = TaskActionButton("run", "立即运行", self)
        self.btn_pause = TaskActionButton("pause", "中止运行" if is_running else "暂停任务", self)
        self.btn_edit = TaskActionButton("edit", "编辑任务", self)
        self.btn_more = TaskActionButton("more", "更多操作", self)
        if is_running:
            self.btn_run.setEnabled(False)
        for button in (self.btn_run, self.btn_pause, self.btn_edit, self.btn_more):
            button.clicked.connect(lambda _checked=False, btn=button: self._emit_action(btn.action_label))
            layout.addWidget(button)

    def _emit_action(self, action_label: str) -> None:
        if callable(self._on_action):
            self._on_action(action_label, self.task_name, self)


class TaskDetailPanel(QFrame):
    """Right-side task details and operations panel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("ui", "task-detail-panel")
        self.setFixedWidth(304)

        root = QVBoxLayout(self)
        root.setContentsMargins(SpacingTokens.MD, SpacingTokens.MD, SpacingTokens.MD, SpacingTokens.MD)
        root.setSpacing(SpacingTokens.SM)

        header = QHBoxLayout()
        header.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        header.setSpacing(SpacingTokens.SM)
        header_title = QLabel("任务详情")
        header_title.setProperty("ui", "task-detail-heading")
        _set_font(header_title, 14, True)
        header.addWidget(header_title)
        header.addStretch(1)
        root.addLayout(header)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        title_row.setSpacing(SpacingTokens.SM)
        self.title_label = QLabel("--")
        self.title_label.setProperty("ui", "task-detail-title")
        _set_font(self.title_label, 15, True)
        title_row.addWidget(self.title_label, 1)

        self.status_label = QLabel("--")
        self.status_label.setProperty("ui", "task-detail-status")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFixedHeight(24)
        title_row.addWidget(self.status_label)
        root.addLayout(title_row)

        self.basic_info_value = self._add_section(root, "基本信息")
        self.sync_config_value = self._add_section(root, "同步配置")
        self.schedule_value = self._add_section(root, "调度与重试")
        self.error_value = self._add_error_section(root)
        root.addStretch(1)

    def _add_section(self, root: QVBoxLayout, title: str) -> QLabel:
        section = QFrame(self)
        section.setProperty("ui", "task-detail-section")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(SpacingTokens.NONE, SpacingTokens.XXS, SpacingTokens.NONE, SpacingTokens.XXS)
        layout.setSpacing(SpacingTokens.XXS)

        title_label = QLabel(title)
        title_label.setProperty("ui", "task-detail-section-title")
        _set_font(title_label, 12, True)
        layout.addWidget(title_label)

        value_label = QLabel("--")
        value_label.setProperty("ui", "task-detail-text")
        value_label.setWordWrap(True)
        value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(value_label)
        root.addWidget(section)
        return value_label

    def _add_error_section(self, root: QVBoxLayout) -> QLabel:
        section = QFrame(self)
        section.setProperty("ui", "task-error-card")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(SpacingTokens.SM, SpacingTokens.XS, SpacingTokens.SM, SpacingTokens.XS)
        layout.setSpacing(SpacingTokens.XXS)

        title_label = QLabel("最近结果")
        title_label.setProperty("ui", "task-detail-section-title")
        _set_font(title_label, 12, True)
        layout.addWidget(title_label)

        value_label = QLabel("--")
        value_label.setProperty("ui", "task-detail-error-text")
        value_label.setWordWrap(True)
        value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(value_label)
        root.addWidget(section)
        return value_label

    def set_task(
        self,
        task: Mapping[str, Any] | None,
    ) -> None:
        if not task:
            self.title_label.setText("未选择任务")
            self.status_label.setText("--")
            self.basic_info_value.setText("--")
            self.sync_config_value.setText("--")
            self.schedule_value.setText("--")
            self.error_value.setText("--")
            return

        title = str(_first_value(task, "task_name", "name", "title", default="--"))
        status_text, tone = _status_display(_first_value(task, "status", "state", default=""))
        self.title_label.setText(title)
        self.status_label.setText(status_text)
        self.status_label.setProperty("tone", tone)
        _refresh_style(self.status_label)

        self.basic_info_value.setText(
            "\n".join(
                [
                    f"任务ID: {_first_value(task, 'task_id', 'id', default='--')}",
                    f"创建时间: {_first_value(task, 'created_at', 'create_time', default='--')}",
                    f"创建人: {_first_value(task, 'creator', 'created_by', default='--')}",
                    f"更新时间: {_first_value(task, 'updated_at', 'update_time', default='--')}",
                ]
            )
        )
        self.sync_config_value.setText(
            "\n".join(
                [
                    f"同步范围: {_first_value(task, 'scope', 'sync_scope', default='--')}",
                    f"增量字段: {_first_value(task, 'increment_field', 'incremental_field', default='--')}",
                    f"目标表: {_first_value(task, 'target_table', 'form_name', default='--')}",
                ]
            )
        )
        schedule_lines = [
            f"执行方式: {_first_value(task, 'sync_mode', 'mode', default='--')}",
            f"调度策略: {_first_value(task, 'schedule', 'schedule_policy', default='--')}",
            f"重试策略: {_first_value(task, 'retry_policy', default='失败后重试 3 次，间隔 5 分钟')}",
        ]
        progress_stage = _first_value(task, "progress_stage", default="")
        progress_percent = _first_value(task, "progress_percent", default="")
        progress_updated_at = _first_value(task, "progress_updated_at", default="")
        if progress_stage or progress_percent not in ("", None):
            schedule_lines.extend(
                [
                    f"当前阶段: {progress_stage or '同步进行中'}",
                    f"当前进度: {progress_percent if progress_percent not in ('', None) else 0}%",
                    f"进度时间: {progress_updated_at or '--'}",
                ]
            )

        record_count = _first_value(task, "record_count", "total_records", default="")
        duration_seconds = _first_value(task, "duration_seconds", "duration", default="")
        if record_count not in ("", None) or duration_seconds not in ("", None):
            schedule_lines.extend(
                [
                    f"最近结果: {_result_status_text(_first_value(task, 'status', 'state', default='--'))}",
                    f"写入行数: {_format_count(record_count)}",
                    f"耗时: {_format_seconds(duration_seconds)}",
                ]
            )
        self.schedule_value.setText("\n".join(schedule_lines))

        error_time = _first_value(task, "last_error_time", "error_time", default="--")
        error_message = _first_value(task, "last_error_message", "error_message", default="暂无错误")
        error_count = _first_value(task, "error_count", "retry_count", default="0/3")
        self.error_value.setText(f"错误时间: {error_time}\n错误信息: {error_message}\n错误次数: {error_count}")


class TaskEditorDialog(QDialog):
    """Small editor for creating or updating a config-backed sync task."""

    def __init__(
        self,
        form_options: list[tuple[str, str]],
        initial: Mapping[str, Any] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("任务配置")
        self.setModal(False)
        self.setProperty("ui", "task-editor-dialog")
        self.setMinimumWidth(420)

        root = QVBoxLayout(self)
        root.setContentsMargins(SpacingTokens.LG, SpacingTokens.LG, SpacingTokens.LG, SpacingTokens.LG)
        root.setSpacing(SpacingTokens.MD)

        form = QFormLayout()
        form.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        form.setHorizontalSpacing(SpacingTokens.MD)
        form.setVerticalSpacing(SpacingTokens.SM)

        self.form_combo = QComboBox(self)
        for form_name, table_name in form_options:
            self.form_combo.addItem(form_name, table_name)
        self.form_combo.setProperty("td", "win11-input")
        self.form_combo.setFixedHeight(SizeTokens.CONTROL_HEIGHT)
        form.addRow("关联表单", self.form_combo)

        self.mode_combo = QComboBox(self)
        self.mode_combo.addItem("增量同步", "incremental")
        self.mode_combo.addItem("完全同步", "complete")
        self.mode_combo.setProperty("td", "win11-input")
        self.mode_combo.setFixedHeight(SizeTokens.CONTROL_HEIGHT)
        form.addRow("同步方式", self.mode_combo)

        self.enabled_check = QCheckBox("启用任务", self)
        form.addRow("启用状态", self.enabled_check)

        self.increment_field_edit = QLineEdit(self)
        self.increment_field_edit.setProperty("td", "win11-input")
        self.increment_field_edit.setPlaceholderText("例如 FModifyDate")
        self.increment_field_edit.setFixedHeight(SizeTokens.CONTROL_HEIGHT)
        form.addRow("增量字段", self.increment_field_edit)

        root.addLayout(form)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        self.btn_cancel = QPushButton("取消", self)
        self.btn_cancel.setProperty("class", "secondary")
        self.btn_cancel.clicked.connect(self.reject)
        action_row.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("保存", self)
        self.btn_save.setProperty("class", "primary")
        action_row.addWidget(self.btn_save)
        root.addLayout(action_row)

        self._apply_initial(initial or {})

    def _apply_initial(self, initial: Mapping[str, Any]) -> None:
        form_name = str(initial.get("form_name") or "")
        if form_name:
            index = self.form_combo.findText(form_name)
            if index >= 0:
                self.form_combo.setCurrentIndex(index)
        mode = str(initial.get("sync_mode") or "incremental")
        if mode in {"full", "reset"}:
            mode = "complete"
        mode_index = self.mode_combo.findData(mode)
        if mode_index >= 0:
            self.mode_combo.setCurrentIndex(mode_index)
        self.enabled_check.setChecked(bool(initial.get("enabled", True)))
        self.increment_field_edit.setText(str(initial.get("increment_field") or ""))

    def payload(self) -> dict[str, Any]:
        return {
            "form_name": self.form_combo.currentText(),
            "sync_mode": str(self.mode_combo.currentData() or "incremental"),
            "enabled": self.enabled_check.isChecked(),
            "increment_field": self.increment_field_edit.text().strip(),
        }


class TaskManagementPage(Win11PageScaffold):
    task_progress_requested = Signal(str, str, int)
    batch_progress_requested = Signal(str, int, object)

    """Task management page with real-service-first data loading."""

    # Static sample fallbacks removed — real data comes from TaskService._build_tasks()
    _SAMPLE_TASKS: list[dict[str, Any]] = []
    _SAMPLE_STATS: dict[str, Any] = {}

    def __init__(self, parent_gui, parent: QWidget | None = None) -> None:
        self.gui = parent_gui
        self.current_page = 1
        self.page_size = 10
        self.total_pages = 1
        self.total_tasks = 0
        self.tasks: list[dict[str, Any]] = []
        self.last_action_feedback = ""
        self._suppress_filter_query = False

        super().__init__(
            title="任务管理",
            eyebrow="任务",
            subtitle="管理同步任务的启停、运行状态和最近执行结果。",
            parent=parent,
        )
        self.task_progress_requested.connect(self._apply_task_progress)
        self.batch_progress_requested.connect(self._apply_batch_progress)
        self.setProperty("page", "task-management")
        self.set_hero_visible(False)
        self.hero_card.setVisible(False)
        self.primary_action_host.setVisible(False)
        self.summary_strip.setVisible(False)
        self._build_ui()
        self.load_tasks()

    def _build_ui(self) -> None:
        self.set_content(self._create_content())

    def _create_content(self) -> QWidget:
        root = QWidget()
        root.setObjectName("task_management_root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        layout.setSpacing(SpacingTokens.MD)

        layout.addWidget(self._create_title_row())
        layout.addWidget(self._create_operation_status_bar())
        layout.addWidget(self._create_filter_bar())
        layout.addWidget(self._create_workspace(), 1)
        return root

    def _create_title_row(self) -> QWidget:
        title_row = QWidget()
        layout = QHBoxLayout(title_row)
        layout.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        layout.setSpacing(SpacingTokens.MD)

        self.page_title = QLabel("任务管理")
        self.page_title.setProperty("ui", "task-page-title")
        _set_font(self.page_title, 20, True)
        layout.addWidget(self.page_title)
        layout.addStretch(1)

        self.btn_new_task = QPushButton("+ 新建任务")
        self.btn_new_task.setProperty("class", "primary")
        self.btn_new_task.setFixedHeight(38)
        self.btn_new_task.setMinimumWidth(120)
        self.btn_new_task.clicked.connect(self._handle_new_task)
        layout.addWidget(self.btn_new_task)

        self.btn_batch_enable = QPushButton("批量启用")
        self.btn_batch_enable.setProperty("class", "secondary")
        self.btn_batch_enable.setFixedHeight(38)
        self.btn_batch_enable.setMinimumWidth(104)
        self.btn_batch_enable.clicked.connect(self._handle_batch_enable)
        layout.addWidget(self.btn_batch_enable)

        self.btn_batch_pause = QPushButton("批量暂停")
        self.btn_batch_pause.setProperty("class", "secondary")
        self.btn_batch_pause.setFixedHeight(38)
        self.btn_batch_pause.setMinimumWidth(104)
        self.btn_batch_pause.setEnabled(False)
        self.btn_batch_pause.clicked.connect(self._handle_batch_pause)
        layout.addWidget(self.btn_batch_pause)

        self.btn_batch_run = QPushButton("批量运行")
        self.btn_batch_run.setProperty("class", "secondary")
        self.btn_batch_run.setFixedHeight(38)
        self.btn_batch_run.setMinimumWidth(104)
        self.btn_batch_run.setEnabled(False)
        self.btn_batch_run.clicked.connect(self._handle_batch_run)
        layout.addWidget(self.btn_batch_run)
        return title_row

    def _create_operation_status_bar(self) -> QFrame:
        self.operation_status_bar = QFrame()
        self.operation_status_bar.setProperty("ui", "task-operation-status-bar")
        self.operation_status_bar.setFixedHeight(36)
        layout = QHBoxLayout(self.operation_status_bar)
        layout.setContentsMargins(SpacingTokens.MD, SpacingTokens.XS, SpacingTokens.MD, SpacingTokens.XS)
        layout.setSpacing(SpacingTokens.SM)

        self.operation_status_dot = QLabel("●")
        self.operation_status_dot.setProperty("ui", "task-operation-status-dot")
        layout.addWidget(self.operation_status_dot)

        self.operation_status_summary = QLabel("最近操作：暂无记录")
        self.operation_status_summary.setProperty("ui", "task-operation-status-summary")
        layout.addWidget(self.operation_status_summary, 1)

        self.operation_status_time = QLabel("--")
        self.operation_status_time.setProperty("ui", "task-operation-status-time")
        layout.addWidget(self.operation_status_time)

        return self.operation_status_bar

    def _create_filter_bar(self) -> QFrame:
        self.filter_bar = QFrame()
        self.filter_bar.setProperty("ui", "task-filter-bar")
        self.filter_bar.setMaximumHeight(64)
        layout = QHBoxLayout(self.filter_bar)
        layout.setContentsMargins(SpacingTokens.LG, SpacingTokens.SM, SpacingTokens.LG, SpacingTokens.SM)
        layout.setSpacing(SpacingTokens.MD)

        self.combo_status = self._create_combo(["全部状态", "启用中", "已暂停", "失败"])
        self.combo_type = self._create_combo(["全部类型", "基础资料", "业务单据", "库存数据", "财务数据"])
        self.combo_mode = self._create_combo(["全部方式", "增量同步", "完全同步"])
        for combo in (self.combo_status, self.combo_type, self.combo_mode):
            combo.currentIndexChanged.connect(self._apply_filters)

        self._add_filter_group(layout, "任务状态：", self.combo_status)
        self._add_filter_group(layout, "表单类型：", self.combo_type)
        self._add_filter_group(layout, "执行方式：", self.combo_mode)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索任务名称或表单")
        self.search_box.setProperty("td", "win11-input")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setFixedHeight(SizeTokens.CONTROL_HEIGHT)
        self.search_box.setMinimumWidth(300)
        self.search_box.returnPressed.connect(self._apply_filters)
        self.search_box.editingFinished.connect(self._apply_filters)
        layout.addWidget(self.search_box, 1)

        self.btn_reset = QPushButton("重置")
        self.btn_reset.setProperty("class", "secondary")
        self.btn_reset.setFixedHeight(SizeTokens.BUTTON_HEIGHT)
        self.btn_reset.clicked.connect(self._reset_filters)
        layout.addWidget(self.btn_reset)

        self.btn_filter = QPushButton("筛选")
        self.btn_filter.setObjectName("task_filter_btn")
        self.btn_filter.setFixedHeight(SizeTokens.BUTTON_HEIGHT)
        self.btn_filter.setFixedWidth(56)
        self.btn_filter.clicked.connect(self._apply_filters)
        layout.addWidget(self.btn_filter)
        return self.filter_bar

    def _create_combo(self, items: list[str]) -> QComboBox:
        combo = QComboBox()
        combo.addItems(items)
        combo.setProperty("td", "win11-input")
        combo.setFixedHeight(SizeTokens.CONTROL_HEIGHT)
        combo.setMinimumWidth(116)
        return combo

    def _reset_filters(self) -> None:
        self._suppress_filter_query = True
        try:
            self.combo_status.setCurrentIndex(0)
            self.combo_type.setCurrentIndex(0)
            self.combo_mode.setCurrentIndex(0)
            self.search_box.clear()
        finally:
            self._suppress_filter_query = False
        self.load_tasks()

    def _apply_filters(self) -> None:
        if self._suppress_filter_query:
            return
        self.current_page = 1
        self.load_tasks()

    def _current_filters(self) -> dict[str, str]:
        filters: dict[str, str] = {}
        if self.combo_status.currentIndex() > 0:
            filters["status"] = self.combo_status.currentText()
        if self.combo_type.currentIndex() > 0:
            filters["form_type"] = self.combo_type.currentText()
        if self.combo_mode.currentIndex() > 0:
            filters["sync_mode"] = self.combo_mode.currentText()
        keyword = self.search_box.text().strip()
        if keyword:
            filters["keyword"] = keyword
        return filters

    def _add_filter_group(self, layout: QHBoxLayout, title: str, widget: QWidget) -> None:
        group = QWidget()
        group_layout = QHBoxLayout(group)
        group_layout.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        group_layout.setSpacing(SpacingTokens.XS)
        label = QLabel(title)
        label.setProperty("ui", "task-filter-label")
        group_layout.addWidget(label)
        group_layout.addWidget(widget)
        layout.addWidget(group)

    def _create_metric_grid(self) -> QWidget:
        grid_host = QWidget()
        layout = QGridLayout(grid_host)
        layout.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        layout.setHorizontalSpacing(SpacingTokens.MD)
        layout.setVerticalSpacing(SpacingTokens.MD)

        self.card_enabled = TaskMetricCard("启用任务", "play", "success")
        self.card_paused = TaskMetricCard("暂停任务", "pause", "warning")
        self.card_executed = TaskMetricCard("今日已执行", "chart", "info")
        self.card_retry = TaskMetricCard("失败待重试", "warning", "danger")
        for index, card in enumerate((self.card_enabled, self.card_paused, self.card_executed, self.card_retry)):
            layout.addWidget(card, 0, index)
            layout.setColumnStretch(index, 1)
        return grid_host

    def _create_workspace(self) -> QWidget:
        workspace = QWidget()
        layout = QHBoxLayout(workspace)
        layout.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        layout.setSpacing(SpacingTokens.MD)

        left_col = QVBoxLayout()
        left_col.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        left_col.setSpacing(SpacingTokens.MD)
        left_col.addWidget(self._create_metric_grid())
        left_col.addWidget(self._create_table_card(), 1)
        left_col.addWidget(self._create_pagination_card())
        layout.addLayout(left_col, 1)

        right_col = QVBoxLayout()
        right_col.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        right_col.setSpacing(SpacingTokens.MD)
        self.detail_panel = TaskDetailPanel()
        right_col.addWidget(self.detail_panel)
        layout.addLayout(right_col)
        return workspace

    def _create_table_card(self) -> QFrame:
        card = QFrame()
        card.setProperty("ui", "task-table-card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE, SpacingTokens.NONE)
        layout.setSpacing(SpacingTokens.NONE)

        self.task_table = DataTable(
            ["任务名称", "关联表单", "执行方式", "调度策略", "状态", "最近执行", "成功率", "操作"]
        )
        self.task_table.set_empty_text("暂无任务数据。")
        self.table = self.task_table.table
        self.table.verticalHeader().setDefaultSectionSize(50)
        self.table.setMouseTracking(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.viewport().installEventFilter(self)
        header = self.table.horizontalHeader()
        for column in range(8):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
        self._apply_table_column_widths()
        self.table.cellClicked.connect(self._handle_table_cell_clicked)
        self.table.itemSelectionChanged.connect(self._update_batch_action_state)
        layout.addWidget(self.task_table, 1)
        return card

    def eventFilter(self, watched: QWidget, event: QEvent) -> bool:  # noqa: N802 - Qt API
        if hasattr(self, "table") and watched is self.table.viewport() and event.type() == QEvent.Type.Resize:
            self._apply_table_column_widths()
        return super().eventFilter(watched, event)

    def _apply_table_column_widths(self) -> None:
        if not hasattr(self, "table"):
            return
        viewport_width = max(760, self.table.viewport().width())
        weights = (168, 138, 92, 94, 82, 168, 72, 88)
        total_weight = sum(weights)
        widths = [max(60, int(viewport_width * weight / total_weight)) for weight in weights]
        widths[0] = max(widths[0], 168)
        widths[1] = max(widths[1], 130)
        widths[5] = max(widths[5], 158)
        widths[7] = min(max(widths[7], 84), 92)
        delta = viewport_width - sum(widths)
        widths[0] += delta
        for column, width in enumerate(widths):
            self.table.setColumnWidth(column, max(60, width))

    def _create_pagination_card(self) -> QFrame:
        self.pagination_card = QFrame()
        self.pagination_card.setProperty("ui", "task-pagination-card")
        self.pagination_card.setFixedHeight(46)
        layout = QHBoxLayout(self.pagination_card)
        layout.setContentsMargins(SpacingTokens.NONE, SpacingTokens.XS, SpacingTokens.NONE, SpacingTokens.XS)
        layout.setSpacing(SpacingTokens.SM)

        self.lbl_total = QLabel("共 0 条")
        self.lbl_total.setProperty("ui", "task-pagination-text")
        layout.addWidget(self.lbl_total)
        layout.addSpacing(SpacingTokens.LG)

        self.page_size_combo = QComboBox()
        self.page_size_combo.addItem("10 条/页", 10)
        self.page_size_combo.addItem("20 条/页", 20)
        self.page_size_combo.setProperty("td", "win11-input")
        self.page_size_combo.setFixedHeight(SizeTokens.PAGINATION_BUTTON_HEIGHT)
        self.page_size_combo.setFixedWidth(112)
        self.page_size_combo.currentIndexChanged.connect(self._handle_page_size_changed)
        layout.addWidget(self.page_size_combo)
        layout.addStretch(1)

        self.btn_prev = self._create_page_button("←")
        self.btn_page_1 = self._create_page_button("1", checked=True)
        self.btn_page_2 = self._create_page_button("2")
        self.btn_page_3 = self._create_page_button("3")
        self.btn_page_4 = self._create_page_button("4")
        self.btn_next = self._create_page_button("→")
        for button in (self.btn_prev, self.btn_page_1, self.btn_page_2, self.btn_page_3, self.btn_page_4, self.btn_next):
            layout.addWidget(button)
        self.btn_prev.clicked.connect(self._go_prev_page)
        self.btn_next.clicked.connect(self._go_next_page)
        for button in (self.btn_page_1, self.btn_page_2, self.btn_page_3, self.btn_page_4):
            button.clicked.connect(lambda _checked=False, btn=button: self._go_page(int(btn.text())))

        return self.pagination_card

    def _create_page_button(self, text: str, *, checked: bool = False) -> QPushButton:
        button = QPushButton(text)
        button.setCheckable(True)
        button.setChecked(checked)
        button.setProperty("ui", "task-page-button")
        button.setFixedSize(SizeTokens.HISTORY_PAGINATION_LABEL_WIDTH, SizeTokens.PAGINATION_BUTTON_HEIGHT)
        return button

    def load_tasks(self) -> None:
        service = self._resolve_task_service()
        filters = self._current_filters() if hasattr(self, "combo_status") else {}
        tasks, total = self._load_tasks(service, filters)
        stats = self._derive_stats(tasks) if service is None else self._load_stats(service)
        if not stats or stats == self._derive_stats([]):
            stats = self._derive_stats(tasks)
        if "total" not in stats:
            stats["total"] = total if total is not None else len(tasks)

        self.tasks = tasks
        self.total_tasks = int(stats.get("total") or total or len(tasks))
        self._update_metrics(stats)
        self._update_table(tasks)
        self.lbl_total.setText(f"共 {self.total_tasks} 条")
        self.detail_panel.set_task(tasks[0] if tasks else None)
        self._update_pagination()
        self._refresh_operation_audit()

    def _refresh_operation_audit(self) -> None:
        service = self._resolve_task_service()
        get_audit = getattr(service, "get_latest_operation_audit", None)
        audit = get_audit() if callable(get_audit) else {}
        if not isinstance(audit, Mapping) or not audit:
            self.operation_status_summary.setText("最近操作：暂无记录")
            self.operation_status_time.setText("--")
            self.operation_status_dot.setProperty("status", "idle")
            _refresh_style(self.operation_status_dot)
            return

        summary = str(audit.get("summary") or "最近操作：暂无")
        timestamp = str(audit.get("timestamp") or "--")
        status = str(audit.get("status") or "idle")
        self.operation_status_summary.setText(summary)
        self.operation_status_time.setText(timestamp)
        self.operation_status_dot.setProperty("status", status)
        _refresh_style(self.operation_status_dot)

    def _set_operation_feedback(
        self,
        summary: str,
        *,
        status: str = "success",
        detail: str = "",
        timestamp: str | None = None,
    ) -> None:
        self.last_action_feedback = summary
        self.operation_status_summary.setText(summary)
        self.operation_status_time.setText(timestamp or "--")
        self.operation_status_dot.setProperty("status", status)
        _refresh_style(self.operation_status_dot)

    def _go_prev_page(self) -> None:
        self._go_page(self.current_page - 1)

    def _go_next_page(self) -> None:
        self._go_page(self.current_page + 1)

    def _go_page(self, page: int) -> None:
        target = max(1, min(int(page), self.total_pages))
        if target == self.current_page:
            return
        self.current_page = target
        self.load_tasks()

    def _handle_page_size_changed(self) -> None:
        self.page_size = int(self.page_size_combo.currentData() or 10)
        self.current_page = 1
        self.load_tasks()

    def _update_pagination(self) -> None:
        self.total_pages = max(1, math.ceil(max(0, self.total_tasks) / max(1, self.page_size)))
        self.current_page = max(1, min(self.current_page, self.total_pages))
        self.btn_prev.setEnabled(self.current_page > 1)
        self.btn_next.setEnabled(self.current_page < self.total_pages)

        page_buttons = (self.btn_page_1, self.btn_page_2, self.btn_page_3, self.btn_page_4)
        start_page = min(max(1, self.current_page), max(1, self.total_pages - len(page_buttons) + 1))
        for offset, button in enumerate(page_buttons):
            page_number = start_page + offset
            button.setText(str(page_number))
            button.setVisible(page_number <= self.total_pages)
            button.setEnabled(page_number <= self.total_pages)
            button.setChecked(page_number == self.current_page)

    def _resolve_task_service(self) -> Any:
        return getattr(self.gui, "task_service", None) or getattr(self.gui, "task_manager", None) or default_task_service

    @staticmethod
    def _service_has_operation_audit(service: Any) -> bool:
        return callable(getattr(service, "get_latest_operation_audit", None))

    def _load_tasks(self, service: Any, filters: Mapping[str, str] | None = None) -> tuple[list[dict[str, Any]], int | None]:
        if service is None:
            return [], 0
        for method_name in ("get_tasks", "list_tasks", "query_tasks"):
            method = getattr(service, method_name, None)
            if callable(method):
                result = self._call_task_method(method, filters or {})
                tasks, total = self._normalize_task_result(result)
                if self._method_supports_pagination(method):
                    return tasks, total
                filtered = self._filter_tasks(tasks, filters or {})
                return self._paginate_tasks(filtered), len(filtered)
        return [], 0

    def _call_task_method(self, method, filters: Mapping[str, str]):
        try:
            signature = inspect.signature(method)
        except (TypeError, ValueError):
            try:
                return method(filters=filters, page=self.current_page, page_size=self.page_size)
            except TypeError:
                if filters:
                    return method(filters=filters)
                return method()
        if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()):
            return method(filters=filters, page=self.current_page, page_size=self.page_size)
        kwargs: dict[str, Any] = {}
        if "filters" in signature.parameters:
            kwargs["filters"] = filters
        if "page" in signature.parameters:
            kwargs["page"] = self.current_page
        if "page_size" in signature.parameters:
            kwargs["page_size"] = self.page_size
        if kwargs:
            return method(**kwargs)
        return method()

    @staticmethod
    def _method_supports_pagination(method) -> bool:
        try:
            signature = inspect.signature(method)
        except (TypeError, ValueError):
            return True
        return any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()) or (
            "page" in signature.parameters and "page_size" in signature.parameters
        )

    def _paginate_tasks(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        start = (self.current_page - 1) * self.page_size
        return tasks[start : start + self.page_size]

    def _filter_tasks(self, tasks: list[dict[str, Any]], filters: Mapping[str, str]) -> list[dict[str, Any]]:
        if not filters:
            return tasks
        status_filter = filters.get("status")
        type_filter = filters.get("form_type")
        mode_filter = filters.get("sync_mode")
        keyword = (filters.get("keyword") or "").strip().lower()
        result: list[dict[str, Any]] = []
        for task in tasks:
            status_text, _ = _status_display(_first_value(task, "status", "state", default=""))
            if status_filter and status_text != status_filter:
                continue
            if type_filter and not self._task_matches_form_type(task, type_filter):
                continue
            mode_text = str(_first_value(task, "sync_mode", "mode", "execution_mode", default=""))
            if mode_filter and mode_text != mode_filter:
                continue
            haystack = " ".join(
                str(_first_value(task, key, default=""))
                for key in ("task_name", "name", "title", "form_name", "target_table", "scope")
            ).lower()
            if keyword and keyword not in haystack:
                continue
            result.append(task)
        return result

    @staticmethod
    def _task_matches_form_type(task: Mapping[str, Any], form_type: str) -> bool:
        text = " ".join(
            str(_first_value(task, key, default=""))
            for key in ("task_name", "form_name", "target_table", "scope")
        )
        if form_type == "基础资料":
            return any(token in text for token in ("基础", "资料", "物料", "客户"))
        if form_type == "业务单据":
            return any(token in text for token in ("订单", "单据", "销售", "采购", "收款", "付款"))
        if form_type == "库存数据":
            return "库存" in text
        if form_type == "财务数据":
            return any(token in text for token in ("财务", "收款", "付款", "应收", "应付"))
        return True

    def _load_stats(self, service: Any) -> dict[str, Any]:
        if service is None:
            return {}
        for method_name in ("get_task_stats", "get_stats", "stats"):
            method = getattr(service, method_name, None)
            if callable(method):
                result = method()
                return dict(result or {}) if isinstance(result, Mapping) else {}
        return self._derive_stats(self.tasks)

    def _normalize_task_result(self, result: Any) -> tuple[list[dict[str, Any]], int | None]:
        total = None
        raw_tasks = result
        if isinstance(result, Mapping):
            raw_tasks = (
                result.get("tasks")
                or result.get("items")
                or result.get("rows")
                or result.get("data")
                or result.get("records")
                or []
            )
            total = result.get("total")
        elif isinstance(result, tuple) and len(result) >= 2:
            raw_tasks, total = result[0], result[1]

        tasks: list[dict[str, Any]] = []
        if isinstance(raw_tasks, Sequence) and not isinstance(raw_tasks, (str, bytes)):
            for item in raw_tasks:
                if isinstance(item, Mapping):
                    tasks.append(dict(item))
                elif isinstance(item, Sequence) and not isinstance(item, (str, bytes)):
                    tasks.append(self._row_to_task(item))
        return tasks, int(total) if total not in (None, "") else None

    def _row_to_task(self, row: Sequence[Any]) -> dict[str, Any]:
        keys = ["task_name", "form_name", "sync_mode", "schedule", "status", "last_run", "success_rate"]
        return {key: row[index] if index < len(row) else "" for index, key in enumerate(keys)}

    def _derive_stats(self, tasks: list[dict[str, Any]]) -> dict[str, Any]:
        enabled = 0
        paused = 0
        retry = 0
        for task in tasks:
            _, tone = _status_display(_first_value(task, "status", "state", default=""))
            if tone == "success":
                enabled += 1
            elif tone == "warning":
                paused += 1
            elif tone == "danger":
                retry += 1
        return {
            "enabled": enabled,
            "paused": paused,
            "executed_today": len(tasks),
            "retry": retry,
            "enabled_delta": "较昨日 --",
            "paused_delta": "较昨日 --",
            "executed_delta": "较昨日 --",
            "retry_delta": "较昨日 --",
            "total": len(tasks),
        }

    def _update_metrics(self, stats: Mapping[str, Any]) -> None:
        self.card_enabled.set_data(
            _first_value(stats, "enabled", "enabled_count", "active", default=0),
            str(_first_value(stats, "enabled_delta", default="较昨日 --")),
        )
        self.card_paused.set_data(
            _first_value(stats, "paused", "paused_count", "disabled", default=0),
            str(_first_value(stats, "paused_delta", default="较昨日 --")),
        )
        self.card_executed.set_data(
            _first_value(stats, "executed_today", "today_executed", "executed", default=0),
            str(_first_value(stats, "executed_delta", default="较昨日 --")),
        )
        self.card_retry.set_data(
            _first_value(stats, "retry", "retry_count", "failed_retry", default=0),
            str(_first_value(stats, "retry_delta", default="较昨日 --")),
        )

    def _update_table(self, tasks: list[dict[str, Any]]) -> None:
        rows = []
        for task in tasks:
            rows.append(
                [
                    str(_first_value(task, "task_name", "name", "title", default="--")),
                    str(_first_value(task, "form_name", "form", "form_id", default="--")),
                    str(_first_value(task, "sync_mode", "mode", "execution_mode", default="--")),
                    str(_first_value(task, "schedule", "schedule_policy", "cron", default="--")),
                    "",
                    str(_first_value(task, "last_run", "last_run_at", "last_execute_time", default="--")),
                    str(_first_value(task, "success_rate", "rate", default="--")),
                    "",
                ]
            )
        self.task_table.set_data(rows)
        for row_index, task in enumerate(tasks):
            for col_index in (0, 1, 2, 3, 5, 6, 7):
                item = self.table.item(row_index, col_index)
                if item is not None:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                    item.setToolTip(item.text())
            status_text, tone = _status_display(_first_value(task, "status", "state", default=""))
            self.table.setCellWidget(row_index, 4, TaskStatusTag(status_text, tone, self.table))
            task_name = str(_first_value(task, "task_name", "name", "title", default="--"))
            self.table.setCellWidget(
                row_index,
                7,
                TaskActionCell(task_name, self._handle_task_action, self.table, is_running=status_text == "运行中"),
            )
        if tasks:
            self.table.setCurrentCell(0, 0)
            self.table.selectRow(0)
        self._update_batch_action_state()

    def _handle_table_cell_clicked(self, row: int, column: int) -> None:
        if 0 <= row < len(self.tasks):
            self.table.setCurrentCell(row, max(0, column))
            self.detail_panel.set_task(self.tasks[row])

    def _handle_task_action(self, action_label: str, task_name: str, action_cell: TaskActionCell | None = None) -> None:
        service = self._resolve_task_service()
        if action_label == "更多操作":
            self._show_task_more_menu(task_name, action_cell)
            return
        if action_label == "编辑任务":
            self._open_task_editor(task_name)
            return
        action_methods = {
            "立即运行": "run_task",
            "暂停任务": "pause_task",
            "中止运行": "cancel_task",
        }
        method_name = action_methods.get(action_label)
        method = getattr(service, method_name, None) if method_name else None
        button = action_cell.btn_run if action_label == "立即运行" and action_cell is not None else None
        if button is not None:
            button.setEnabled(False)
        if action_label == "立即运行":
            self._set_task_running_feedback(task_name)
        try:
            if callable(method):
                if action_label == "立即运行":
                    result = self._call_with_optional_progress(
                        method,
                        task_name,
                        progress_callback=self._make_task_progress_callback(task_name),
                    )
                else:
                    result = method(task_name)
            else:
                result = None
            if action_label == "中止运行":
                self._handle_cancel_task_result(task_name, result)
                return
            self._set_operation_feedback(f"{action_label}：{task_name}", status="success")
            if action_label in {"立即运行", "暂停任务"}:
                self.load_tasks()
        except Exception as exc:
            self._set_operation_feedback(f"{action_label}失败：{exc}", status="failed", detail=f"{task_name}：{exc}")
            if self._service_has_operation_audit(service):
                self._refresh_operation_audit()
        finally:
            if button is not None:
                button.setEnabled(True)

    def _make_task_progress_callback(self, task_name: str):
        def handle_progress(message: str, percent: int) -> None:
            safe_percent = self._normalize_progress_percent(percent)
            safe_message = str(message or "同步进行中")
            self.task_progress_requested.emit(task_name, safe_message, safe_percent)

        return handle_progress

    def _apply_task_progress(self, task_name: str, message: str, percent: int) -> None:
        self._update_task_progress_detail(task_name, message, percent)
        self._set_operation_feedback(
            f"立即运行：{task_name}，{percent}%，{message}",
            status="running",
            detail=f"{task_name}：{message}，{percent}%",
        )

    def _update_task_progress_detail(self, task_name: str, stage: str, percent: int) -> None:
        updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for row, task in enumerate(self.tasks):
            current_name = str(_first_value(task, "task_name", "name", "title", default=""))
            if current_name != task_name:
                continue
            task.update(
                {
                    "status": "running",
                    "success_rate": "--",
                    "progress_stage": stage,
                    "progress_percent": percent,
                    "progress_updated_at": updated_at,
                }
            )
            self.table.setCellWidget(row, 4, TaskStatusTag("运行中", "info", self.table))
            self.table.setCellWidget(
                row,
                7,
                TaskActionCell(task_name, self._handle_task_action, self.table, is_running=True),
            )
            if self.table.currentRow() == row:
                self.detail_panel.set_task(task)
            break

    @staticmethod
    def _call_with_optional_progress(method, *args, progress_callback):
        try:
            return method(*args, progress_callback=progress_callback)
        except TypeError as exc:
            if "progress_callback" not in str(exc):
                raise
            return method(*args)

    @staticmethod
    def _normalize_progress_percent(value: Any) -> int:
        try:
            percent = int(float(str(value).replace("%", "")))
        except (TypeError, ValueError):
            return 0
        return max(0, min(percent, 100))

    def _handle_cancel_task_result(self, task_name: str, result: Any) -> None:
        message = "当前同步任务暂不支持中止"
        status = "warning"
        if isinstance(result, Mapping):
            message = str(result.get("message") or message)
            status = "success" if result.get("cancelled") else "warning"
        self._set_operation_feedback(f"中止任务：{task_name}，{message}", status=status, detail=f"{task_name}：{message}")
        service = self._resolve_task_service()
        if self._service_has_operation_audit(service):
            self._refresh_operation_audit()

    def _set_task_running_feedback(self, task_name: str) -> None:
        self._set_operation_feedback(
            f"立即运行：{task_name}，运行中",
            status="running",
            detail=f"{task_name}：运行中",
        )
        for row, task in enumerate(self.tasks):
            if str(_first_value(task, "task_name", "name", "title", default="")) != task_name:
                continue
            task["status"] = "running"
            task["success_rate"] = "--"
            self.table.setCellWidget(row, 4, TaskStatusTag("运行中", "info", self.table))
            self.table.setCellWidget(
                row,
                7,
                TaskActionCell(task_name, self._handle_task_action, self.table, is_running=True),
            )
            if self.table.currentRow() == row:
                self.detail_panel.set_task(task)
            break

    def _set_batch_running_feedback(self, task_names: list[str]) -> None:
        task_label = "、".join(task_names)
        self._set_operation_feedback(
            f"批量运行：{len(task_names)} 个任务运行中",
            status="running",
            detail=f"运行任务：{task_label}",
        )
        task_name_set = set(task_names)
        for row, task in enumerate(self.tasks):
            task_name = str(_first_value(task, "task_name", "name", "title", default=""))
            if task_name not in task_name_set:
                continue
            task["status"] = "running"
            task["success_rate"] = "--"
            self.table.setCellWidget(row, 4, TaskStatusTag("运行中", "info", self.table))
            self.table.setCellWidget(
                row,
                7,
                TaskActionCell(task_name, self._handle_task_action, self.table, is_running=True),
            )
        current_row = self.table.currentRow()
        if 0 <= current_row < len(self.tasks):
            self.detail_panel.set_task(self.tasks[current_row])

    def _show_task_more_menu(self, task_name: str, action_cell: TaskActionCell | None = None) -> None:
        self.task_more_menu = QMenu(self)
        for action_label in ("立即运行", "暂停任务", "编辑任务"):
            action = self.task_more_menu.addAction(action_label)
            action.triggered.connect(
                lambda _checked=False, label=action_label: self._handle_task_action(label, task_name, action_cell)
            )
        if action_cell is not None:
            self.task_more_menu.popup(action_cell.btn_more.mapToGlobal(action_cell.btn_more.rect().bottomLeft()))

    def _selected_task_names(self) -> list[str]:
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        return [
            str(_first_value(self.tasks[row], "task_name", "name", "title", default=""))
            for row in rows
            if 0 <= row < len(self.tasks)
        ]

    def _update_batch_action_state(self) -> None:
        if not hasattr(self, "btn_batch_pause"):
            return
        has_selection = len(self._selected_task_names()) >= 2 if hasattr(self, "table") else False
        self.btn_batch_pause.setEnabled(has_selection)
        self.btn_batch_run.setEnabled(has_selection)

    def _handle_batch_pause(self) -> None:
        task_names = self._selected_task_names()
        if not task_names:
            self._set_operation_feedback("批量暂停：请选择任务", status="warning")
            return
        service = self._resolve_task_service()
        method = getattr(service, "pause_tasks", None)
        if not callable(method):
            self._set_operation_feedback("批量暂停失败：当前未配置任务服务", status="failed")
            return
        task_label = "、".join(task_names)
        if not confirm_task_action(self, "确认批量暂停", f"确定要暂停以下任务吗？\n{task_label}"):
            self._set_operation_feedback("批量暂停：已取消", status="warning")
            return
        try:
            paused_count = int(method(task_names) or 0)
            self._set_operation_feedback(f"批量暂停：已暂停 {paused_count} 个任务", status="success")
            self.load_tasks()
        except Exception as exc:
            self._set_operation_feedback(f"批量暂停失败：{exc}", status="failed", detail=str(exc))

    def _handle_batch_run(self) -> None:
        task_names = self._selected_task_names()
        if not task_names:
            self._set_operation_feedback("批量运行：请选择任务", status="warning")
            return
        service = self._resolve_task_service()
        method = getattr(service, "run_tasks", None)
        if not callable(method):
            self._set_operation_feedback("批量运行失败：当前未配置任务服务", status="failed")
            return
        task_label = "、".join(task_names)
        if not confirm_task_action(self, "确认批量运行", f"确定要立即运行以下任务吗？\n{task_label}"):
            self._set_operation_feedback("批量运行：已取消", status="warning")
            return
        self._set_batch_running_feedback(task_names)
        self.btn_batch_run.setEnabled(False)
        self.btn_batch_pause.setEnabled(False)
        try:
            result = self._call_with_optional_progress(
                method,
                task_names,
                progress_callback=self._make_batch_progress_callback(task_names),
            )
            requested = result.get("requested", len(task_names)) if isinstance(result, Mapping) else len(task_names)
            succeeded = result.get("succeeded", 0) if isinstance(result, Mapping) else 0
            failed = result.get("failed", 0) if isinstance(result, Mapping) else 0
            feedback = f"批量运行：成功 {succeeded}/{requested}，失败 {failed}"
            errors = result.get("errors", []) if isinstance(result, Mapping) else []
            details: list[str] = []
            if errors:
                for error in errors:
                    if not isinstance(error, Mapping):
                        continue
                    task_name = str(error.get("task_name") or "").strip()
                    message = str(error.get("error") or "").strip()
                    if task_name and message:
                        details.append(f"{task_name}：{message}")
                    elif task_name:
                        details.append(task_name)
                    elif message:
                        details.append(message)
                if details:
                    feedback = f"{feedback}；{'；'.join(details)}"
            self._set_operation_feedback(feedback, status="failed" if failed else "success", detail="；".join(details))
            self.load_tasks()
            if self._service_has_operation_audit(service):
                self._refresh_operation_audit()
        except Exception as exc:
            self._set_operation_feedback(f"批量运行失败：{exc}", status="failed", detail=str(exc))
        finally:
            self._update_batch_action_state()

    def _make_batch_progress_callback(self, task_names: list[str] | None = None):
        def handle_progress(message: str, percent: int) -> None:
            safe_percent = self._normalize_progress_percent(percent)
            safe_message = str(message or "同步进行中")
            self.batch_progress_requested.emit(safe_message, safe_percent, list(task_names or []))

        return handle_progress

    def _apply_batch_progress(self, message: str, percent: int, task_names: object) -> None:
        names = list(task_names) if isinstance(task_names, Sequence) and not isinstance(task_names, str) else []
        matched_task = self._match_progress_task_name(message, names)
        if matched_task:
            self._update_task_progress_detail(matched_task, message, percent)
        self._set_operation_feedback(
            f"批量运行：{percent}%，{message}",
            status="running",
            detail=f"批量运行：{message}，{percent}%",
        )

    @staticmethod
    def _match_progress_task_name(message: str, task_names: Sequence[str]) -> str:
        normalized_message = str(message or "")
        for task_name in task_names:
            safe_name = str(task_name or "")
            if safe_name and normalized_message.startswith((safe_name, safe_name.removesuffix("同步"))):
                return safe_name
        return ""

    def _handle_new_task(self) -> None:
        self._open_task_editor()

    def _open_task_editor(self, task_name: str | None = None) -> None:
        service = self._resolve_task_service()
        get_options = getattr(service, "get_form_options", None)
        get_initial = getattr(service, "get_task_editor_data", None)
        form_options = get_options() if callable(get_options) else []
        initial = get_initial(task_name) if task_name and callable(get_initial) else {}
        self.task_editor_dialog = TaskEditorDialog(form_options, initial, self)
        self.task_editor_dialog.btn_save.clicked.connect(self._save_task_editor)
        self.task_editor_dialog.show()
        feedback = "新建任务：已打开任务配置" if not task_name else f"编辑任务：{task_name}"
        self._set_operation_feedback(feedback, status="success")

    def _save_task_editor(self) -> None:
        service = self._resolve_task_service()
        save_task = getattr(service, "save_task", None)
        if not callable(save_task):
            self._set_operation_feedback("保存任务失败：当前未配置任务服务", status="failed")
            return
        try:
            result = save_task(self.task_editor_dialog.payload())
            form_name = result.get("form_name") if isinstance(result, Mapping) else self.task_editor_dialog.form_combo.currentText()
            self._set_operation_feedback(f"保存任务：{form_name}", status="success")
            self.task_editor_dialog.accept()
            self.load_tasks()
        except Exception as exc:
            self._set_operation_feedback(f"保存任务失败：{exc}", status="failed", detail=str(exc))

    def _handle_batch_enable(self) -> None:
        service = self._resolve_task_service()
        result = self._call_first_service_method(
            service,
            ("batch_enable_tasks", "enable_all_tasks", "enable_selected_tasks", "batch_enable"),
        )
        if result is False:
            self._set_operation_feedback("批量启用：当前未配置任务服务", status="failed")
            return

        enabled_count = self._extract_affected_count(result)
        self._set_operation_feedback(f"批量启用：已启用 {enabled_count} 个任务", status="success")
        self.load_tasks()

    @staticmethod
    def _call_first_service_method(service: Any, method_names: tuple[str, ...]) -> Any:
        if service is None:
            return False
        for method_name in method_names:
            method = getattr(service, method_name, None)
            if callable(method):
                return method()
        return False

    @staticmethod
    def _extract_affected_count(result: Any) -> int:
        if isinstance(result, Mapping):
            value = (
                result.get("enabled")
                or result.get("count")
                or result.get("affected")
                or result.get("updated")
                or result.get("total")
                or 0
            )
        else:
            value = result
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
