"""
Design tokens for the desktop UI.

Direction: sky-blue-and-white palette with clean neutral contrast.

Compatibility: keep legacy token names (e.g. BRAND_600, TEXT_PRIMARY) working,
since other modules may still reference them. Prefer the Fluent-friendly aliases
for new code.
"""

from PySide6.QtGui import QColor


class ColorTokens:
    """
    Shared color tokens (sky-blue-and-white palette).

    Notes:
    - `ACCENT_*`, `NEUTRAL_*`, `SURFACE_*`, `STROKE_*` are the preferred names.
    - `BRAND_*`, `TEXT_*`, `BORDER_*` are legacy aliases kept for compatibility.
    """

    # Accent (sky blue).
    ACCENT_700 = "#2578DA"  # pressed/darker
    ACCENT_600 = "#4CA8F8"  # primary accent
    ACCENT_500 = "#7AC2FF"  # hover/lighter accent
    ACCENT_100 = "#D8EEFF"  # tint
    ACCENT_50 = "#EFF8FF"  # very light tint
    INTERACTIVE_SURFACE = "#2563EB"  # interactive surface (buttons, links, active bg)
    INTERACTIVE_PRESSED = "#1D4ED8"  # pressed/active text and surfaces
    INTERACTIVE_PRIMARY = "#0F6CBD"  # primary interactive text and controls
    ACCENT_BG_SOFT = "#EDF6FF"  # soft accent background (cards, panels)
    ACCENT_HOVER_BG = "#E8F0FF"  # accent hover background

    # Neutrals.
    NEUTRAL_900 = "#14263A"  # near-black
    NEUTRAL_700 = "#284157"
    NEUTRAL_600 = "#41607B"
    NEUTRAL_500 = "#647F97"
    NEUTRAL_400 = "#8CA3B6"
    NEUTRAL_200 = "#D7E3ED"
    NEUTRAL_100 = "#EBF2F8"
    NEUTRAL_50 = "#F6FAFD"

    # Surfaces and strokes.
    SURFACE_BASE = "#FFFFFF"
    SURFACE_SUBTLE = "#F7FBFF"
    SURFACE_MUTED = "#EEF6FD"
    STROKE_DEFAULT = "#D4E5F3"
    STROKE_SUBTLE = "#E5F0F8"
    STROKE_SOFT_BLUE = "#DBE3F0"
    GRID_LINE = STROKE_DEFAULT

    # Text.
    TEXT_PRIMARY = NEUTRAL_900
    TEXT_SECONDARY = NEUTRAL_700
    TEXT_MUTED = NEUTRAL_500
    TEXT_DISABLED = NEUTRAL_400
    TEXT_PRIMARY_DEEP = "#0F172A"
    TEXT_PRIMARY_SOFT = "#1F2937"
    TEXT_SECONDARY_DEEP = "#334155"

    # Status colors.
    SUCCESS = "#2E95D9"
    SUCCESS_BG = "#EAF5FF"
    SUCCESS_BORDER = "#BFDFFF"
    SUCCESS_GREEN = "#16A67D"
    SUCCESS_GREEN_DARK = "#0F8A6B"
    SUCCESS_GREEN_DEEP = "#0F7B42"
    SUCCESS_GREEN_MEDIUM = "#178B68"
    SUCCESS_GREEN_BG = "#F8FFFC"
    SUCCESS_GREEN_BG_LIGHT = "#EAFBF5"
    SUCCESS_GREEN_BORDER = "#D2E9E0"

    WARNING = "#B0861A"
    WARNING_BG = "#FFF8E2"
    WARNING_BORDER = "#EAD391"
    WARNING_ORANGE_DEEP = "#B14E24"

    DANGER = "#C24D4D"
    DANGER_BG = "#FCEEEE"
    DANGER_BORDER = "#F1C1C1"

    INFO = ACCENT_600
    INFO_BG = ACCENT_50
    INFO_BORDER = "#BBDFFF"

    # Sync execution page tone colors.
    SYNC_TONE_BLUE = "#2F80ED"
    SYNC_TONE_GREEN = "#2CB66D"
    SYNC_TONE_SLATE = "#7A8A9A"

    # Legacy aliases (kept for backwards compatibility).
    BRAND_700 = ACCENT_700
    BRAND_600 = ACCENT_600
    BRAND_500 = ACCENT_500
    BRAND_100 = ACCENT_100
    BRAND_50 = ACCENT_50

    BORDER_DEFAULT = STROKE_DEFAULT
    BORDER_SUBTLE = STROKE_SUBTLE


