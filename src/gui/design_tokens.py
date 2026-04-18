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
    GRID_LINE = STROKE_DEFAULT

    # Text.
    TEXT_PRIMARY = NEUTRAL_900
    TEXT_SECONDARY = NEUTRAL_700
    TEXT_MUTED = NEUTRAL_500
    TEXT_DISABLED = NEUTRAL_400

    # Status colors.
    SUCCESS = "#2E95D9"
    SUCCESS_BG = "#EAF5FF"
    SUCCESS_BORDER = "#BFDFFF"

    WARNING = "#B0861A"
    WARNING_BG = "#FFF8E2"
    WARNING_BORDER = "#EAD391"

    DANGER = "#C24D4D"
    DANGER_BG = "#FCEEEE"
    DANGER_BORDER = "#F1C1C1"

    INFO = ACCENT_600
    INFO_BG = ACCENT_50
    INFO_BORDER = "#BBDFFF"

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


def qcolor(value: str, alpha: int | None = None) -> QColor:
    """Convert a hex color into QColor."""
    color = QColor(value)
    if alpha is not None:
        color.setAlpha(alpha)
    return color
