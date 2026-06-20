"""
presentation/volume_chart.py
─────────────────────────────
Hourly call volume area chart with per-skill drill-down and day animation.

Trace index map (fixed — frames and dropdown both depend on this order):
    [0]      ghost total         — grey tozeroy fill, hidden by default
    [1–6]    stacked skill areas — monochrome blue family, stackgroup="volume"
    [7–12]   highlight areas     — per-skill accent colour, hidden by default

Public API
──────────
    build_volume_chart(solve: SolveRun) -> go.Figure
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from core.solve_run import SolveRun
from presentation.theme import (
    T, MARGIN, HOURS,
    SKILL_ORDER_RAW, SKILL_ORDER_LABEL, SKILL_LABELS,
    SKILL_MONO, SKILL_COLORS,
)


# ── constants ─────────────────────────────────────────────────────────────────

DAY_LABELS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

N_SKILLS            = len(SKILL_ORDER_RAW)
IDX_GHOST           = 0
IDX_STACK_START     = 1
IDX_STACK_END       = IDX_STACK_START + N_SKILLS       # 7 (exclusive)
IDX_HIGHLIGHT_START = IDX_STACK_END                    # 7
IDX_HIGHLIGHT_END   = IDX_HIGHLIGHT_START + N_SKILLS   # 13 (exclusive)


# ── 1. DATA PREP ──────────────────────────────────────────────────────────────

def _prep_chart_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a single long-form DataFrame with columns:
        day    : "all" | "Monday" … "Sunday"
        hour   : int, filtered to HOURS.hours
        skill  : raw skill_id string
        demand : float

    Filtering to operating hours and computing both the all-days aggregate
    and per-day rows happens here — nowhere else.
    """
    df = df[df["hour"].isin(HOURS.hours)]

    # per-day rows — map integer day index to day name
    by_day = (
        df.groupby(["day", "hour", "skill"])["demand"]
        .sum()
        .reset_index()
    )
    by_day["day"] = by_day["day"].map(lambda x: DAY_LABELS[x % 7])

    # all-days aggregate
    all_days = (
        df.groupby(["hour", "skill"])["demand"]
        .sum()
        .reset_index()
    )
    all_days.insert(0, "day", "all")

    return pd.concat([all_days, by_day], ignore_index=True)


# ── 2. VISIBILITY HELPERS ─────────────────────────────────────────────────────

def _vis_all() -> list[bool]:
    """Ghost hidden, stack visible, highlights hidden."""
    return (
        [False]           * 1        +   # ghost
        [True]            * N_SKILLS +   # stack
        [False]           * N_SKILLS     # highlights
    )


def _vis_skill(skill_index: int) -> list[bool]:
    """Ghost visible, stack hidden, one highlight visible."""
    highlights = [False] * N_SKILLS
    highlights[skill_index] = True
    return (
        [True]            * 1        +   # ghost
        [False]           * N_SKILLS +   # stack
        highlights                       # highlights
    )


# ── 3. TRACES ─────────────────────────────────────────────────────────────────

def _build_traces(chart_df: pd.DataFrame) -> list[go.Scatter]:
    """
    Build all 13 traces against the all-days aggregate.
    Returns traces in fixed index order: ghost, stack x6, highlight x6.
    """
    traces = []
    all_df = chart_df[chart_df["day"] == "all"]

    # [0] ghost total
    total_by_hour = (
        all_df.groupby("hour")["demand"]
        .sum()
        .reindex(HOURS.hours, fill_value=0)
    )
    traces.append(go.Scatter(
        x=HOURS.hours,
        y=total_by_hour.values,
        fill="tozeroy",
        mode="none",
        fillcolor=T.GHOST_FILL,
        name="Total Volume",
        visible=False,
        hoverinfo="skip",
        showlegend=False,
    ))

    # [1–6] stacked skill areas
    for i, skill in enumerate(SKILL_ORDER_RAW):
        skill_demand = (
            all_df[all_df["skill"] == skill]
            .set_index("hour")["demand"]
            .reindex(HOURS.hours, fill_value=0)
        )
        traces.append(go.Scatter(
            x=HOURS.hours,
            y=skill_demand.values,
            mode="none",
            fill="tonexty" if i > 0 else "tozeroy",
            fillcolor=SKILL_MONO[i],
            name=SKILL_LABELS[skill],
            stackgroup="volume",
            hovertemplate=(
                f"{SKILL_LABELS[skill]}: %{{y:,.0f}}<br>"
                f"%{{x}}:00<extra></extra>"
            ),
        ))

    # [7–12] single-skill highlight areas
    for skill in SKILL_ORDER_RAW:
        skill_demand = (
            all_df[all_df["skill"] == skill]
            .set_index("hour")["demand"]
            .reindex(HOURS.hours, fill_value=0)
        )
        traces.append(go.Scatter(
            x=HOURS.hours,
            y=skill_demand.values,
            mode="none",
            fill="tozeroy",
            fillcolor=SKILL_COLORS.get(skill, T.ACCENT),
            name=SKILL_LABELS[skill],
            visible=False,
            hovertemplate=(
                f"{SKILL_LABELS[skill]}: %{{y:,.0f}}<br>"
                f"%{{x}}:00<extra></extra>"
            ),
            showlegend=False,
        ))

    return traces


# ── 4. DROPDOWN ───────────────────────────────────────────────────────────────