class RadiusTokens:
    """Corner radius tokens."""

    SM = 10
    MD = 12
    LG = 18
    PILL = 999


class SizeTokens:
    """Control sizing tokens."""

    CONTROL_HEIGHT = 40
    BUTTON_HEIGHT = 36
    PAGINATION_SIZE = 34
    ICON_SIZE_SM = 16
    ICON_SIZE_MD = 20
    SIDEBAR_EXPANDED = 256
    SIDEBAR_COMPACT = 96
    MIN_DESKTOP_WIDTH = 1366
    MIN_DESKTOP_HEIGHT = 768
    FIELD_ROW_SPIN_WIDTH_COMPACT = 120
    FIELD_ROW_SPIN_WIDTH = 140
    FIELD_ROW_EDITOR_MAX_WIDTH = 420
    QT_MAX_WIDTH = 16777215
    LOG_ACTION_BUTTON_HEIGHT = 32
    METRIC_CARD_MIN_HEIGHT = 84
    FORM_ACTION_BUTTON_HEIGHT = 36
    FORM_SEARCH_WIDTH_COMPACT = 260
    FORM_SEARCH_WIDTH = 320
    FORM_SEARCH_MIN_WIDTH_COMPACT = 180
    FORM_SEARCH_MIN_WIDTH = 260
    SYNC_LOG_MIN_HEIGHT_COMPACT = 180
    SYNC_LOG_MIN_HEIGHT = 220
    SYNC_CONFIG_PANEL_WIDTH = 420
    SYNC_EXECUTION_CARD_MAX_HEIGHT_COMPACT = 320
    SYNC_SPLITTER_SIZES_WIDE = (540, 980)
    SCHEDULE_LOG_MIN_HEIGHT_COMPACT = 180
    SCHEDULE_LOG_MIN_HEIGHT = 220
    SCHEDULE_LEFT_PANEL_MIN_WIDTH = 420
    SCHEDULE_LEFT_PANEL_MAX_WIDTH = 560
    SCHEDULE_SPLITTER_SIZES_WIDE = (560, 920)
    SCHEDULE_STATUS_CARD_MIN_HEIGHT = 220
    SCHEDULE_WORKSPACE_STATUS_EXTRA_HEIGHT = 180
    SCHEDULE_WORKSPACE_HEIGHT_RATIO = 0.58
    SCHEDULE_WORKSPACE_BOTTOM_MIN_HEIGHT = 260
    SYNC_WORKSPACE_HEIGHT_RATIO = 0.44
    SYNC_WORKSPACE_BOTTOM_MIN_HEIGHT = 360
    PROGRESS_BAR_HEIGHT = 10
    SCHEDULE_STATUS_TEXT_MIN_HEIGHT = 38
    SCHEDULE_PRESET_BUTTON_HEIGHT = 32
    TOGGLE_WIDTH = 44
    TOGGLE_HEIGHT = 24
    COMBO_POPUP_ITEM_HEIGHT = 40
    COMBO_POPUP_EXTRA_HEIGHT = 60
    COMBO_POPUP_MAX_HEIGHT = 300
    CHART_MIN_HEIGHT = 200
    CHART_COMPACT_MIN_HEIGHT = 150
    CHART_BAR_HEIGHT = 24
    PAGINATION_BUTTON_HEIGHT = 34
    PAGINATION_LABEL_WIDTH = 52
    PAGINATION_JUMP_WIDTH = 86
    HISTORY_PAGINATION_LABEL_WIDTH = 42
    HISTORY_PAGINATION_COMBO_WIDTH = 96
    HISTORY_EXPORT_BUTTON_WIDTH = 108
    HISTORY_EXPORT_BUTTON_HEIGHT = 36
    HISTORY_FILTER_TIME_WIDTH = 260
    HISTORY_FILTER_SELECT_WIDTH = 176
    HISTORY_FILTER_SEARCH_MIN_WIDTH = 280
    HISTORY_FILTER_ACTION_WIDTH = 90
    DASHBOARD_STATUS_CARD_MIN_SIZE = 220
    DASHBOARD_TREND_CHART_MIN_HEIGHT = 300
    DASHBOARD_VOLUME_CHART_MIN_HEIGHT = 240
    DASHBOARD_TABLE_HEADER_HEIGHT = 24
    DASHBOARD_TABLE_ROW_HEIGHT = 28
    DASHBOARD_TABLE_MAX_HEIGHT = 320
    SCHEDULE_INTERVAL_SPIN_WIDTH = 160
    DATA_TABLE_MIN_SECTION_WIDTH = 60
    DATA_TABLE_ROW_HEIGHT = 42
    HISTORY_TABLE_ROW_HEIGHT = 33
    HISTORY_TABLE_HEADER_HEIGHT = 36


