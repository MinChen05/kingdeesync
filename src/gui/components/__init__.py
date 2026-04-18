"""Shared GUI component primitives used across the app."""

from src.gui.components.buttons import ClickableLabel, SwitchButton, LoadingButton, ScaleButton
from src.gui.components.charts import SimpleLineChart, HorizontalBarChart, SuccessRateBar
from src.gui.components.combobox import SearchableComboBox
from src.gui.components.page_shell import Win11PageScaffold, Win11SummaryCard
from src.gui.components.states import StateWidget

__all__ = [
    "ClickableLabel",
    "SwitchButton",
    "LoadingButton",
    "ScaleButton",
    "SimpleLineChart",
    "HorizontalBarChart",
    "SuccessRateBar",
    "SearchableComboBox",
    "Win11PageScaffold",
    "Win11SummaryCard",
    "StateWidget",
]
