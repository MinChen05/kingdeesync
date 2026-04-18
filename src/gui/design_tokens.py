"""
Design tokens for the desktop UI.

Direction: mint-and-white palette with clean neutral contrast.

Compatibility: keep legacy token names (e.g. BRAND_600, TEXT_PRIMARY) working,
since other modules may still reference them. Prefer the Fluent-friendly aliases
for new code.
"""

from PySide6.QtGui import QColor


class ColorTokens:
    """
    Shared color tokens (mint-and-white palette).

    Notes:
    - `ACCENT_*`, `NEUTRAL_*`, `SURFACE_*`, `STROKE_*` are the preferred names.
    - `BRAND_*`, `TEXT_*`, `BORDER_*` are legacy aliases kept for compatibility.
    """

    # Accent (mint green).
    ACCENT_700 = "#0F8A6B"  # pressed/darker
    ACCENT_600 = "#16A67D"  # primary accent
    ACCENT_500 = "#37C39A"  # hover/lighter accent
    ACCENT_100 = "#C9F2E5"  # tint
    ACCENT_50 = "#EAFBF5"  # very light tint

    # Neutrals.
    NEUTRAL_900 = "#11212A"  # near-black
    NEUTRAL_700 = "#233740"
    NEUTRAL_600 = "#34505A"
    NEUTRAL_500 = "#56717C"
    NEUTRAL_400 = "#7D97A0"
    NEUTRAL_200 = "#CDE0DB"
    NEUTRAL_100 = "#E6F0ED"
    NEUTRAL_50 = "#F2F8F6"

    # Surfaces and strokes.
    SURFACE_BASE = "#FFFFFF"
    SURFACE_SUBTLE = "#F5FCF9"
    SURFACE_MUTED = "#EAF7F2"
    STROKE_DEFAULT = "#CFE3DC"
    STROKE_SUBTLE = "#E1EFEA"
    GRID_LINE = STROKE_DEFAULT

    # Text.
    TEXT_PRIMARY = NEUTRAL_900
    TEXT_SECONDARY = NEUTRAL_700
    TEXT_MUTED = NEUTRAL_500
    TEXT_DISABLED = NEUTRAL_400

    # Status colors.
    SUCCESS = "#178B68"
    SUCCESS_BG = "#E4F8EF"
    SUCCESS_BORDER = "#A7E3CC"

    WARNING = "#B0861A"
    WARNING_BG = "#FFF8E2"
    WARNING_BORDER = "#EAD391"

    DANGER = "#C24D4D"
    DANGER_BG = "#FCEEEE"
    DANGER_BORDER = "#F1C1C1"

    INFO = ACCENT_600
    INFO_BG = ACCENT_50
    INFO_BORDER = "#A4E3CF"

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
    BAR_START = "#16A67D"
    BAR_END = "#52CDA9"
    LINE = "#0F8A6B"
    # Use mint in RGBA form for fills.
    LINE_FILL_START = (22, 166, 125, 68)
    LINE_FILL_END = (22, 166, 125, 0)
    TOOLTIP_BG = "#1C3B43"
    TOOLTIP_TEXT = "#FFFFFF"


def qcolor(value: str, alpha: int | None = None) -> QColor:
    """Convert a hex color into QColor."""
    color = QColor(value)
    if alpha is not None:
        color.setAlpha(alpha)
    return color