class ChartTokens:
    """Chart-specific tokens."""

    BAR_TRACK = ColorTokens.STROKE_DEFAULT
    BAR_START = "#4CA8F8"
    BAR_END = "#8DD1FF"
    LINE = "#2578DA"
    # Use sky blue in RGBA form for fills.
    LINE_FILL_START = (76, 168, 248, 76)
    LINE_FILL_END = (76, 168, 248, 0)
    TOOLTIP_BG = "#17324D"
    TOOLTIP_TEXT = "#FFFFFF"


class SpacingTokens:
    """Spacing scale tokens (pixels)."""

    NONE = 0
    XXS = 3
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 20
    XXL = 24
    XXXL = 32
    ACTION_BAR_GAP = 10
    FIELD_ROW_VERTICAL = 12
    FIELD_ROW_GAP = 14
    LOG_TOOLBAR_H_PADDING = 10
    LOG_TOOLBAR_V_PADDING = 8
    FORM_ROW_VERTICAL = 14
    FORM_ROW_GAP = 12
    FORM_META_GAP = 6
    FORM_PAGE_GAP = 16
    FORM_FILTER_GAP = 12
    FORM_LIST_VERTICAL_PADDING = 4
    WORKSPACE_COLUMN_GAP = 14
    PROGRESS_PANEL_PADDING = 14
    SHELL_CARD_PADDING = 18


class TypographyTokens:
    """Typography tokens."""

    FONT_FAMILY = '"Segoe UI Variable", "Microsoft YaHei UI", sans-serif'
    FONT_SIZE_SM = 12
    FONT_SIZE_MD = 13
    FONT_SIZE_LG = 15
    FONT_SIZE_XL = 18
    FONT_WEIGHT_NORMAL = 400
    FONT_WEIGHT_MEDIUM = 600
    FONT_WEIGHT_BOLD = 700


class EffectTokens:
    """Visual effect tokens."""

    SHADOW_CARD = "0 2px 8px rgba(0,0,0,0.06)"
    SHADOW_POPUP = "0 4px 16px rgba(0,0,0,0.12)"
    FOCUS_RING_COLOR = ColorTokens.ACCENT_500


def qcolor(value: str, alpha: int | None = None) -> QColor:
    """Convert a hex color into QColor."""
    color = QColor(value)
    if alpha is not None:
        color.setAlpha(alpha)
    return color
