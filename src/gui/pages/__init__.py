"""
页面模块
包含所有页面组件
"""

from src.gui.pages.dashboard_page import DashboardPage
from src.gui.pages.forms_page import FormConfigPage
from src.gui.pages.history_page import HistoryPage
from src.gui.pages.schedule_page import SchedulePage
from src.gui.pages.settings_page import SettingsPage
from src.gui.pages.sync_page import SyncPage

__all__ = [
    "SyncPage",
    "SchedulePage",
    "DashboardPage",
    "SettingsPage",
    "HistoryPage",
    "FormConfigPage",
]
