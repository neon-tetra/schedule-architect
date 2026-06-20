"""
presentation/kpi_chart.py
─────────────────────────
KPI snapshot chart: four indicator cards + volume-by-skill bar.

Public API
──────────
    build_kpi_chart(solve: SolveRun) -> go.Figure
"""

from __future__ import annotations

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core.solve_run import SolveRun
from presentation.theme import (
    T, CARD, MARGIN,
    SKILL_ORDER_RAW, SKILL_ORDER_LABEL, SKILL_LABELS,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _kpi_scalars(solve: SolveRun) -> dict:
    """Derive the four headline numbers from a SolveRun."""
    df = solve.df_interval
    total_volume    = df["demand"].sum()
    total_shortfall = df["shortfall"].sum()
    sla_pct         = (
        (total_volume - total_shortfall) / total_volume
        if total_volume else 0.0
    )
    total_agents       = solve.df_roster["count"].sum()
    total_monthly_cost = (
        solve.df_roster["count"] * solve.df_roster["monthly_cost"]
    ).sum()

    return dict(
        total_volume=total_volume,
        sla_pct=sla_pct,
        total_agents=total_agents,
        total_monthly_cost=total_monthly_cost,
    )


def _volume_by_skill(solve: SolveRun):
    """Return a label-ordered Series: skill_label → total demand."""
    s = (
        solve.df_interval
        .groupby("skill")["demand"]
        .sum()
        .reindex(SKILL_ORDER_RAW, fill_value=0)
    )
    s.index = [SKILL_LABELS[k] for k in s.index]
    return s.reindex(SKILL_ORDER_LABEL)


# ── card background shapes ────────────────────────────────────────────────────

def _add_card_shapes(fig: go.Figure) -> None:
    """Draw the four KPI card backgrounds using CARD geometry."""
    for cx, fill in zip(CARD.centers, CARD.fills):
        fig.add_shape(
            type="rect",
            xref="paper", yref="paper",
            x0=cx - CARD.width / 2,
            x1=cx + CARD.width / 2,
            y0=CARD.y0,
            y1=CARD.y1,
            fillcolor=fill,
            line=dict(color=T.BORDER, width=1),
            layer="below",
        )


# ── indicator traces ──────────────────────────────────────────────────────────
def _add_indicators(fig: go.Figure, kpis: dict) -> None:
    specs = [
        dict(
            mode="number",
            value=kpis["total_volume"],
            title=dict(text="Weekly Call<br>Volume", font=T.FONT_KPI_LABEL),
            number=dict(valueformat=",.0f", font=T.FONT_KPI_VALUE),
        ),
        dict(
            mode="number+delta",
            value=kpis["sla_pct"] * 100,
            title=dict(text="SLA Achievement", font=T.FONT_KPI_LABEL),
            number=dict(suffix="%", valueformat=".1f", font=T.FONT_KPI_VALUE),
            delta=dict(reference=80, relative=False),
        ),
        dict(
            mode="number",
            value=kpis["total_agents"],
            title=dict(text="Total<br>Agents", font=T.FONT_KPI_LABEL),
            number=dict(valueformat=",.0f", font=T.FONT_KPI_VALUE),
        ),
        dict(
            mode="number",
            value=kpis["total_monthly_cost"],
            title=dict(text="Monthly<br>Cost", font=T.FONT_KPI_LABEL),
            number=dict(prefix="$", valueformat=",.0f", font=T.FONT_KPI_VALUE),
        ),
    ]

    for i, spec in enumerate(specs):
        fig.add_trace(go.Indicator(domain=CARD.domains[i], **spec))

# ── bar chart ─────────────────────────────────────────────────────────────────

def _add_volume_bar(fig: go.Figure, vol: "pd.Series") -> None:
    colors = [T.SKILL_COLORS.get(s, T.ACCENT) for s in SKILL_ORDER_RAW]

    fig.add_trace(
        go.Bar(
            x=vol.index,
            y=vol.values,
            marker=dict(color=colors, line=dict(width=0)),
            text=[f"{v:,.0f}" for v in vol.values],
            textposition="outside",
            textfont=T.FONT_LABEL,
            cliponaxis=False,
            showlegend=False,
        ),
        row=1, col=1,
    )


# ── layout ────────────────────────────────────────────────────────────────────

def _apply_layout(fig: go.Figure) -> None:
    fig.update_layout(
        height=620,
        margin=MARGIN.default,
        title=dict(
            text="<b>Operations KPI Snapshot</b>",
            y=0.97, yanchor="top",
            font=T.FONT_TITLE,
        ),
    )

    fig.update_xaxes(
        categoryorder="array",
        categoryarray=SKILL_ORDER_LABEL,
        row=1, col=1,
    )
    fig.update_yaxes(
        rangemode="tozero",
        row=1, col=1,
    )
    fig.update_layout(
        yaxis=dict(domain=[0.0, 1.0 - CARD.row_height - 0.1])
    )

def _add_annotations(fig: go.Figure) -> None:
    shared = dict(showarrow=False, xref="paper", yref="paper",
                  font=T.FONT_SUBTITLE)  # xanchor removed from shared
    fig.add_annotation(
        x=0.01, y=0.965,
        xanchor="left",
        text="Current roster performance and weekly queue volume",
        **shared,
    )
    fig.add_annotation(
        x=0.5, y=0.575,
        xanchor="center",
        text="Call Volume by Queue",
        **shared,
    )

# ── public entry point ────────────────────────────────────────────────────────

def build_kpi_chart(solve: SolveRun) -> go.Figure:
    """
    Build the KPI snapshot figure from a completed SolveRun.

    Returns a go.Figure ready to pass to cl.Plotly().
    """
    kpis = _kpi_scalars(solve)
    vol  = _volume_by_skill(solve)

    fig = make_subplots(
        rows=1,
        cols=4,
        specs=[[{"colspan": 4, "type": "xy"}, None, None, None]],
    )

    _add_card_shapes(fig)
    _add_indicators(fig, kpis)
    _add_volume_bar(fig, vol)
    _apply_layout(fig)
    _add_annotations(fig)

    return fig

