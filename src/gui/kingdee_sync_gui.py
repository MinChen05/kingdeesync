"""Desktop GUI shell for the Kingdee sync tool."""

import ctypes
import logging
import os
import sys
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

wintypes: Any
try:
    from ctypes import wintypes as ctypes_wintypes
except Exception:  # pragma: no cover
    wintypes = None
else:
    wintypes = ctypes_wintypes

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.config.config_manager import config_manager
from src.core.scheduler import auto_scheduler
from src.gui.components.buttons import ClickableLabel
from src.gui.components.common import SvgIconLabel
from src.gui.design_tokens import ColorTokens
from src.gui.feedback import UiFeedback
from src.gui.pages.dashboard_page import DashboardPage
from src.gui.pages.data_source_page import DataSourcePage
from src.gui.pages.diagnostics_page import DiagnosticsPage
from src.gui.pages.forms_page import FormConfigPage
from src.gui.pages.history_page import HistoryPage
from src.gui.pages.log_center_page import LogCenterPage
from src.gui.pages.schedule_page import SchedulePage
from src.gui.pages.settings_page import SettingsPage
from src.gui.pages.sync_page import SyncPage
from src.gui.pages.task_management_page import TaskManagementPage
from src.gui.ui_text import ShellText


def _make_nav_icon(icon_id: str, size: int = 18, color: str = "#41607B") -> QIcon:
    """Create a QPainter-drawn icon for sidebar navigation."""
    from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap, QRadialGradient

    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(color), 1.4))
    p.setBrush(Qt.NoBrush)
    s = icon_id
    if s == "dashboard":
        p.drawEllipse(2, 2, size - 4, size - 4)
        p.setBrush(QBrush(QColor(color)))
        p.drawPie(2, 2, size - 4, size - 4, 90 * 16, -95 * 16)
        p.setBrush(Qt.NoBrush)
        p.drawLine(size // 2, size // 2, size // 2, 3)
        p.drawLine(size // 2, size // 2, size - 3, size // 2)
    elif s == "history":
        p.drawEllipse(2, 2, size - 4, size - 4)
        p.drawLine(size // 2, 4, size // 2, size // 2)
        p.drawLine(size // 2, size // 2, size - 4, size // 2 + 2)
    elif s == "task_management":
        p.drawRoundedRect(2, 1, size - 4, size - 2, 2, 2)
        p.drawLine(4, 5, size - 4, 5)
        p.drawLine(4, size // 2, size - 4, size // 2)
        p.drawLine(4, size - 4, size // 2, size - 4)
    elif s == "data_source":
        p.drawRoundedRect(2, 3, size - 4, size - 6, 3, 3)
        p.drawEllipse(size // 2 - 2, size // 2 - 1, 4, 4)
    elif s == "forms":
        p.drawRoundedRect(2, 1, size - 4, size - 2, 2, 2)
        p.drawLine(4, 5, size - 4, 5)
        p.drawLine(4, size // 2, size - 6, size // 2)
    elif s == "schedule":
        p.drawEllipse(2, 2, size - 4, size - 4)
        p.drawLine(size // 2, 4, size // 2, size // 2)
        p.drawLine(size // 2, size // 2, size - 5, size // 2 + 2)
    elif s == "diagnostics":
        p.drawLine(4, size - 3, size // 2, 4)
        p.drawLine(size // 2, 4, size - 4, size - 3)
        p.drawLine(6, size // 2 + 1, size - 6, size // 2 + 1)
    elif s == "log_center":
        p.drawRoundedRect(2, 1, size - 4, size - 2, 2, 2)
        p.drawLine(4, 5, size - 4, 5)
        p.drawLine(4, size // 2, size - 4, size // 2)
        p.drawLine(4, size - 4, size // 2, size - 4)
    elif s == "settings":
        p.drawEllipse(size // 2 - 2, size // 2 - 2, 4, 4)
        p.drawEllipse(size // 2 - 4, size // 2 - 4, 8, 8)
    p.end()
    return QIcon(pm)


SIDEBAR_NAV_ICON_FILES = {
    "dashboard": "概览_chart-proportion.svg",
    "sync": "icons/sync.svg",
    "history": "同步历史_time.svg",
    "task_management": "任务管理_transaction-order.svg",
    "data_source": "数据源管理_data.svg",
    "forms": "表单映射_link.svg",
    "schedule": "调度管理_schedule.svg",
    "diagnostics": "异常诊断_caution.svg",
    "log_center": "日志中心_notes.svg",
    "settings": "系统设置_setting.svg",
}


def _make_cloud_logo(size: int = 46, color: str = ""):
    """Draw the target sidebar cloud mark as a real pixmap."""
    from PySide6.QtGui import QPixmap

    accent = QColor(color or ColorTokens.ACCENT_700)
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)

    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(accent, max(2.0, size * 0.055))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    w = float(size)
    path = QPainterPath()
    path.moveTo(w * 0.18, w * 0.65)
    path.cubicTo(w * 0.07, w * 0.64, w * 0.06, w * 0.43, w * 0.22, w * 0.42)
    path.cubicTo(w * 0.25, w * 0.25, w * 0.45, w * 0.20, w * 0.56, w * 0.32)
    path.cubicTo(w * 0.67, w * 0.29, w * 0.81, w * 0.37, w * 0.82, w * 0.52)
    path.cubicTo(w * 0.95, w * 0.54, w * 0.95, w * 0.73, w * 0.78, w * 0.74)
    path.lineTo(w * 0.19, w * 0.74)
    painter.drawPath(path)

    inner_pen = QPen(accent, max(1.7, size * 0.045))
    inner_pen.setCapStyle(Qt.RoundCap)
    inner_pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(inner_pen)
    painter.drawArc(int(w * 0.28), int(w * 0.48), int(w * 0.22), int(w * 0.22), 210 * 16, 260 * 16)
    painter.drawArc(int(w * 0.47), int(w * 0.48), int(w * 0.22), int(w * 0.22), 30 * 16, 260 * 16)
    painter.end()
    return pm


def _make_user_icon(size: int = 18, color: str = ""):
    """Draw a compact account icon for the top bar."""
    from PySide6.QtGui import QPixmap

    ink = QColor(color or ColorTokens.NEUTRAL_700)
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(ink)
    painter.drawEllipse(int(size * 0.34), int(size * 0.14), int(size * 0.32), int(size * 0.32))
    body = QRect(int(size * 0.18), int(size * 0.50), int(size * 0.64), int(size * 0.36))
    painter.drawRoundedRect(body, int(size * 0.18), int(size * 0.18))
    painter.end()
    return pm


class KingdeeSyncGUI(QMainWindow):
    """Main application window for the desktop sync console."""

    def __init__(self):
        super().__init__()
        self.setProperty("theme", "win11-shell")
        self.assets_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets"
        )
        self.logger = logging.getLogger(__name__)
        self.kd_connected = False
        self.db_connected = False
        self.sync_running = False
        self.form_selector = None
        self.sync_type_combo = None
        self.start_sync_btn = None
        self.test_conn_btn = None
        # removed: self.title_bar = None (DesktopTitleBar deleted)
        self.main_splitter = None
        self.sidebar = None
        self.sidebar_logo_subtitle = None
        self.sidebar_section_title = None
        self.sidebar_status_card = None
        self.sidebar_compact = False
        self.sidebar_expanded_width = 240
        self.sidebar_compact_width = 96
        self.shortcuts = []
        self.pages = {}
        self.nav_tree = None
        self.nav_item_map = {}
        self.nav_tool_buttons = {}
        self.topbar_action_buttons = []
        self.current_page_id = "dashboard"
        self.page_order = [
            "dashboard",
            "sync",
            "history",
            "task_management",
            "data_source",
            "forms",
            "schedule",
            "diagnostics",
            "log_center",
            "settings",
        ]
        self.page_index_map = {page_id: idx for idx, page_id in enumerate(self.page_order)}
        self.page_meta = {
            "dashboard": ("概览", "查看核心运行指标、连接状态与任务概览"),
            "sync": ("同步执行", "选择同步范围并手动发起数据同步"),
            "history": ("同步历史", "查看同步任务历史、筛选与追踪问题"),
            "task_management": ("任务管理", "管理和监控数据同步任务的创建、编辑与运行状态"),
            "data_source": ("数据源管理", "配置和管理金蝶 API 及数据库等外部数据源连接"),
            "forms": ("表单映射", "维护同步表单映射与字段配置"),
            "schedule": ("调度管理", "管理自动调度任务与执行状态"),
            "diagnostics": ("异常诊断", "诊断同步过程中的异常，定位问题根因并查看修复建议"),
            "log_center": ("日志中心", "集中查看系统运行日志，支持关键字搜索与级别筛选"),
            "settings": ("系统设置", "维护金蝶与数据库连接等基础配置"),
        }
        self._resize_border_px = 8
        self._windows_effects_applied = False
        self._snap_overlay = None
        self._snap_target_mode = None
        self._snap_target_rect = QRect()
        self._snap_target_region = None
        self._snap_target_signature = None
        self._drag_session_active = False
        self._drag_snap_screen = None
        self._drag_snap_miss_count = 0
        self._snap_enter_threshold = 16
        self._snap_hold_threshold = 24
        self._screen_switch_margin = 28
        self._snap_hide_miss_limit = 2

        self.apply_theme()
        self.init_ui()
        self.setup_timer()

    def apply_theme(self):
        """Load the shared application stylesheet."""
        css_path = os.path.join(self.assets_dir, "styles.css")
        if not os.path.exists(css_path):
            self.logger.warning("Stylesheet not found: %s", css_path)
            return

        try:
            with open(css_path, encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except Exception as exc:
            self.logger.error("Failed to load stylesheet: %s", exc)

    def init_ui(self):
        """Build frameless layout — window controls integrated into top status bar."""
        self.setWindowTitle("金蝶数据同步工具 v2.0")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.resize(1460, 820)
        self.setMinimumSize(1024, 768)
        app_icon = os.path.join(self.assets_dir, "icons", "dashboard.svg")
        if os.path.exists(app_icon):
            self.setWindowIcon(QIcon(app_icon))

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        body = QWidget()
        body.setObjectName("desktop_body")
        root_layout.addWidget(body, 1)

        main_layout = QHBoxLayout(body)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setObjectName("app_splitter")
        self.main_splitter.setChildrenCollapsible(True)
        self.main_splitter.setHandleWidth(1)
        main_layout.addWidget(self.main_splitter)

        self.create_sidebar(self.main_splitter)
        self.create_main_content(self.main_splitter)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([self.sidebar_expanded_width, 1200])

        self.setup_menu_bar()
        self.setup_status_bar()
        self.setup_shortcuts()
        # native title bar — no custom titlebar state update needed
        self._apply_responsive_shell_layout()

        self.switch_to_page("dashboard")
        QTimer.singleShot(100, self.refresh_dashboard)

    def create_sidebar(self, layout):
        """侧边栏：品牌区 + 图标菜单 + 底部版权。"""
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setProperty("ui", "win11-nav-panel")
        sidebar.setMinimumWidth(self.sidebar_expanded_width)
        sidebar.setMaximumWidth(self.sidebar_expanded_width)
        self.sidebar = sidebar

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # ── 顶部品牌区（云朵 logo + 名称 + 版本）──
        brand = QWidget()
        brand.setObjectName("sidebar_brand")
        brand.setFixedHeight(88)
        self.sidebar_brand = brand
        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(24, 16, 16, 16)
        brand_layout.setSpacing(12)

        self.sidebar_logo = QLabel()
        self.sidebar_logo.setFixedSize(48, 48)
        self.sidebar_logo.setPixmap(_make_cloud_logo(48, ColorTokens.ACCENT_700))
        brand_layout.addWidget(self.sidebar_logo)

        text_col = QVBoxLayout()
        text_col.setSpacing(0)
        app_name = QLabel("金蝶数据同步工具")
        app_name.setObjectName("sidebar_app_name")
        text_col.addWidget(app_name)
        ver = QLabel("v1.2.0")
        ver.setObjectName("sidebar_ver")
        text_col.addWidget(ver)
        brand_layout.addLayout(text_col, 1)
        sidebar_layout.addWidget(brand)

        # ── 导航菜单（图标 + 文案）──
        nav_container = QWidget()
        nav_container.setObjectName("sidebar_nav_container")
        self.sidebar_nav_container = nav_container
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(18, 20, 18, 8)
        nav_layout.setSpacing(9)

        self.nav_buttons: dict[str, QPushButton] = {}
        for page_id in self.page_order:
            title, _ = self.page_meta.get(page_id, (page_id, ""))
            btn = QPushButton(title)
            btn.setObjectName(f"sidebar_nav_{page_id}")
            btn.setProperty("class", "sidebar-nav-btn")
            btn.setCheckable(True)
            btn.setFixedHeight(48)
            icon_file = SIDEBAR_NAV_ICON_FILES.get(page_id)
            icon_path = os.path.join(self.assets_dir, icon_file) if icon_file else ""
            if icon_file and os.path.exists(icon_path):
                btn.setProperty("icon-source", icon_file)
                icon = QIcon(icon_path)
            else:
                icon = _make_nav_icon(page_id, 18, ColorTokens.NEUTRAL_500)
            btn.setIcon(icon)
            btn.setIconSize(QSize(20, 20))
            btn.clicked.connect(lambda _checked=False, pid=page_id: self.switch_to_page(pid))
            nav_layout.addWidget(btn)
            self.nav_buttons[page_id] = btn

        nav_layout.addStretch(1)
        sidebar_layout.addWidget(nav_container, 1)

        # ── 底部版权区 ──
        footer = QWidget()
        footer.setObjectName("sidebar_footer")
        footer.setFixedHeight(40)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 0, 16, 0)
        footer_layout.setSpacing(0)

        copyright_label = QLabel("© 2024 Kingdee")
        copyright_label.setObjectName("sidebar_copyright")
        footer_layout.addWidget(copyright_label)
        footer_layout.addStretch(1)
        self.sidebar_collapse_btn = QPushButton("")
        self.sidebar_collapse_btn.setObjectName("sidebar_collapse_btn")
        self.sidebar_collapse_btn.setProperty("icon-source", "menu_fold.svg")
        self.sidebar_collapse_btn.setIcon(QIcon(os.path.join(self.assets_dir, "icons", "menu_fold.svg")))
        self.sidebar_collapse_btn.setIconSize(QSize(16, 16))
        self.sidebar_collapse_btn.setFixedSize(24, 24)
        footer_layout.addWidget(self.sidebar_collapse_btn)
        sidebar_layout.addWidget(footer)

        layout.addWidget(sidebar)

        # 保持 nav_item_map 兼容现有测试
        self.nav_item_map = dict.fromkeys(self.page_order)

        # 标记首项选中
        if self.nav_buttons:
            self.nav_buttons["dashboard"].setChecked(True)

    def _create_nav_toolstrip(self):
        frame = QFrame()
        frame.setObjectName("sidebar_toolstrip")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        tool_pages = ["dashboard", "history", "task_management", "forms", "schedule", "settings"]
        self.nav_tool_buttons = {}
        for page_id in tool_pages:
            btn = QToolButton()
            btn.setProperty("class", "nav-tool-btn")
            btn.setCheckable(True)
            btn.setAutoRaise(False)
            btn.setFixedSize(30, 30)
            btn.setToolButtonStyle(Qt.ToolButtonIconOnly)

            icon_name = {
                "dashboard": "dashboard.svg",
                "history": "history.svg",
                "task_management": "dashboard.svg",
                "forms": "forms.svg",
                "schedule": "schedule.svg",
                "settings": "settings.svg",
            }.get(page_id)
            if icon_name:
                icon_path = os.path.join(self.assets_dir, "icons", icon_name)
                if os.path.exists(icon_path):
                    btn.setIcon(QIcon(icon_path))
                    btn.setIconSize(QSize(16, 16))
            btn.setToolTip(self.page_meta.get(page_id, (page_id, ""))[0])
            btn.clicked.connect(lambda _checked=False, pid=page_id: self.switch_to_page(pid))
            self.nav_tool_buttons[page_id] = btn
            layout.addWidget(btn)

        layout.addStretch()
        return frame

    def _create_nav_tree(self):
        self.nav_tree = QTreeWidget()
        self.nav_tree.setObjectName("nav-tree")
        self.nav_tree.setHeaderHidden(True)
        self.nav_tree.setFrameShape(QFrame.NoFrame)
        self.nav_tree.setRootIsDecorated(False)
        self.nav_tree.setExpandsOnDoubleClick(False)
        self.nav_tree.setIndentation(0)
        self.nav_tree.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nav_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nav_tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.nav_item_map = {}
        for page_id in self.page_order:
            title, _subtitle = self.page_meta.get(page_id, (page_id, ""))
            item = QTreeWidgetItem([title])
            item.setData(0, Qt.UserRole, page_id)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.nav_tree.addTopLevelItem(item)
            self.nav_item_map[page_id] = item

        self.nav_tree.currentItemChanged.connect(self._on_nav_tree_item_changed)
        return self.nav_tree

    def _on_nav_tree_item_changed(self, current, previous):
        if current is None:
            return

        page_id = current.data(0, Qt.UserRole)
        if page_id is None:
            return

        self._activate_page(page_id, sync_nav=False)

    def _set_toolstrip_active(self, page_id):
        for pid, btn in self.nav_tool_buttons.items():
            btn.blockSignals(True)
            btn.setChecked(pid == page_id)
            btn.blockSignals(False)

    def _set_nav_tree_current(self, page_id):
        if self.nav_tree is None:
            return
        item = self.nav_item_map.get(page_id)
        if item is None:
            return
        self.nav_tree.blockSignals(True)
        self.nav_tree.setCurrentItem(item)
        self.nav_tree.scrollToItem(item)
        self.nav_tree.blockSignals(False)

    def _activate_page(self, page_id, sync_nav=True):
        target_index = self.page_index_map.get(page_id)
        if target_index is None:
            return

        self.current_page_id = page_id
        self.stacked_widget.setCurrentIndex(target_index)
        self._set_toolstrip_active(page_id)
        # 更新侧边栏按钮选中态
        for pid, btn in self.nav_buttons.items():
            btn.blockSignals(True)
            btn.setChecked(pid == page_id)
            btn.blockSignals(False)
        self._update_topbar_page(page_id)
        self._refresh_top_status_bar()

        page = self.stacked_widget.currentWidget()
        if hasattr(page, "load_config"):
            page.load_config()
        if hasattr(page, "load_settings"):
            page.load_settings()
        if hasattr(page, "load_history") and page_id == "history":
            page.load_history(1)

    def _create_status_row(self, parent_layout, text, callback):
        row = QWidget()
        row.setProperty("class", "status-row")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        icon_label = QLabel()
        icon_label.setFixedSize(16, 16)

        text_label = ClickableLabel(text)
        text_label.setObjectName("status_text")
        text_label.clicked.connect(callback)

        tag_label = QLabel("未连接")
        tag_label.setProperty("class", "status-pill-offline")

        row_layout.addWidget(icon_label)
        row_layout.addWidget(text_label)
        row_layout.addStretch()
        row_layout.addWidget(tag_label)
        parent_layout.addWidget(row)
        return icon_label, text_label, tag_label

    def create_main_content(self, layout):
        """Create the stacked page container and top status area."""
        content_shell = QWidget()
        content_shell.setObjectName("main_content_shell")
        content_shell.setProperty("ui", "win11-shell")
        shell_layout = QVBoxLayout(content_shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        shell_layout.addWidget(self._create_top_status_bar())

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setObjectName("main-content")
        shell_layout.addWidget(self.stacked_widget, 1)

        self.pages = {
            "dashboard": DashboardPage(self),
            "history": HistoryPage(self),
            "task_management": TaskManagementPage(self),
            "data_source": DataSourcePage(self),
            "forms": FormConfigPage(self),
            "schedule": SchedulePage(self),
            "diagnostics": DiagnosticsPage(self),
            "log_center": LogCenterPage(self),
            "sync": SyncPage(self),
            "settings": SettingsPage(self),
        }

        for page_name in self.page_order:
            self.stacked_widget.addWidget(self.pages[page_name])

        layout.addWidget(content_shell)

    def _create_top_status_bar(self):
        """顶栏（56px）：连接信息 + 设置/帮助 + 用户 + 窗口控制（整栏可拖拽）"""
        bar = QFrame()
        bar.setObjectName("top_status_bar")
        bar.setProperty("ui", "win11-command-bar")
        bar.setFixedHeight(80)
        root_layout = QHBoxLayout(bar)
        root_layout.setContentsMargins(28, 0, 24, 0)
        root_layout.setSpacing(0)

        # ═══════ 左侧连接信息区 ═══════
        info_group = QHBoxLayout()
        info_group.setSpacing(48)

        # 组1：连接状态
        conn_group = QHBoxLayout()
        conn_group.setSpacing(6)
        dot = QLabel("●")
        dot.setObjectName("topbar_status_dot")
        conn_group.addWidget(dot)
        conn_label = QLabel("连接状态：")
        conn_val = QLabel("已连接")
        conn_val.setObjectName("topbar_value")
        self.topbar_status_dot = dot
        self.topbar_conn_value = conn_val
        conn_group.addWidget(conn_label)
        conn_group.addWidget(conn_val)
        info_group.addLayout(conn_group)

        # 组2：金蝶云地址
        kd_group = QHBoxLayout()
        kd_group.setSpacing(6)
        kd_label = QLabel("金蝶云星空：")
        kd_val = QLabel("https://api.yunxingkong.com")
        kd_val.setObjectName("topbar_value")
        self.topbar_kingdee_value = kd_val
        kd_group.addWidget(kd_label)
        kd_group.addWidget(kd_val)
        info_group.addLayout(kd_group)

        # 组3：数据库地址
        db_group = QHBoxLayout()
        db_group.setSpacing(6)
        db_label = QLabel("数据库：")
        db_val = QLabel("SQL Server (192.168.1.50)")
        db_val.setObjectName("topbar_value")
        self.topbar_database_value = db_val
        db_group.addWidget(db_label)
        db_group.addWidget(db_val)
        info_group.addLayout(db_group)

        root_layout.addLayout(info_group)
        root_layout.addStretch(1)

        # ═══════ 右侧功能区 ═══════
        # ── 功能组：设置 + 帮助 ──
        action_group = QHBoxLayout()
        action_group.setSpacing(10)

        self.btn_setting = QPushButton("设置")
        self.btn_setting.setFixedHeight(36)
        self.btn_setting.setObjectName("topbar_action_text_btn")
        self.btn_setting.setIcon(QIcon(os.path.join(self.assets_dir, "icons", "topbar_settings.svg")))
        self.btn_setting.setIconSize(QSize(18, 18))
        self.btn_setting.clicked.connect(lambda: self.switch_to_page("settings"))
        action_group.addWidget(self.btn_setting)

        self.btn_help = QPushButton("帮助")
        self.btn_help.setFixedHeight(36)
        self.btn_help.setObjectName("topbar_action_text_btn")
        self.btn_help.setIcon(QIcon(os.path.join(self.assets_dir, "icons", "topbar_help.svg")))
        self.btn_help.setIconSize(QSize(18, 18))
        self.btn_help.clicked.connect(lambda: UiFeedback.info(self, "帮助", "金蝶数据同步工具 v2.0"))
        action_group.addWidget(self.btn_help)
        root_layout.addLayout(action_group)

        # ── 分隔间距20px + 窗口控制 ──
        root_layout.addSpacing(20)

        win_group = QHBoxLayout()
        win_group.setSpacing(0)

        for txt, fn in [("—", self.showMinimized), ("□", self._toggle_max_restore), ("×", self.close)]:
            btn = QPushButton(txt)
            btn.setFixedSize(44, 40)
            btn.setObjectName("topbar_window_close_btn" if txt == "×" else "topbar_window_btn")
            btn.clicked.connect(fn)
            win_group.addWidget(btn)

        root_layout.addLayout(win_group)

        # 整栏拖拽
        bar.mousePressEvent = lambda e: (
            setattr(self, '_drag_pos', e.globalPosition().toPoint() - self.frameGeometry().topLeft())
            if e.button() == Qt.LeftButton else None
        )
        bar.mouseMoveEvent = lambda e: (
            self.move(e.globalPosition().toPoint() - self._drag_pos)
            if e.buttons() == Qt.LeftButton else None
        )

        # 隐藏 topbar_title 但保留属性供测试读
        self.topbar_title = QLabel("概览")
        self.topbar_title.setObjectName("topbar_title")
        self.topbar_title.setVisible(False)
        self.topbar_subtitle = QLabel("")
        self.topbar_subtitle.setObjectName("topbar_subtitle")
        self.topbar_subtitle.setVisible(False)

        self._refresh_top_status_bar()
        return bar

    def _create_top_action_button(self, text, callback, accent=False):
        button = QPushButton(text)
        button.setObjectName("topbar_action_btn")
        button.setProperty("ui", "win11-command-button")
        button.setProperty("accent", accent)
        button.setFixedHeight(34)
        base_width = 78 if accent else 84
        # Ensure localized (e.g. zh-CN) labels do not get clipped while keeping old sizing as a floor.
        text_width = button.fontMetrics().horizontalAdvance(text)
        button.setMinimumWidth(max(base_width, text_width + 32))
        button.clicked.connect(callback)
        return button

    def focus_topbar_search(self):
        pass

    def _apply_responsive_shell_layout(self):
        compact = self.width() <= 1024
        self.sidebar_compact = compact

        if self.sidebar is not None:
            self.sidebar.setProperty("compact", compact)
            sidebar_width = self.sidebar_compact_width if compact else self.sidebar_expanded_width
            self.sidebar.setMinimumWidth(sidebar_width)
            self.sidebar.setMaximumWidth(sidebar_width)
            sidebar_style = self.sidebar.style()
            if sidebar_style is not None:
                sidebar_style.unpolish(self.sidebar)
                sidebar_style.polish(self.sidebar)

        if self.sidebar_logo_subtitle is not None:
            self.sidebar_logo_subtitle.setVisible(not compact)
        if self.sidebar_status_card is not None:
            self.sidebar_status_card.setVisible(not compact)

        if self.main_splitter is not None:
            sidebar_width = self.sidebar_compact_width if compact else self.sidebar_expanded_width
            content_width = max(960, self.width() - sidebar_width)
            self.main_splitter.setSizes([sidebar_width, content_width])

    def switch_to_page(self, page_id):
        self._activate_page(page_id, sync_nav=True)

    def handle_topbar_search(self):
        keyword = self.topbar_search.text().strip().lower() if self.topbar_search else ""
        if not keyword:
            return

        for page_id in self.page_order:
            title, subtitle = self.page_meta.get(page_id, ("", ""))
            if keyword in page_id.lower() or keyword in title.lower() or keyword in subtitle.lower():
                self.switch_to_page(page_id)
                return

        UiFeedback.info(self, "未找到结果", f"未匹配到关键字：{keyword}")

    def _set_topbar_chip(self, widget, text, tone):
        widget.setText(text)
        widget.setProperty("class", f"topbar-chip-{tone}")
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _update_topbar_page(self, page_id):
        if page_id not in self.page_index_map:
            page_id = "dashboard"
        title, _subtitle = self.page_meta.get(page_id, self.page_meta["dashboard"])
        self.topbar_title.setText(title)
        self._refresh_desktop_status()

    def _topbar_kingdee_display(self) -> str:
        try:
            cfg = config_manager.get_kingdee_config()
        except Exception as exc:
            self.logger.warning("Failed to read Kingdee config for topbar: %s", exc)
            return "未配置"

        raw_url = str(cfg.get("query_url") or cfg.get("login_url") or cfg.get("api_url") or "").strip()
        if not raw_url:
            return "未配置"

        parsed = urlparse(raw_url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
        return raw_url.split("/", 1)[0] or "未配置"

    def _topbar_database_display(self) -> str:
        try:
            db_config = config_manager.get_db_config()
        except Exception as exc:
            self.logger.warning("Failed to read database config for topbar: %s", exc)
            return "未配置"

        db_type = str(db_config.get("type", "sqlserver")).strip().lower()
        display_type = "SQL Server" if db_type == "sqlserver" else "MySQL" if db_type == "mysql" else db_type.upper()
        target_cfg = db_config.get(db_type, {}) if isinstance(db_config, dict) else {}
        host = str(target_cfg.get("host") or "").strip()
        return f"{display_type} ({host})" if host else f"{display_type} (未配置)"

    def _refresh_top_status_bar(self):
        """Update top status bar from readonly connection state and config."""
        if hasattr(self, "topbar_conn_value"):
            if self.kd_connected and self.db_connected:
                self.topbar_conn_value.setText("已连接")
                self.topbar_status_dot.setProperty("status", "online")
            elif self.kd_connected or self.db_connected:
                self.topbar_conn_value.setText("部分连接")
                self.topbar_status_dot.setProperty("status", "partial")
            else:
                self.topbar_conn_value.setText("未连接")
                self.topbar_status_dot.setProperty("status", "offline")
            self.topbar_status_dot.style().unpolish(self.topbar_status_dot)
            self.topbar_status_dot.style().polish(self.topbar_status_dot)

        if hasattr(self, "topbar_kingdee_value"):
            self.topbar_kingdee_value.setText(self._topbar_kingdee_display())
            self.topbar_kingdee_value.setToolTip(self.topbar_kingdee_value.text())
        if hasattr(self, "topbar_database_value"):
            self.topbar_database_value.setText(self._topbar_database_display())
            self.topbar_database_value.setToolTip(self.topbar_database_value.text())
        self._refresh_desktop_status()

    def _update_status_display(self, is_kingdee, connected, message=None):
        """Update sidebar status rows and top badges."""
        if is_kingdee:
            icon_label = self.kd_status_icon
            text_label = self.kd_status_text
            tag_label = self.kd_status_tag
            prefix = "金蝶 API"
            self.kd_connected = connected
        else:
            icon_label = self.db_status_icon
            text_label = self.db_status_text
            tag_label = self.db_status_tag
            prefix = "数据库"
            self.db_connected = connected

        icon_name = "status_ok.svg" if connected else "status_err.svg"
        icon_path = os.path.join(self.assets_dir, "icons", icon_name)
        if os.path.exists(icon_path):
            icon_label.setPixmap(QIcon(icon_path).pixmap(16, 16))

        text_label.setText(message or f"{prefix}: {'已连接' if connected else '未连接'}")
        tag_label.setText("已连接" if connected else "未连接")
        tag_label.setProperty("class", "status-pill-online" if connected else "status-pill-offline")
        tag_label.style().unpolish(tag_label)
        tag_label.style().polish(tag_label)
        self._refresh_top_status_bar()

    def show_status_detail(self, target):
        """Show connection detail for Kingdee or database."""
        if target == "kingdee":
            config = config_manager.get_kingdee_config()
            title = "金蝶连接详情"
            message = (
                f"登录地址: {config.get('login_url', '未配置')}\n"
                f"查询地址: {config.get('query_url', '未配置')}\n"
                f"账套 ID: {config.get('acct_id', '未配置')}\n\n"
                f"状态: {self.kd_status_text.text()}"
            )
        else:
            db_config = config_manager.get_db_config()
            db_type = db_config.get("type", "mysql")
            target_cfg = db_config.get(db_type, {}) if isinstance(db_config, dict) else {}
            title = "数据库连接详情"
            message = (
                f"类型: {db_type}\n"
                f"主机: {target_cfg.get('host', '未配置')}\n"
                f"数据库: {target_cfg.get('database', '未配置')}\n\n"
                f"状态: {self.db_status_text.text()}"
            )

        UiFeedback.info(self, title, message)

    def switch_page(self, index):
        """Compatibility wrapper for legacy index-based callers."""
        if isinstance(index, int):
            if index < 0 or index >= len(self.page_order):
                return
            self.switch_to_page(self.page_order[index])
            return

        if isinstance(index, str):
            self.switch_to_page(index)

    def refresh_dashboard(self):
        page = self.pages.get("dashboard")
        if page is not None:
            page.refresh_dashboard()

    def load_recent_errors(self):
        page = self.pages.get("dashboard")
        if page is not None and hasattr(page, "_refresh_error_list"):
            page._refresh_error_list()

    def setup_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_scheduler_status)
        self.timer.start(5000)
        self._refresh_top_status_bar()

    def check_scheduler_status(self):
        self._refresh_top_status_bar()

    def setup_menu_bar(self):
        """Create hidden native-style menu bar and popup window menu."""
        menu_bar = self.menuBar()
        menu_bar.setObjectName("desktop_menu_bar")

        file_menu = menu_bar.addMenu("文件(&F)")
        refresh_action = QAction("刷新仪表盘", self)
        refresh_action.setShortcut(QKeySequence("Ctrl+R"))
        refresh_action.triggered.connect(self.refresh_dashboard)
        file_menu.addAction(refresh_action)

        focus_search_action = QAction("聚焦搜索", self)
        focus_search_action.setShortcut(QKeySequence("Ctrl+F"))
        focus_search_action.triggered.connect(self.focus_topbar_search)
        file_menu.addAction(focus_search_action)
        file_menu.addSeparator()

        exit_action = QAction("退出", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_menu = menu_bar.addMenu("视图(&V)")
        self.toggle_sidebar_action = QAction("显示侧边栏", self)
        self.toggle_sidebar_action.setCheckable(True)
        self.toggle_sidebar_action.setChecked(True)
        self.toggle_sidebar_action.toggled.connect(self._set_sidebar_visible)
        view_menu.addAction(self.toggle_sidebar_action)

        nav_menu = menu_bar.addMenu("导航(&N)")
        nav_entries = [
            ("概览", "dashboard", "Ctrl+1"),
            ("同步执行", "sync", "Ctrl+2"),
            ("同步历史", "history", "Ctrl+3"),
            ("任务管理", "task_management", "Ctrl+4"),
            ("数据源管理", "data_source", "Ctrl+5"),
            ("表单映射", "forms", "Ctrl+6"),
            ("调度管理", "schedule", "Ctrl+7"),
            ("异常诊断", "diagnostics", "Ctrl+8"),
            ("日志中心", "log_center", "Ctrl+9"),
            ("系统设置", "settings", "Ctrl+0"),
        ]
        for label, page_id, shortcut in nav_entries:
            action = QAction(label, self)
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(lambda checked=False, pid=page_id: self.switch_to_page(pid))
            nav_menu.addAction(action)

        help_menu = menu_bar.addMenu("帮助(&H)")
        about_action = QAction("关于", self)
        about_action.triggered.connect(
            lambda: UiFeedback.info(
                self,
                "关于",
                "金蝶数据同步工具 v2.0\n已统一为更轻量的桌面工作台风格，覆盖同步、调度、历史和系统设置等核心页面。",
            )
        )
        help_menu.addAction(about_action)

        self.window_menu_popup = QMenu(self)
        self.window_menu_popup.addMenu(file_menu)
        self.window_menu_popup.addMenu(view_menu)
        self.window_menu_popup.addMenu(nav_menu)
        self.window_menu_popup.addMenu(help_menu)
        menu_bar.setNativeMenuBar(False)
        menu_bar.setVisible(False)

    def setup_status_bar(self):
        """Create compact desktop status bar matching target design."""
        status = self.statusBar()
        status.setObjectName("desktop_status_bar")
        status.setSizeGripEnabled(False)
        status.setFixedHeight(28)

        state_row = QHBoxLayout()
        state_row.setContentsMargins(12, 0, 12, 0)
        state_row.setSpacing(6)

        dot = QLabel()
        dot.setObjectName("statusbar_dot")
        dot.setFixedSize(10, 10)
        dot.setAlignment(Qt.AlignCenter)
        dot_pm = QPixmap(8, 8)
        dot_pm.fill(Qt.transparent)
        dot_painter = QPainter(dot_pm)
        dot_painter.setRenderHint(QPainter.Antialiasing)
        dot_painter.setPen(Qt.NoPen)
        dot_painter.setBrush(QColor(ColorTokens.SUCCESS_GREEN))
        dot_painter.drawEllipse(0, 0, 8, 8)
        dot_painter.end()
        dot.setPixmap(dot_pm)
        state_row.addWidget(dot)

        self.statusbar_state = QLabel("数据同步服务运行中")
        self.statusbar_state.setObjectName("statusbar_state")
        sf = self.statusbar_state.font()
        sf.setPointSize(10)
        self.statusbar_state.setFont(sf)
        sp = self.statusbar_state.palette()
        sp.setColor(QPalette.WindowText, QColor(ColorTokens.NEUTRAL_500))
        self.statusbar_state.setPalette(sp)
        state_row.addWidget(self.statusbar_state)
        state_row.addStretch()

        self.statusbar_conn = QLabel("")
        self.statusbar_conn.setObjectName("statusbar_conn")
        state_row.addWidget(self.statusbar_conn)

        self.statusbar_clock = QLabel("上次同步：2024-05-14 10:15:32")
        self.statusbar_clock.setObjectName("statusbar_clock")
        cf = self.statusbar_clock.font()
        cf.setPointSize(10)
        self.statusbar_clock.setFont(cf)
        cp = self.statusbar_clock.palette()
        cp.setColor(QPalette.WindowText, QColor(ColorTokens.NEUTRAL_500))
        self.statusbar_clock.setPalette(cp)
        state_row.addWidget(self.statusbar_clock)

        wrapper = QWidget()
        wrapper.setLayout(state_row)
        wrapper.setFixedHeight(28)
        wrapper_p = wrapper.palette()
        wrapper_p.setColor(QPalette.Window, QColor(ColorTokens.SURFACE_BASE))
        wrapper.setAutoFillBackground(True)
        wrapper.setPalette(wrapper_p)

        status.addWidget(wrapper, 1)

    def setup_shortcuts(self):
        """Register application-wide keyboard shortcuts."""
        key_map = {
            "F5": self.refresh_dashboard,
            "Ctrl+F": self.focus_topbar_search,
            "Ctrl+1": lambda: self.switch_to_page("dashboard"),
            "Ctrl+2": lambda: self.switch_to_page("sync"),
            "Ctrl+3": lambda: self.switch_to_page("history"),
            "Ctrl+4": lambda: self.switch_to_page("task_management"),
            "Ctrl+5": lambda: self.switch_to_page("data_source"),
            "Ctrl+6": lambda: self.switch_to_page("forms"),
            "Ctrl+7": lambda: self.switch_to_page("schedule"),
            "Ctrl+8": lambda: self.switch_to_page("diagnostics"),
            "Ctrl+9": lambda: self.switch_to_page("log_center"),
            "Ctrl+0": lambda: self.switch_to_page("settings"),
        }

        for seq, callback in key_map.items():
            shortcut = QShortcut(QKeySequence(seq), self)
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)

    def _set_sidebar_visible(self, visible):
        if not self.main_splitter:
            return
        total = max(self.width(), 1000)
        if visible:
            self.main_splitter.setSizes([self.sidebar_expanded_width, max(740, total - self.sidebar_expanded_width)])
        else:
            self.main_splitter.setSizes([0, total])
        self._refresh_desktop_status()

    def _refresh_desktop_status(self):
        if not all(hasattr(self, attr) for attr in ("statusbar_state", "statusbar_conn", "statusbar_clock")):
            return
        self.statusbar_state.setText("数据同步服务运行中")
        self.statusbar_conn.setText("")
        self.statusbar_clock.setText("上次同步：2024-05-14 10:15:32")

    def _show_window_menu(self, global_pos):
        pass  # native title bar — no custom window menu

    def _minimize_window(self):
        self.showMinimized()

    def _toggle_max_restore(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _update_titlebar_state(self):
        pass  # native title bar handles maximize/restore

    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange:
            if self.isMaximized() or self.isMinimized():
                self._hide_snap_preview()
        super().changeEvent(event)

    def resizeEvent(self, event):
        self._apply_responsive_shell_layout()
        super().resizeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_windows_effects()

    def _apply_windows_effects(self):
        """Enable native Windows frame behaviors for the custom title bar."""
        if self._windows_effects_applied:
            return
        if not sys.platform.startswith("win"):
            return

        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            dwmapi = ctypes.windll.dwmapi
        except Exception:
            return

        try:
            # 1) Keep native resize/min/max styles for frameless window
            gwl_style = -16
            ws_thickframe = 0x00040000
            ws_minimizebox = 0x00020000
            ws_maximizebox = 0x00010000
            style = user32.GetWindowLongW(hwnd, gwl_style)
            desired = style | ws_thickframe | ws_minimizebox | ws_maximizebox
            if desired != style:
                user32.SetWindowLongW(hwnd, gwl_style, desired)
                swp_nosize = 0x0001
                swp_nomove = 0x0002
                swp_nozorder = 0x0004
                swp_noactivate = 0x0010
                swp_framechanged = 0x0020
                user32.SetWindowPos(
                    hwnd,
                    0,
                    0,
                    0,
                    0,
                    0,
                    swp_nosize | swp_nomove | swp_nozorder | swp_noactivate | swp_framechanged,
                )
        except Exception:
            pass

        try:
            # 2) Prefer rounded corners on Windows 11
            dwmwa_window_corner_preference = 33
            dwmwcp_round = 2
            corner_pref = ctypes.c_int(dwmwcp_round)
            dwmapi.DwmSetWindowAttribute(
                hwnd,
                dwmwa_window_corner_preference,
                ctypes.byref(corner_pref),
                ctypes.sizeof(corner_pref),
            )
        except Exception:
            pass

        try:
            # 3) Enable DWM non-client rendering policy
            dwmwa_ncrendering_policy = 2
            dwmncrp_enabled = 2
            policy = ctypes.c_int(dwmncrp_enabled)
            dwmapi.DwmSetWindowAttribute(
                hwnd,
                dwmwa_ncrendering_policy,
                ctypes.byref(policy),
                ctypes.sizeof(policy),
            )

            class MARGINS(ctypes.Structure):
                _fields_ = [
                    ("cxLeftWidth", ctypes.c_int),
                    ("cxRightWidth", ctypes.c_int),
                    ("cyTopHeight", ctypes.c_int),
                    ("cyBottomHeight", ctypes.c_int),
                ]

            margins = MARGINS(1, 1, 1, 1)
            dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))
        except Exception:
            pass

        self._windows_effects_applied = True

    def _begin_drag_session(self, global_pos):
        """Start tracking a drag gesture for snap preview handling."""
        self._drag_session_active = True
        self._drag_snap_screen = QApplication.screenAt(global_pos)
        if self._drag_snap_screen is None:
            self._drag_snap_screen = QApplication.primaryScreen()
        self._drag_snap_miss_count = 0
        self._hide_snap_preview()

    def _end_drag_session(self):
        """Reset drag-session state after moving the window."""
        self._drag_session_active = False
        self._drag_snap_screen = None
        self._drag_snap_miss_count = 0
        self._snap_target_signature = None

    def _resolve_snap_screen(self, global_pos):
        """Choose the snap target screen while dragging across monitors."""
        candidate = QApplication.screenAt(global_pos)
        if candidate is None:
            return self._drag_snap_screen or QApplication.primaryScreen()

        if not self._drag_session_active:
            return candidate

        if self._drag_snap_screen is None:
            self._drag_snap_screen = candidate
            return candidate

        if candidate == self._drag_snap_screen:
            return candidate

        sticky_area = self._drag_snap_screen.availableGeometry().adjusted(
            -self._screen_switch_margin,
            -self._screen_switch_margin,
            self._screen_switch_margin,
            self._screen_switch_margin,
        )
        if sticky_area.contains(global_pos):
            return self._drag_snap_screen

        self._drag_snap_screen = candidate
        return candidate

    def _detect_snap_region(self, area, global_pos, threshold):
        near_left = global_pos.x() <= area.left() + threshold
        near_right = global_pos.x() >= area.right() - threshold
        near_top = global_pos.y() <= area.top() + threshold
        near_bottom = global_pos.y() >= area.bottom() - threshold

        if near_top and near_left:
            return "top_left"
        if near_top and near_right:
            return "top_right"
        if near_bottom and near_left:
            return "bottom_left"
        if near_bottom and near_right:
            return "bottom_right"
        if near_left:
            return "left"
        if near_right:
            return "right"
        if near_top:
            return "top"
        return None

    def _target_from_region(self, area, region):
        half_w = area.width() // 2
        half_h = area.height() // 2

        if region == "top_left":
            return "rect", QRect(area.left(), area.top(), half_w, half_h)
        if region == "top_right":
            return "rect", QRect(area.left() + half_w, area.top(), area.width() - half_w, half_h)
        if region == "bottom_left":
            return "rect", QRect(area.left(), area.top() + half_h, half_w, area.height() - half_h)
        if region == "bottom_right":
            return "rect", QRect(area.left() + half_w, area.top() + half_h, area.width() - half_w, area.height() - half_h)
        if region == "left":
            return "rect", QRect(area.left(), area.top(), half_w, area.height())
        if region == "right":
            return "rect", QRect(area.left() + half_w, area.top(), area.width() - half_w, area.height())
        if region == "top":
            return "maximized", area
        return None, QRect()

    def _get_snap_target(self, global_pos):
        """Resolve the current Windows snap target for the given cursor position."""
        if not sys.platform.startswith("win"):
            return None, QRect(), None

        screen = self._resolve_snap_screen(global_pos)
        if screen is None:
            return None, QRect(), None

        area = screen.availableGeometry()
        if area.isNull():
            return None, QRect(), None

        threshold = self._snap_enter_threshold
        if self._drag_session_active and self._snap_target_mode is not None and screen == self._drag_snap_screen:
            threshold = self._snap_hold_threshold

        region = self._detect_snap_region(area, global_pos, threshold)
        if region is None:
            return None, QRect(), None

        mode, rect = self._target_from_region(area, region)
        return mode, rect, region

    def _update_snap_preview(self, global_pos):
        """Show or clear the snap preview overlay based on cursor location."""
        mode, target, region = self._get_snap_target(global_pos)
        if mode is None or target.isNull():
            if self._snap_target_mode is None:
                return
            self._drag_snap_miss_count += 1
            if self._drag_snap_miss_count < self._snap_hide_miss_limit:
                return
            self._hide_snap_preview()
            return

        self._drag_snap_miss_count = 0

        if self._snap_overlay is None:
            self._snap_overlay = SnapPreviewOverlay()

        screen_id = id(self._drag_snap_screen) if self._drag_snap_screen is not None else 0
        signature = (screen_id, mode, target.x(), target.y(), target.width(), target.height())
        if signature == self._snap_target_signature and self._snap_overlay.isVisible():
            return

        self._snap_target_signature = signature
        self._snap_target_mode = mode
        self._snap_target_rect = QRect(target)
        self._snap_target_region = region
        self._snap_overlay.show_target(target)

    def _hide_snap_preview(self):
        self._snap_target_mode = None
        self._snap_target_rect = QRect()
        self._snap_target_region = None
        self._snap_target_signature = None
        self._drag_snap_miss_count = 0
        if self._snap_overlay is not None and self._snap_overlay.isVisible():
            self._snap_overlay.hide()

    def _apply_snap_target(self):
        """Apply the pending snap target when the drag gesture ends."""
        if self._snap_target_mode is None or self._snap_target_rect.isNull():
            self._hide_snap_preview()
            return

        target_mode = self._snap_target_mode
        target_rect = QRect(self._snap_target_rect)
        self._hide_snap_preview()

        if target_mode == "maximized":
            self.showMaximized()
            return

        if self.isMaximized():
            self.showNormal()

        self.setGeometry(target_rect)
        self.raise_()
        self.activateWindow()

    def nativeEvent(self, event_type, message):
        """Handle Windows hit-testing so the frameless window can resize."""
        if not sys.platform.startswith("win"):
            return super().nativeEvent(event_type, message)
        if wintypes is None:
            return super().nativeEvent(event_type, message)

        if event_type != "windows_generic_MSG":
            return super().nativeEvent(event_type, message)

        msg = wintypes.MSG.from_address(int(message))
        wm_nchittest = 0x0084
        if msg.message != wm_nchittest:
            return super().nativeEvent(event_type, message)

        if self.isMaximized():
            return False, 0

        # Extract mouse position from lParam (signed short)
        x = ctypes.c_short(msg.lParam & 0xFFFF).value
        y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
        rect = self.frameGeometry()

        left = x <= rect.left() + self._resize_border_px
        right = x >= rect.right() - self._resize_border_px
        top = y <= rect.top() + self._resize_border_px
        bottom = y >= rect.bottom() - self._resize_border_px

        # Win32 HT codes
        htleft = 10
        htright = 11
        httop = 12
        httopleft = 13
        httopright = 14
        htbottom = 15
        htbottomleft = 16
        htbottomright = 17

        if top and left:
            return True, httopleft
        if top and right:
            return True, httopright
        if bottom and left:
            return True, htbottomleft
        if bottom and right:
            return True, htbottomright
        if left:
            return True, htleft
        if right:
            return True, htright
        if top:
            return True, httop
        if bottom:
            return True, htbottom

        return False, 0


class SnapPreviewOverlay(QWidget):
    """Lightweight overlay that previews the pending snap rectangle."""

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.BypassWindowManagerHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._target = QRect()

    def show_target(self, rect):
        if rect.isNull():
            self.hide()
            return
        inset = 8
        target_rect = QRect(rect.adjusted(inset, inset, -inset, -inset))
        if target_rect == self._target and self.isVisible():
            return

        self._target = target_rect
        if self.geometry() != self._target:
            self.setGeometry(self._target)
        if not self.isVisible():
            self.show()
        self.raise_()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        body_rect = self.rect().adjusted(1, 1, -1, -1)

        fill = QColor(37, 99, 235, 58)
        border = QColor(37, 99, 235, 210)
        painter.setBrush(QBrush(fill))
        painter.setPen(QPen(border, 2))
        painter.drawRoundedRect(body_rect, 12, 12)


class DesktopTitleBar(QFrame):
    """Custom title bar with menu, drag, and window controls."""

    menu_requested = Signal(QPoint)
    minimize_requested = Signal()
    maximize_restore_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("desktop_title_bar")
        self.setProperty("ui", "win11-title-bar")
        self.setFixedHeight(48)
        self._dragging = False
        self._drag_offset = QPoint()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(8)

        self.btn_close = QPushButton("")
        self.btn_close.setObjectName("titlebar_close_btn")
        self.btn_close.setProperty("ui", "win11-caption-close")
        self.btn_close.setText("✕")
        self.btn_close.setToolTip("关闭")
        self.btn_close.setFixedSize(42, 30)
        self.btn_close.clicked.connect(self.close_requested.emit)

        self.btn_min = QPushButton("")
        self.btn_min.setObjectName("titlebar_min_btn")
        self.btn_min.setProperty("ui", "win11-caption-minimize")
        self.btn_min.setText("—")
        self.btn_min.setToolTip("最小化")
        self.btn_min.setFixedSize(42, 30)
        self.btn_min.clicked.connect(self.minimize_requested.emit)

        self.btn_max = QPushButton("")
        self.btn_max.setObjectName("titlebar_max_btn")
        self.btn_max.setProperty("ui", "win11-caption-maximize")
        self.btn_max.setText("□")
        self.btn_max.setToolTip("最大化")
        self.btn_max.setFixedSize(42, 30)
        self.btn_max.clicked.connect(self.maximize_restore_requested.emit)

        self.icon_label = QLabel()
        self.icon_label.setObjectName("titlebar_icon")
        self.icon_label.setFixedSize(18, 18)

        self.title_label = QLabel("金蝶数据同步工具")
        self.title_label.setObjectName("titlebar_text")
        self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.menu_btn = QPushButton("窗口")
        self.menu_btn.setObjectName("titlebar_menu_btn")
        self.menu_btn.setProperty("ui", "win11-shell-button")
        self.menu_btn.setFixedHeight(28)
        self.menu_btn.setFixedWidth(76)
        self.menu_btn.clicked.connect(self._request_menu)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)
        layout.addStretch()
        layout.addWidget(self.menu_btn)
        layout.addSpacing(10)
        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_max)
        layout.addWidget(self.btn_close)

    def set_title(self, title):
        self.title_label.setText(title)

    def set_icon(self, icon):
        self.icon_label.setPixmap(icon.pixmap(18, 18))

    def set_maximized(self, maximized):
        self.btn_max.setProperty("maximized", maximized)
        style = self.btn_max.style()
        if style is not None:
            style.unpolish(self.btn_max)
            style.polish(self.btn_max)

    def _request_menu(self):
        pos = self.menu_btn.mapToGlobal(QPoint(0, self.menu_btn.height() + 2))
        self.menu_requested.emit(pos)

    def _is_button_region(self, point):
        widget = self.childAt(point)
        return isinstance(widget, QPushButton)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self._is_button_region(event.position().toPoint()):
            self._dragging = True
            window = self.window()
            global_pos = event.globalPosition().toPoint()
            if hasattr(window, "_begin_drag_session"):
                window._begin_drag_session(global_pos)
            elif hasattr(window, "_hide_snap_preview"):
                window._hide_snap_preview()
            self._drag_offset = global_pos - window.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() & Qt.LeftButton:
            window = self.window()
            global_pos = event.globalPosition().toPoint()
            if window.isMaximized():
                ratio = 0.5
                if self.width() > 0:
                    ratio = max(0.1, min(0.9, event.position().x() / self.width()))
                window.showNormal()
                normal_x = global_pos.x() - int(window.width() * ratio)
                normal_y = global_pos.y() - 12
                window.move(normal_x, normal_y)
                self._drag_offset = global_pos - window.frameGeometry().topLeft()
            window.move(global_pos - self._drag_offset)
            if hasattr(window, "_update_snap_preview"):
                window._update_snap_preview(global_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        window = self.window()
        if self._dragging and hasattr(window, "_apply_snap_target"):
            window._apply_snap_target()
        self._dragging = False
        if hasattr(window, "_end_drag_session"):
            window._end_drag_session()
        elif hasattr(window, "_hide_snap_preview"):
            window._hide_snap_preview()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and not self._is_button_region(event.position().toPoint()):
            window = self.window()
            if hasattr(window, "_end_drag_session"):
                window._end_drag_session()
            if hasattr(window, "_hide_snap_preview"):
                window._hide_snap_preview()
            self.maximize_restore_requested.emit()
        super().mouseDoubleClickEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = KingdeeSyncGUI()
    window.show()
    sys.exit(app.exec())











