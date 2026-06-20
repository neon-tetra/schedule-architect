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
    build_volume_chart(solve: SolveRun, initial_skill=None, initial_day=None) -> go.Figure
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
ALL_DAYS   = ["Weekly Avg"] + DAY_LABELS

N_SKILLS            = len(SKILL_ORDER_RAW)
IDX_GHOST           = 0
IDX_STACK_START     = 1
IDX_STACK_END       = IDX_STACK_START + N_SKILLS        # 7 (exclusive)
IDX_HIGHLIGHT_START = IDX_STACK_END                     # 7
IDX_HIGHLIGHT_END   = IDX_HIGHLIGHT_START + N_SKILLS    # 13 (exclusive)


# ── 1. DATA PREP ──────────────────────────────────────────────────────────────

def _prep_chart_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a single long-form DataFrame with columns:
        day    : "Weekly Avg" | "Monday" … "Sunday"
        hour   : int, filtered to HOURS.hours
        skill  : raw skill_id string
        demand : float
    """
    df = df[df["hour"].isin(HOURS.hours)]

    by_day = (
        df.groupby(["day", "hour", "skill"])["demand"]
        .sum()
        .reset_index()
    )
    by_day["day"] = by_day["day"].map(lambda x: DAY_LABELS[x % 7])

    all_days = (
        df.groupby(["hour", "skill"])["demand"]
        .sum()
        .reset_index()
    )
    all_days.insert(0, "day", "Weekly Avg")

    return pd.concat([all_days, by_day], ignore_index=True)


# ── 2. VISIBILITY HELPERS ─────────────────────────────────────────────────────

def _vis_all() -> list[bool]:
    """Ghost hidden, stack visible, highlights hidden."""
    return (
        [False] * 1        +
        [True]  * N_SKILLS +
        [False] * N_SKILLS
    )


def _vis_skill(skill_index: int) -> list[bool]:
    """Ghost visible, stack hidden, one highlight visible."""
    highlights = [False] * N_SKILLS
    highlights[skill_index] = True
    return (
        [True]  * 1        +
        [False] * N_SKILLS +
        highlights
    )


# ── 3. TRACE BUILDER ──────────────────────────────────────────────────────────

def _build_traces_for_day(day_df: pd.DataFrame) -> list[go.Scatter]:
    """
    Build all 13 traces against a specific day slice.
    Fixed index order: [0] ghost, [1-6] stack, [7-12] highlights.
    """
    traces = []

    # [0] ghost total
    total_by_hour = (
        day_df.groupby("hour")["demand"]
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
            day_df[day_df["skill"] == skill]
            .set_index("hour")["demand"]
            .reindex(HOURS.hours, fill_value=0)
        )
        traces.append(go.Scatter(
            x=HOURS.hours,
            y=skill_demand.values,
            mode="none",
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
            day_df[day_df["skill"] == skill]
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

def _build_dropdown(initial_skill: str | None = None) -> dict:
    """
    Skill selector dropdown. active= is set to match initial_skill so the
    dropdown label agrees with the trace visibility on load.
    """
    active_index = 0
    if initial_skill is not None and initial_skill in SKILL_ORDER_RAW:
        active_index = SKILL_ORDER_RAW.index(initial_skill) + 1  # +1 for "All Queues" at 0

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
        active=active_index,
        type="dropdown",
        x=1.0, xanchor="right",
        y=1.12, yanchor="top",
        bgcolor=T.BG_PAGE,
        bordercolor=T.BORDER,
        font=dict(color=T.TEXT_PRIMARY),
        buttons=buttons,
    )


# ── 5. ANIMATION ──────────────────────────────────────────────────────────────

def _build_frames(chart_df: pd.DataFrame) -> list[go.Frame]:
    """
    One frame per day. Full trace definitions in each frame so stackgroup
    context is preserved across transitions. Visibility not set — dropdown
    state must survive frame changes.
    """
    frames = []

    for day_label in ALL_DAYS:
        day_df = chart_df[chart_df["day"] == day_label]
        frame_data = []

        # [0] ghost total
        total_by_hour = (
            day_df.groupby("hour")["demand"]
            .sum()
            .reindex(HOURS.hours, fill_value=0)
        )
        frame_data.append(go.Scatter(
            x=HOURS.hours,
            y=total_by_hour.values,
            fill="tozeroy",
            mode="none",
            fillcolor=T.GHOST_FILL,
        ))

        # [1–6] stacked skill areas
        for i, skill in enumerate(SKILL_ORDER_RAW):
            skill_demand = (
                day_df[day_df["skill"] == skill]
                .set_index("hour")["demand"]
                .reindex(HOURS.hours, fill_value=0)
            )
            frame_data.append(go.Scatter(
                x=HOURS.hours,
                y=skill_demand.values,
                mode="none",
                fillcolor=SKILL_MONO[i],
                stackgroup="volume",
            ))

        # [7–12] highlight areas
        for skill in SKILL_ORDER_RAW:
            skill_demand = (
                day_df[day_df["skill"] == skill]
                .set_index("hour")["demand"]
                .reindex(HOURS.hours, fill_value=0)
            )
            frame_data.append(go.Scatter(
                x=HOURS.hours,
                y=skill_demand.values,
                mode="none",
                fill="tozeroy",
                fillcolor=SKILL_COLORS.get(skill, T.ACCENT),
            ))

        frames.append(go.Frame(data=frame_data, name=day_label))

    return frames


def _build_animation_controls(active_day_index: int = 0) -> tuple[dict, dict]:
    """Returns (play_pause_menu, slider)."""
    play_pause = dict(
        type="buttons",
        active=-1,
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
        active=active_day_index,
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
            for day in ALL_DAYS
        ],
    )

    return play_pause, slider


# ── 6. LAYOUT ─────────────────────────────────────────────────────────────────

def _apply_layout(
    fig: go.Figure,
    dropdown: dict,
    play_pause: dict,
    slider: dict,
    initial_skill: str | None = None,
) -> None:
    title_text = (
        f"<b>Call Volume — {SKILL_LABELS[initial_skill]}</b>"
        if initial_skill and initial_skill in SKILL_LABELS
        else "<b>Call Volume — All Queues</b>"
    )
    fig.update_layout(
        height=480,
        margin=MARGIN.default,
        title=dict(text=title_text, font=T.FONT_TITLE),
        xaxis=dict(
            tickmode="array",
            tickvals=HOURS.hours,
            ticktext=HOURS.tick_labels,
        ),
        yaxis=dict(rangemode="tozero"),
        legend=dict(orientation="h", y=-0.15, x=0.0),
        updatemenus=[dropdown, play_pause],
        sliders=[slider],
    )


# ── 7. PUBLIC ENTRY POINT ─────────────────────────────────────────────────────

def build_volume_chart(
    solve: SolveRun,
    initial_skill: str | None = None,
    initial_day: str | None = None,
) -> go.Figure:
    """
    Build the volume area chart from a completed SolveRun.

    Parameters
    ----------
    initial_skill : raw skill_id string e.g. "account_services", or None for all
    initial_day   : day label e.g. "Monday" or "Weekly Avg", or None for "Weekly Avg"
    """
    resolved_day = initial_day if initial_day in ALL_DAYS else "Weekly Avg"

    chart_df = _prep_chart_data(solve.df_interval)

    # build traces born in the correct initial day state
    day_df = chart_df[chart_df["day"] == resolved_day]
    fig = go.Figure()
    for trace in _build_traces_for_day(day_df):
        fig.add_trace(trace)

    # apply initial skill visibility directly on the freshly built traces
    if initial_skill is not None and initial_skill in SKILL_ORDER_RAW:
        vis = _vis_skill(SKILL_ORDER_RAW.index(initial_skill))
        for idx, v in enumerate(vis):
            fig.data[idx].update(visible=v)

    # frames + controls
    fig.frames = _build_frames(chart_df)
    dropdown  = _build_dropdown(initial_skill=initial_skill)
    play_pause, slider = _build_animation_controls(
        active_day_index=ALL_DAYS.index(resolved_day)
    )
    _apply_layout(fig, dropdown, play_pause, slider, initial_skill=initial_skill)

    return fig