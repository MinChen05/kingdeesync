"""Desktop GUI shell for the Kingdee sync tool."""

import logging
import os
import sys
import ctypes
from datetime import datetime
from typing import Any

wintypes: Any
try:
    from ctypes import wintypes as ctypes_wintypes
except Exception:  # pragma: no cover
    wintypes = None
else:
    wintypes = ctypes_wintypes

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QIcon, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPushButton,
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
from src.gui.design_tokens import ColorTokens
from src.gui.feedback import UiFeedback
from src.gui.pages.dashboard_page import DashboardPage
from src.gui.pages.forms_page import FormConfigPage
from src.gui.pages.history_page import HistoryPage
from src.gui.pages.schedule_page import SchedulePage
from src.gui.pages.settings_page import SettingsPage
from src.gui.pages.sync_page import SyncPage
from src.gui.ui_text import ShellText


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
        self.title_bar = None
        self.main_splitter = None
        self.sidebar = None
        self.sidebar_logo_subtitle = None
        self.sidebar_section_title = None
        self.sidebar_status_card = None
        self.sidebar_compact = False
        self.sidebar_expanded_width = 256
        self.sidebar_compact_width = 96
        self.shortcuts = []
        self.pages = {}
        self.nav_tree = None
        self.nav_item_map = {}
        self.nav_tool_buttons = {}
        self.topbar_action_buttons = []
        self.current_page_id = "dashboard"
        self.page_order = ["dashboard", "sync", "forms", "schedule", "history", "settings"]
        self.page_index_map = {page_id: idx for idx, page_id in enumerate(self.page_order)}
        self.page_meta = {
            "dashboard": ("运营总览", "查看核心运行指标、连接状态与任务概览"),
            "sync": ("同步执行", "执行单次同步任务并查看运行反馈"),
            "forms": ("表单配置", "维护同步表单映射与字段配置"),
            "schedule": ("调度管理", "管理自动调度任务与执行状态"),
            "history": ("历史记录", "查看同步任务历史、筛选与追踪问题"),
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
            with open(css_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except Exception as exc:
            self.logger.error("Failed to load stylesheet: %s", exc)

    def init_ui(self):
        """Build the frameless desktop layout and page shell."""
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

        self.title_bar = DesktopTitleBar(self)
        self.title_bar.set_title(self.windowTitle())
        if os.path.exists(app_icon):
            self.title_bar.set_icon(QIcon(app_icon))
        self.title_bar.menu_requested.connect(self._show_window_menu)
        self.title_bar.minimize_requested.connect(self._minimize_window)
        self.title_bar.maximize_restore_requested.connect(self._toggle_max_restore)
        self.title_bar.close_requested.connect(self.close)
        root_layout.addWidget(self.title_bar)

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
        self.main_splitter.setSizes([256, 1200])

        self.setup_menu_bar()
        self.setup_status_bar()
        self.setup_shortcuts()
        self._update_titlebar_state()
        self._apply_responsive_shell_layout()

        self.switch_to_page("dashboard")
        QTimer.singleShot(100, self.refresh_dashboard)

    def create_sidebar(self, layout):
        """Create the left navigation rail and connection summary."""
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setProperty("ui", "win11-nav-panel")
        sidebar.setMinimumWidth(0)
        sidebar.setMaximumWidth(360)
        self.sidebar = sidebar

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 16, 16, 16)
        sidebar_layout.setSpacing(16)

        sidebar_header = QFrame()
        sidebar_header.setObjectName("sidebar_header")
        header_layout = QVBoxLayout(sidebar_header)
        header_layout.setContentsMargins(16, 16, 16, 16)
        header_layout.setSpacing(4)

        logo_label = QLabel("金蝶数据同步")
        logo_label.setObjectName("app-logo")
        logo_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header_layout.addWidget(logo_label)

        logo_subtitle = QLabel("数据运营协同后台")
        logo_subtitle.setObjectName("app-subtitle")
        header_layout.addWidget(logo_subtitle)
        self.sidebar_logo_subtitle = logo_subtitle
        sidebar_layout.addWidget(sidebar_header)

        nav_title = QLabel("功能导航")
        nav_title.setObjectName("sidebar_section_title")
        self.sidebar_section_title = nav_title
        sidebar_layout.addWidget(nav_title)

        sidebar_layout.addWidget(self._create_nav_tree(), 1)

        status_frame = QFrame()
        status_frame.setObjectName("sidebar_bottom")
        status_layout = QVBoxLayout(status_frame)
        status_layout.setContentsMargins(0, 0, 0, 0)

        status_card = QFrame()
        status_card.setObjectName("status_card")
        status_card.setProperty("ui", "win11-sidebar-status")
        self.sidebar_status_card = status_card
        card_layout = QVBoxLayout(status_card)
        card_layout.setContentsMargins(14, 14, 14, 14)
        card_layout.setSpacing(10)

        status_title = QLabel("连接状态")
        status_title.setObjectName("sidebar_status_title")
        status_hint = QLabel("点击状态文本可查看连接详情")
        status_hint.setObjectName("sidebar_status_hint")
        card_layout.addWidget(status_title)
        card_layout.addWidget(status_hint)

        self.kd_status_icon, self.kd_status_text, self.kd_status_tag = self._create_status_row(
            card_layout, "金蝶 API: 未连接", lambda: self.show_status_detail("kingdee")
        )
        self.db_status_icon, self.db_status_text, self.db_status_tag = self._create_status_row(
            card_layout, "数据库: 未连接", lambda: self.show_status_detail("database")
        )

        status_layout.addWidget(status_card)
        sidebar_layout.addWidget(status_frame)
        layout.addWidget(sidebar)

        self._update_status_display(True, False)
        self._update_status_display(False, False)

    def _create_nav_toolstrip(self):
        frame = QFrame()
        frame.setObjectName("sidebar_toolstrip")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        tool_pages = ["dashboard", "sync", "history", "settings"]
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
                "sync": "sync.svg",
                "history": "history.svg",
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

        groups = [
            ("运营视图", [("dashboard", "数据运营中心", "dashboard.svg")]),
            ("执行控制", [("sync", "数据同步", "sync.svg"), ("schedule", "定时调度", "schedule.svg")]),
            ("配置管理", [("forms", "表单配置", "forms.svg"), ("settings", "系统设置", "settings.svg")]),
            ("追踪分析", [("history", "同步历史", "history.svg")]),
        ]

        self.nav_item_map = {}
        for group_text, children in groups:
            group_item = QTreeWidgetItem([group_text])
            group_item.setFlags(Qt.ItemIsEnabled)
            group_item.setData(0, Qt.UserRole, None)
            group_item.setForeground(0, QColor(ColorTokens.NEUTRAL_400))
            group_font = group_item.font(0)
            group_font.setBold(True)
            group_font.setPointSize(max(9, group_font.pointSize() - 1))
            group_item.setFont(0, group_font)
            self.nav_tree.addTopLevelItem(group_item)

            for page_id, title, _icon_name in children:
                child_item = QTreeWidgetItem([title])
                child_item.setData(0, Qt.UserRole, page_id)
                child_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                group_item.addChild(child_item)
                self.nav_item_map[page_id] = child_item

            group_item.setExpanded(True)

        self.nav_tree.currentItemChanged.connect(self._on_nav_tree_item_changed)
        return self.nav_tree

    def _on_nav_tree_item_changed(self, current, previous):
        if current is None:
            return

        page_id = current.data(0, Qt.UserRole)
        if page_id is None:
            previous_page_id = previous.data(0, Qt.UserRole) if previous is not None else None
            fallback_page_id = previous_page_id or self.current_page_id
            fallback_item = self.nav_item_map.get(fallback_page_id)
            if fallback_item is not None and self.nav_tree is not None:
                self.nav_tree.blockSignals(True)
                self.nav_tree.setCurrentItem(fallback_item)
                self.nav_tree.blockSignals(False)
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
        if sync_nav:
            self._set_nav_tree_current(page_id)
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
        shell_layout.setContentsMargins(18, 16, 18, 18)
        shell_layout.setSpacing(14)

        shell_layout.addWidget(self._create_top_status_bar())

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setObjectName("main-content")
        shell_layout.addWidget(self.stacked_widget, 1)

        self.pages = {
            "dashboard": DashboardPage(self),
            "sync": SyncPage(self),
            "forms": FormConfigPage(self),
            "schedule": SchedulePage(self),
            "history": HistoryPage(self),
            "settings": SettingsPage(self),
        }

        for page_name in self.page_order:
            self.stacked_widget.addWidget(self.pages[page_name])

        layout.addWidget(content_shell)

    def _create_top_status_bar(self):
        bar = QFrame()
        bar.setObjectName("top_status_bar")
        bar.setProperty("ui", "win11-command-bar")
        root_layout = QVBoxLayout(bar)
        root_layout.setContentsMargins(18, 14, 18, 14)
        root_layout.setSpacing(14)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)
        self.topbar_breadcrumb = QLabel("首页 / 运营总览")
        self.topbar_breadcrumb.setObjectName("topbar_breadcrumb")
        self.topbar_breadcrumb.setVisible(False)
        top_row.addWidget(self.topbar_breadcrumb)
        top_row.addStretch()

        self.topbar_search = QLineEdit()
        self.topbar_search.setObjectName("topbar_search")
        self.topbar_search.setPlaceholderText(ShellText.TOPBAR_SEARCH_PLACEHOLDER)
        self.topbar_search.returnPressed.connect(self.handle_topbar_search)
        self.topbar_search.setClearButtonEnabled(True)
        self.topbar_search.setMinimumWidth(120)
        self.topbar_search.setMaximumWidth(280)
        top_row.addWidget(self.topbar_search)

        self.btn_search = self._create_top_action_button(ShellText.SEARCH, self.focus_topbar_search, accent=True)
        self.btn_notice = self._create_top_action_button(ShellText.HISTORY, lambda: self.switch_to_page("history"))
        self.btn_setting = self._create_top_action_button(
            ShellText.SYSTEM_SETTINGS, lambda: self.switch_to_page("settings")
        )
        self.topbar_action_buttons = [self.btn_search, self.btn_notice, self.btn_setting]
        top_row.addWidget(self.btn_search)
        top_row.addWidget(self.btn_notice)
        top_row.addWidget(self.btn_setting)

        self.topbar_user = QLabel(ShellText.TOPBAR_USER_BADGE)
        self.topbar_user.setObjectName("topbar_user")
        top_row.addWidget(self.topbar_user)
        root_layout.addLayout(top_row)

        layout = QHBoxLayout()
        layout.setSpacing(16)

        title_wrap = QVBoxLayout()
        title_wrap.setSpacing(4)
        self.topbar_title = QLabel("运营总览")
        self.topbar_title.setObjectName("topbar_title")
        self.topbar_subtitle = QLabel("查看核心运行指标、连接状态与任务概览")
        self.topbar_subtitle.setObjectName("topbar_subtitle")
        self.topbar_subtitle.setVisible(False)
        title_wrap.addWidget(self.topbar_title)
        title_wrap.addWidget(self.topbar_subtitle)
        layout.addLayout(title_wrap)
        layout.addStretch()

        self.topbar_sync_badge = QLabel("自动同步待命")
        self.topbar_sync_badge.setProperty("class", "topbar-chip-neutral")
        self.topbar_kd_badge = QLabel("金蝶离线")
        self.topbar_kd_badge.setProperty("class", "topbar-chip-danger")
        self.topbar_db_badge = QLabel("数据库离线")
        self.topbar_db_badge.setProperty("class", "topbar-chip-danger")
        self.topbar_time = QLabel("")
        self.topbar_time.setObjectName("topbar_time")

        layout.addWidget(self.topbar_sync_badge, 0, Qt.AlignVCenter)
        layout.addWidget(self.topbar_kd_badge, 0, Qt.AlignVCenter)
        layout.addWidget(self.topbar_db_badge, 0, Qt.AlignVCenter)
        layout.addWidget(self.topbar_time, 0, Qt.AlignVCenter)
        root_layout.addLayout(layout)
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
        if hasattr(self, "topbar_search") and self.topbar_search is not None:
            self.topbar_search.setFocus()
            self.topbar_search.selectAll()

    def _apply_responsive_shell_layout(self):
        compact = self.width() <= 1366
        self.sidebar_compact = compact

        if self.sidebar is not None:
            self.sidebar.setProperty("compact", compact)
            self.sidebar.setMaximumWidth(self.sidebar_compact_width if compact else 320)
            sidebar_style = self.sidebar.style()
            if sidebar_style is not None:
                sidebar_style.unpolish(self.sidebar)
                sidebar_style.polish(self.sidebar)

        if self.sidebar_logo_subtitle is not None:
            self.sidebar_logo_subtitle.setVisible(not compact)
        if self.sidebar_section_title is not None:
            self.sidebar_section_title.setVisible(not compact)
        if self.sidebar_status_card is not None:
            self.sidebar_status_card.setVisible(not compact)

        if hasattr(self, "topbar_search") and self.topbar_search is not None:
            self.topbar_search.setMaximumWidth(180 if compact else 280)

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
        title, subtitle = self.page_meta.get(page_id, self.page_meta["dashboard"])
        self.topbar_title.setText(title)
        self.topbar_subtitle.setText(subtitle)
        if hasattr(self, "topbar_breadcrumb"):
            self.topbar_breadcrumb.setText(f"首页 / {title}")
        self._refresh_desktop_status()

    def _refresh_top_status_bar(self):
        if not all(
            hasattr(self, attr)
            for attr in (
                "topbar_kd_badge",
                "topbar_db_badge",
                "topbar_sync_badge",
                "topbar_time",
            )
        ):
            return

        self._set_topbar_chip(
            self.topbar_kd_badge,
            "金蝶已连接" if self.kd_connected else "金蝶离线",
            "success" if self.kd_connected else "danger",
        )
        self._set_topbar_chip(
            self.topbar_db_badge,
            "数据库已连接" if self.db_connected else "数据库离线",
            "success" if self.db_connected else "danger",
        )
        self._set_topbar_chip(
            self.topbar_sync_badge,
            "自动同步运行中" if auto_scheduler.is_running() else "自动同步待命",
            "info" if auto_scheduler.is_running() else "neutral",
        )
        self.topbar_time.setText(datetime.now().strftime("%Y-%m-%d %H:%M"))
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
            ("运营总览", "dashboard", "Ctrl+1"),
            ("同步执行", "sync", "Ctrl+2"),
            ("表单配置", "forms", "Ctrl+3"),
            ("调度管理", "schedule", "Ctrl+4"),
            ("历史记录", "history", "Ctrl+5"),
            ("系统设置", "settings", "Ctrl+6"),
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
        """Create compact desktop status bar."""
        status = self.statusBar()
        status.setObjectName("desktop_status_bar")
        status.setSizeGripEnabled(True)

        self.statusbar_state = QLabel("待命")
        self.statusbar_state.setObjectName("statusbar_state")
        self.statusbar_conn = QLabel("连接状态检测中")
        self.statusbar_conn.setObjectName("statusbar_conn")
        self.statusbar_clock = QLabel("--:--:--")
        self.statusbar_clock.setObjectName("statusbar_clock")

        status.addWidget(self.statusbar_state)
        status.addPermanentWidget(self.statusbar_conn, 1)
        status.addPermanentWidget(self.statusbar_clock)
        self._refresh_desktop_status()

    def setup_shortcuts(self):
        """Register application-wide keyboard shortcuts."""
        key_map = {
            "F5": self.refresh_dashboard,
            "Ctrl+F": self.focus_topbar_search,
            "Ctrl+1": lambda: self.switch_to_page("dashboard"),
            "Ctrl+2": lambda: self.switch_to_page("sync"),
            "Ctrl+3": lambda: self.switch_to_page("forms"),
            "Ctrl+4": lambda: self.switch_to_page("schedule"),
            "Ctrl+5": lambda: self.switch_to_page("history"),
            "Ctrl+6": lambda: self.switch_to_page("settings"),
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
            self.main_splitter.setSizes([256, max(740, total - 256)])
        else:
            self.main_splitter.setSizes([0, total])
        self._refresh_desktop_status()

    def _refresh_desktop_status(self):
        if not all(hasattr(self, attr) for attr in ("statusbar_state", "statusbar_conn", "statusbar_clock")):
            return
        self.statusbar_state.setText(self.topbar_title.text() if hasattr(self, "topbar_title") else "待命")
        self.statusbar_conn.setText(
            f"金蝶: {'已连接' if self.kd_connected else '离线'} | "
            f"数据库: {'已连接' if self.db_connected else '离线'} | "
            f"调度: {'运行中' if auto_scheduler.is_running() else '已停止'}"
        )
        self.statusbar_clock.setText(datetime.now().strftime("%H:%M:%S"))

    def _show_window_menu(self, global_pos):
        if hasattr(self, "window_menu_popup") and self.window_menu_popup is not None:
            self.window_menu_popup.exec(global_pos)

    def _minimize_window(self):
        self._hide_snap_preview()
        self.showMinimized()

    def _toggle_max_restore(self):
        self._hide_snap_preview()
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self._update_titlebar_state()

    def _update_titlebar_state(self):
        if self.title_bar is not None:
            self.title_bar.set_maximized(self.isMaximized())

    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange:
            self._update_titlebar_state()
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











