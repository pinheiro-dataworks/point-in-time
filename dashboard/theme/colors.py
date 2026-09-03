"""The dashboard's single source of truth for color.

Every value here traces to the validated reference palette (six-checks: CVD
adjacent Delta E, normal-vision floor, contrast, lightness band, chroma
floor). Nothing is picked by eye. See the project's dataviz notes for the
validation method; this module just holds the resulting hex values, assigned
by the *job* each color does — never cycled, never reused across jobs.

Color assignment follows one rule throughout the dashboard: a color's meaning
is fixed for the life of the app. "Naive" is always the critical/red end of
the status pair; "point-in-time" is always the good/green end. A sector
picked for emphasis is always the single accent hue; every other sector is
always the same de-emphasis gray. Nothing here is reassigned per-chart.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Chart chrome & ink (light mode - this dashboard does not ship a dark theme)
# ---------------------------------------------------------------------------
CHART_SURFACE = "#FCFCFB"
PAGE_PLANE = "#F7F6EF"
INK_PRIMARY = "#0B0B0B"
INK_SECONDARY = "#52514E"
INK_MUTED = "#898781"
GRIDLINE = "#E1E0D9"
BASELINE = "#C3C2B7"
BORDER = "rgba(11,11,11,0.10)"

# ---------------------------------------------------------------------------
# Status palette - reserved. Used ONLY for naive-vs-point-in-time framing.
# ---------------------------------------------------------------------------
STATUS_GOOD = "#0CA30C"  # point-in-time correct
STATUS_CRITICAL = "#D03B3B"  # naive / wrong
STATUS_WARNING = "#FAB219"  # reserved, unused in v1

NAIVE_COLOR = STATUS_CRITICAL
PIT_COLOR = STATUS_GOOD

# ---------------------------------------------------------------------------
# Diverging pair - naive-minus-PIT sign (overstates vs understates)
# ---------------------------------------------------------------------------
DIVERGING_POSITIVE = "#2A78D6"  # blue: naive OVERSTATES the sector's return
DIVERGING_NEGATIVE = "#D03B3B"  # red: naive UNDERSTATES the sector's return
DIVERGING_MIDPOINT = "#F0EFEC"

# ---------------------------------------------------------------------------
# Emphasis pattern - one sector highlighted, all others de-emphasised
# ---------------------------------------------------------------------------
EMPHASIS_ACCENT = "#D4A657"  # matches the brand mark's warm gradient
DEEMPHASIS_GRAY = "#C3C2B7"
DEEMPHASIS_GRAY_FAINT = "#E1E0D9"

# ---------------------------------------------------------------------------
# Categorical - 8 validated slots. Used only where <= 8 series are on screen
# at once (e.g. a small filtered subset). Assign in this fixed order; never
# cycle past slot 8 - fold any additional series into "Other" or emphasis.
# ---------------------------------------------------------------------------
CATEGORICAL = [
    "#2A78D6",  # 1 blue
    "#EB6834",  # 2 orange
    "#1BAF7A",  # 3 aqua
    "#EDA100",  # 4 yellow
    "#E87BA4",  # 5 magenta
    "#008300",  # 6 green
    "#4A3AA7",  # 7 violet
    "#E34948",  # 8 red
]

# ---------------------------------------------------------------------------
# Brand
# ---------------------------------------------------------------------------
BRAND_BLACK = "#0B0B0B"
BRAND_CREAM = "#F5F4EC"
