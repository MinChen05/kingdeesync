"""
页面模块
包含所有页面组件
"""

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

__all__ = [
    "DashboardPage",
    "DataSourcePage",
    "DiagnosticsPage",
    "FormConfigPage",
    "HistoryPage",
    "LogCenterPage",
    "SchedulePage",
    "SettingsPage",
    "SyncPage",
    "TaskManagementPage",
]
