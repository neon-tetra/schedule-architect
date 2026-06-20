"""
presentation/theme.py
─────────────────────
Single source of truth for all visual constants used across the
presentation layer.  Import this module; never define colours, fonts,
or geometry in individual chart builders.

Usage
─────
    from presentation.theme import T, SKILL, CARD, MARGIN, HOURS
    # T       — ThemeTokens (colours + fonts)
    # SKILL   — SkillTokens (labels, order, colour maps)
    # CARD    — CardGeometry (derived card positions)
    # MARGIN  — pre-built margin dicts
    # HOURS   — operating window constants

Registration
────────────
    Import this module once (app.py or presentation/__init__.py) and
    the "schedule_architect" Plotly template is registered automatically.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import plotly.graph_objects as go
import plotly.io as pio


# ── 1. COLOURS ───────────────────────────────────────────────────────────────

# Surfaces
BG_PAGE     = "#0f1117"
BG_CARD     = "#1a2130"
BG_CARD_ALT = "#1c2433"   # alternating tint for adjacent cards

# Text / chrome
TEXT_PRIMARY = "#e6edf3"
TEXT_MUTED   = "#8b949e"
BORDER       = "#30363d"
GRID         = "#2a3040"

# Accent
ACCENT      = "#58a6ff"
GHOST_FILL  = "rgba(80, 80, 80, 0.15)"

# Skill palette — keyed to raw skill_id strings from domain.py
SKILL_COLORS: dict[str, str] = {
    "account_services": "#58a6ff",
    "online_orders":    "#79c0ff",
    "photo":            "#a371f7",
    "floral":           "#7ee787",
    "bakery":           "#ffa657",
    "escalations":      "#ff7b72",
}

# Monochromatic blue family for stacked-area base
# Six entries — same order as SKILL_ORDER_RAW below
SKILL_MONO: list[str] = [
    "rgba(88, 166, 255, 0.25)",
    "rgba(88, 166, 255, 0.35)",
    "rgba(88, 166, 255, 0.45)",
    "rgba(88, 166, 255, 0.55)",
    "rgba(88, 166, 255, 0.65)",
    "rgba(88, 166, 255, 0.80)",
]

# Coverage / shortfall diverging scale (0-1 normalised)
COVERAGE_COLORSCALE: list[list] = [
    [0.00, "#d94801"],
    [0.50, "#fd8d3c"],
    [0.75, "#f0f0f0"],
    [0.80, "#9ecae1"],
    [1.00, "#08519c"],
]


# ── 2. TYPOGRAPHY ─────────────────────────────────────────────────────────────
#
# Semantic roles — use these, not bare size numbers.
# Each is a plain dict so it can be unpacked directly into Plotly font args.

FONT_FAMILY = "Arial, sans-serif"

FONT_TITLE:     dict[str, Any] = dict(family=FONT_FAMILY, size=18, color=TEXT_PRIMARY)
FONT_SUBTITLE:  dict[str, Any] = dict(family=FONT_FAMILY, size=13, color=TEXT_MUTED)
FONT_AXIS:      dict[str, Any] = dict(family=FONT_FAMILY, size=11, color=TEXT_MUTED)
FONT_LABEL:     dict[str, Any] = dict(family=FONT_FAMILY, size=11, color=TEXT_MUTED)
FONT_KPI_VALUE: dict[str, Any] = dict(family=FONT_FAMILY, size=28, color=TEXT_PRIMARY)
FONT_KPI_LABEL: dict[str, Any] = dict(family=FONT_FAMILY, size=12, color=TEXT_MUTED)


# ── 3. SKILL METADATA ─────────────────────────────────────────────────────────

# Canonical display labels keyed to raw skill_id
SKILL_LABELS: dict[str, str] = {
    "account_services": "Account Svc",
    "online_orders":    "Online Orders",
    "photo":            "Photo",
    "floral":           "Floral",
    "bakery":           "Bakery",
    "escalations":      "Escalations",
}

# Rendering order — controls stacking order, bar order, legend order
SKILL_ORDER_RAW: list[str] = [
    "account_services",
    "online_orders",
    "bakery",
    "floral",
    "photo",
    "escalations",
]

# Derived — label-ordered list, kept in sync automatically
SKILL_ORDER_LABEL: list[str] = [SKILL_LABELS[s] for s in SKILL_ORDER_RAW]


# ── 4. CARD GEOMETRY ──────────────────────────────────────────────────────────
#
# All four values below are DERIVED from the three root inputs.
# To change card count or row proportions, change the roots only.
#
#   ROOT 1 — how many KPI cards
#   ROOT 2 — what fraction of the figure height the card row occupies
#             (must match row_heights[0] in make_subplots)
#   ROOT 3 — breathing room between the subplot cell edge and the card border

@dataclass(frozen=True)
class CardGeometry:
    count:      int   = 4
    row_height: float = 0.44   # must equal row_heights[0] in make_subplots
    padding:    float = 0.02   # inset from subplot cell edge

    # ── derived ──────────────────────────────────────────────────────────────
    @property
    def width(self) -> float:
        """Card width in paper coordinates."""
        return (1.0 / self.count) - (self.padding * 2)

    @property
    def y0(self) -> float:
        """Card bottom in paper coordinates."""
        return 1.0 - self.row_height + self.padding

    @property
    def y1(self) -> float:
        """Card top in paper coordinates."""
        return 1.0 - self.padding

    @property
    def centers(self) -> list[float]:
        """Horizontal centre of each card in paper coordinates."""
        return [(i + 0.5) / self.count for i in range(self.count)]

    @property
    def fills(self) -> list[str]:
        """Alternating background fills, one per card."""
        pattern = [BG_CARD, BG_CARD_ALT]
        return [pattern[i % 2] for i in range(self.count)]
    
    @property
    def domains(self) -> list[dict]:
        """Explicit x/y domain for each indicator trace."""
        step = 1.0 / self.count
        return [
            dict(
                x=[i * step, (i + 1) * step],
                y=[self.y0, self.y1],
            )
            for i in range(self.count)
        ]

CARD = CardGeometry()   # default instance — import and use directly


# ── 5. MARGINS ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MarginPreset:
    default: dict[str, int] = field(
        default_factory=lambda: dict(t=70, b=36, l=36, r=36)
    )
    slim: dict[str, int] = field(
        default_factory=lambda: dict(t=40, b=36, l=36, r=36)
    )
    tight: dict[str, int] = field(
        default_factory=lambda: dict(t=24, b=24, l=24, r=24)
    )


MARGIN = MarginPreset()


# ── 6. OPERATING HOURS ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class OperatingHours:
    start: int = 8    # inclusive
    end:   int = 20   # inclusive

    @property
    def hours(self) -> list[int]:
        return list(range(self.start, self.end + 1))

    @property
    def tick_labels(self) -> list[str]:
        return [f"{h}:00" for h in self.hours]


HOURS = OperatingHours()


# ── 7. CONVENIENCE BUNDLE ─────────────────────────────────────────────────────
#
# T is a plain namespace for the flat colour/font tokens so chart builders
# can do `t = T` and reference `t.BG_PAGE`, `t.FONT_TITLE` etc. without
# importing every constant individually.

@dataclass(frozen=True)
class ThemeTokens:
    BG_PAGE:     str = BG_PAGE
    BG_CARD:     str = BG_CARD
    BG_CARD_ALT: str = BG_CARD_ALT
    TEXT_PRIMARY: str = TEXT_PRIMARY
    TEXT_MUTED:   str = TEXT_MUTED
    BORDER:       str = BORDER
    GRID:         str = GRID
    ACCENT:       str = ACCENT
    GHOST_FILL:   str = GHOST_FILL

    FONT_FAMILY:   str            = FONT_FAMILY
    FONT_TITLE:    dict[str, Any] = field(default_factory=lambda: FONT_TITLE)
    FONT_SUBTITLE: dict[str, Any] = field(default_factory=lambda: FONT_SUBTITLE)
    FONT_AXIS:     dict[str, Any] = field(default_factory=lambda: FONT_AXIS)
    FONT_LABEL:    dict[str, Any] = field(default_factory=lambda: FONT_LABEL)
    FONT_KPI_VALUE: dict[str, Any] = field(default_factory=lambda: FONT_KPI_VALUE)
    FONT_KPI_LABEL: dict[str, Any] = field(default_factory=lambda: FONT_KPI_LABEL)

    SKILL_COLORS:        dict[str, str] = field(default_factory=lambda: SKILL_COLORS)
    SKILL_MONO:          list[str]      = field(default_factory=lambda: SKILL_MONO)
    COVERAGE_COLORSCALE: list[list]     = field(default_factory=lambda: COVERAGE_COLORSCALE)


T = ThemeTokens()


# ── 8. PLOTLY TEMPLATE ────────────────────────────────────────────────────────
#
# Registered once on import.  Every go.Figure() created after this point
# inherits these defaults automatically — no need to set them per chart.
#
# Override per-figure only when you genuinely need to deviate.

_template = go.layout.Template(
    layout=go.Layout(
        paper_bgcolor=BG_PAGE,
        plot_bgcolor=BG_PAGE,
        font=dict(family=FONT_FAMILY, color=TEXT_PRIMARY),
        colorway=[SKILL_COLORS[s] for s in SKILL_ORDER_RAW],
        title=dict(
            x=0.03,
            xanchor="left",
            font=FONT_TITLE,
            pad=dict(l=6, t=4),
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=FONT_LABEL,
            bordercolor=BORDER,
            borderwidth=1,
        ),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            tickfont=FONT_AXIS,
            linecolor=BORDER,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=GRID,
            zeroline=False,
            tickfont=FONT_AXIS,
            linecolor=BORDER,
        ),
        hoverlabel=dict(
            bgcolor=BG_CARD,
            bordercolor=BORDER,
            font=dict(family=FONT_FAMILY, color=TEXT_PRIMARY, size=12),
        ),
    )
)

pio.templates["schedule_architect"] = _template
pio.templates.default = "schedule_architect"