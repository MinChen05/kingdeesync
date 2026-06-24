"""Shared GUI component primitives used across the app."""

from src.gui.components.buttons import ClickableLabel, LoadingButton, ScaleButton, SwitchButton
from src.gui.components.charts import DashboardDualLineChart, HorizontalBarChart, SimpleLineChart, SuccessRateBar
from src.gui.components.combobox import SearchableComboBox
from src.gui.components.common import ActionBar, FieldRow, LogPanel, MetricCard, StatusChip
from src.gui.components.data_table import DataTable
from src.gui.components.page_shell import Win11PageScaffold, Win11SummaryCard
from src.gui.components.states import StateWidget

__all__ = [
    "ActionBar",
    "ClickableLabel",
    "DashboardDualLineChart",
    "DataTable",
    "FieldRow",
    "HorizontalBarChart",
    "LoadingButton",
    "LogPanel",
    "MetricCard",
    "ScaleButton",
    "SearchableComboBox",
    "SimpleLineChart",
    "StateWidget",
    "StatusChip",
    "SuccessRateBar",
    "SwitchButton",
    "Win11PageScaffold",
    "Win11SummaryCard",
]