def _build_dropdown() -> dict:
    """
    Skill selector dropdown.  First entry restores the full stack,
    subsequent entries drill into a single skill.
    """
    buttons = [
        dict(
            label="All Queues",
            method="update",
            args=[
                {"visible": _vis_all()},
                {"title.text": "<b>Call Volume — All Queues</b>"},
            ],
        )
    ]

    for i, skill in enumerate(SKILL_ORDER_RAW):
        buttons.append(dict(
            label=SKILL_LABELS[skill],
            method="update",
            args=[
                {"visible": _vis_skill(i)},
                {"title.text": f"<b>Call Volume — {SKILL_LABELS[skill]}</b>"},
            ],
        ))

    return dict(
        type="dropdown",
        x=1.0, xanchor="right",
        y=1.12, yanchor="top",
        bgcolor=T.BG_PAGE,
        bordercolor=T.BORDER,
        font=dict(color=T.TEXT_PRIMARY),
        buttons=buttons,
    )


# ── 5. ANIMATION (deferred) ───────────────────────────────────────────────────

def _build_frames(chart_df: pd.DataFrame) -> list[go.Frame]:
    """
    One Frame per day. Each frame updates y-data on all 13 traces
    in fixed index order. Visibility is intentionally not set —
    dropdown state must survive frame transitions.
    """
    frames = []

    for day_label in DAY_LABELS:
        day_df = chart_df[chart_df["day"] == day_label]
        frame_data = []

        # [0] ghost total
        total_by_hour = (
            day_df.groupby("hour")["demand"]
            .sum()
            .reindex(HOURS.hours, fill_value=0)
        )
        frame_data.append(go.Scatter(y=total_by_hour.values))

        # [1–6] stacked skill areas
        for skill in SKILL_ORDER_RAW:
            skill_demand = (
                day_df[day_df["skill"] == skill]
                .set_index("hour")["demand"]
                .reindex(HOURS.hours, fill_value=0)
            )
            frame_data.append(go.Scatter(y=skill_demand.values))

        # [7–12] highlight areas
        for skill in SKILL_ORDER_RAW:
            skill_demand = (
                day_df[day_df["skill"] == skill]
                .set_index("hour")["demand"]
                .reindex(HOURS.hours, fill_value=0)
            )
            frame_data.append(go.Scatter(y=skill_demand.values))

        frames.append(go.Frame(data=frame_data, name=day_label))

    return frames


def _build_animation_controls() -> tuple[dict, dict]:
    """
    Returns (play_pause_menu, slider).
    """
    play_pause = dict(
        type="buttons",
        showactive=False,
        x=0.0, xanchor="left",
        y=-0.12, yanchor="top",
        bgcolor=T.BG_PAGE,
        bordercolor=T.BORDER,
        font=dict(color=T.TEXT_PRIMARY),
        buttons=[
            dict(
                label="▶ Play",
                method="animate",
                args=[
                    None,
                    {
                        "frame": {"duration": 800, "redraw": True},
                        "fromcurrent": True,
                        "transition": {"duration": 300},
                        "autoplay": False,
                    },
                ],
            ),
            dict(
                label="⏸ Pause",
                method="animate",
                args=[
                    [None],
                    {"frame": {"duration": 0}, "mode": "immediate"},
                ],
            ),
        ],
    )

    slider = dict(
        active=0,        
        currentvalue=dict(
            prefix="Day: ",
            font=dict(color=T.TEXT_MUTED, size=11),
            visible=True,
            xanchor="center",
        ),
        pad=dict(t=40),
        bgcolor=T.BG_PAGE,
        bordercolor=T.BORDER,
        tickcolor=T.TEXT_MUTED,
        font=dict(color=T.TEXT_MUTED, size=10),
        steps=[
            dict(
                label=day,
                method="animate",
                args=[
                    [day],
                    {"frame": {"duration": 0, "redraw": True}, "mode": "immediate"},
                ],
            )
            for day in DAY_LABELS
        ],
    )

    return play_pause, slider


# ── 6. LAYOUT ─────────────────────────────────────────────────────────────────

def _apply_layout(fig: go.Figure, dropdown: dict, play_pause: dict, slider: dict) -> None:
    fig.update_layout(
        height=480,
        margin=MARGIN.default,
        title=dict(
            text="<b>Call Volume — All Queues</b>",
            font=T.FONT_TITLE,
        ),
        xaxis=dict(
            tickmode="array",
            tickvals=HOURS.hours,
            ticktext=HOURS.tick_labels,
        ),
        yaxis=dict(
            rangemode="tozero",
        ),
        legend=dict(
            orientation="h",
            y=-0.15,
            x=0.0,
        ),
        updatemenus=[dropdown, play_pause],
        sliders=[slider],        
    )


# ── 7. PUBLIC ENTRY POINT ─────────────────────────────────────────────────────
def build_volume_chart(
    solve: SolveRun,
    initial_skill: str | None = None,
    initial_day: str | None = None,
) -> go.Figure:
    chart_df = _prep_chart_data(solve.df_interval)

    fig = go.Figure()

    for trace in _build_traces(chart_df):
        fig.add_trace(trace)

    # attach animation frames
    fig.frames = _build_frames(chart_df)
    # build controls
    dropdown = _build_dropdown()
    play_pause, slider = _build_animation_controls()
    _apply_layout(fig, dropdown, play_pause, slider)

    # apply initial skill state
    if initial_skill is not None and initial_skill in SKILL_ORDER_RAW:
        i = SKILL_ORDER_RAW.index(initial_skill)
        for idx, v in enumerate(_vis_skill(i)):
            fig.data[idx].visible = v
        fig.update_layout(
            title_text=f"<b>Call Volume — {SKILL_LABELS[initial_skill]}</b>"
        )

    # apply initial day — jump to that frame immediately
    if initial_day is not None and initial_day in DAY_LABELS:
        day_frame = next(f for f in fig.frames if f.name == initial_day)
        for idx, trace in enumerate(day_frame.data):
            fig.data[idx].y = trace.y
        fig.update_layout(
            sliders=[{**slider, "active": DAY_LABELS.index(initial_day)}]
        )

    return fig