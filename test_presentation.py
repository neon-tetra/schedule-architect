from agent.toolkit import Toolkit
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import chainlit as cl

KPI_THEME = {
    "bg": "#0f1117",
    "card_fills": ["#1a2130", "#1c2433", "#1a2130", "#1c2433"],
    "text_primary": "#e6edf3",
    "text_muted": "#8b949e",
    "border_subtle": "#30363d",
    "grid": "#2a3040",
    "accent": "#58a6ff",
    "font_family": "Arial, sans-serif",
    "skill_colors": {
        "Account Svc": "#58a6ff",
        "Online Orders": "#79c0ff",
        "Photo": "#a371f7",
        "Floral": "#7ee787",
        "Bakery": "#ffa657",
        "Escalations": "#ff7b72",
    },
}

SKILL_LABELS = {
    "account_services": "Account Svc",
    "online_orders": "Online Orders",
    "photo": "Photo",
    "floral": "Floral",
    "bakery": "Bakery",
    "escalations": "Escalations",
}

SKILL_ORDER_RAW = [
    "account_services",
    "online_orders",
    "bakery",
    "floral",
    "photo",
    "escalations",
]

SKILL_ORDER_LABEL = [SKILL_LABELS[s] for s in SKILL_ORDER_RAW]


def build_kpi_chart(df_interval, df_roster):
    t = KPI_THEME

    total_volume = df_interval["demand"].sum()
    total_shortfall = df_interval["shortfall"].sum()
    sla_pct = (total_volume - total_shortfall) / total_volume if total_volume else 0.0
    total_agents = df_roster["count"].sum()
    total_monthly_cost = (df_roster["count"] * df_roster["monthly_cost"]).sum()

    volume_by_skill = (
        df_interval.groupby("skill", as_index=True)["demand"]
        .sum()
        .reindex(SKILL_ORDER_RAW, fill_value=0)
        .reset_index()
    )
    volume_by_skill["skill"] = volume_by_skill["skill"].map(SKILL_LABELS)
    volume_by_skill["skill"] = volume_by_skill["skill"].astype("category").cat.set_categories(
        SKILL_ORDER_LABEL, ordered=True
    )
    volume_by_skill = volume_by_skill.sort_values("skill")

    fig = make_subplots(
        rows=2,
        cols=4,
        row_heights=[0.44, 0.56],
        specs=[
            [{"type": "indicator"}, {"type": "indicator"}, {"type": "indicator"}, {"type": "indicator"}],
            [{"colspan": 4, "type": "bar"}, None, None, None],
        ],
        vertical_spacing=0.07,
        horizontal_spacing=0.03,
    )

    CARD_Y0 = 0.70   # move up/down + card bottom
    CARD_Y1 = 0.92   # card top
    CARD_W  = 0.215  # card width
    CARD_CENTERS = [0.125, 0.375, 0.625, 0.875]

    for cx, fill in zip(CARD_CENTERS, t["card_fills"]):
        fig.add_shape(
            type="rect",
            xref="paper", yref="paper",
            x0=cx - CARD_W / 2, x1=cx + CARD_W / 2,
            y0=CARD_Y0, y1=CARD_Y1,
            fillcolor=fill,
            line=dict(color=t["border_subtle"], width=1),
            layer="below",
        )

    fig.add_trace(
        go.Indicator(
            mode="number",
            value=total_volume,
            title={"text": "Weekly Call<br>Volume", "font": {"size": 12, "color": t["text_muted"]}},
            number={"valueformat": ",.0f", "font": {"size": 28, "color": t["text_primary"]}},
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Indicator(
            mode="number+delta",
            value=sla_pct * 100,
            title={"text": "SLA Achievement", "font": {"size": 12, "color": t["text_muted"]}},
            number={"suffix": "%", "valueformat": ".0f", "font": {"size": 28, "color": t["text_primary"]}},
            delta={"reference": 80, "relative": False},
        ),
        row=1,
        col=2,
    )

    fig.add_trace(
        go.Indicator(
            mode="number",
            value=total_agents,
            title={"text": "Total<br>Agents", "font": {"size": 12, "color": t["text_muted"]}},
            number={"valueformat": ",.0f", "font": {"size": 28, "color": t["text_primary"]}},
        ),
        row=1,
        col=3,
    )

    fig.add_trace(
        go.Indicator(
            mode="number",
            value=total_monthly_cost,
            title={"text": "Monthly<br>Cost", "font": {"size": 12, "color": t["text_muted"]}},
            number={"prefix": "$", "valueformat": ",.0f", "font": {"size": 28, "color": t["text_primary"]}},
        ),
        row=1,
        col=4,
    )

    colors = [t["skill_colors"].get(s, t["accent"]) for s in volume_by_skill["skill"]]
    fig.add_trace(
        go.Bar(
            x=volume_by_skill["skill"],
            y=volume_by_skill["demand"],
            marker=dict(color=colors, line=dict(width=0)),
            text=[f"{v:,.0f}" for v in volume_by_skill["demand"]],
            textposition="outside",
            textfont=dict(color=t["text_muted"], size=11),
            cliponaxis=False,
            showlegend=False,
        ),
        row=2,
        col=1,
    )

    fig.update_layout(
        height=620,
        margin=dict(t=70, b=36, l=36, r=36),
        paper_bgcolor=t["bg"],
        plot_bgcolor=t["bg"],
        font=dict(family=t["font_family"], color=t["text_primary"]),
        title=dict(
            text="<b>Operations KPI Snapshot</b>",
            x=0.03, xanchor="left",
            y=0.95, yanchor="top",
            pad=dict(l=6, t=4),
            font=dict(size=18, color=t["text_primary"]),
        ),
        xaxis2=dict(
            categoryorder="array",
            categoryarray=SKILL_ORDER_LABEL,
            tickfont=dict(color=t["text_muted"], size=11),
            showgrid=False,
            zeroline=False,
        ),
        yaxis2=dict(
            tickfont=dict(color=t["text_muted"], size=11),
            showgrid=True,
            gridcolor=t["grid"],
            zeroline=False,
            rangemode="tozero",
        ),
    )

    fig.add_annotation(
        x=0.01,
        y=0.955,
        xref="paper",
        yref="paper",
        text="Current roster performance and weekly queue volume",
        showarrow=False,
        xanchor="left",
        font=dict(size=11, color=t["text_muted"]),
    )

    fig.add_annotation(
        x=0.5,
        y=0.585,
        xref="paper",
        yref="paper",
        text="Call Volume by Queue",
        showarrow=False,
        font=dict(size=11, color=t["text_muted"]),
    )

    fig.write_html("chart_dev.html")
    return fig


toolkit = Toolkit()
toolkit.execute("run_solve", {"label": "Test_Initial_Run"})
solve = toolkit._context._solves[0]
print(solve)

fig = build_kpi_chart(solve.df_interval, solve.df_roster)


@cl.on_chat_start
async def start():
    await cl.Message(
        content="KPI snapshot",
        elements=[cl.Plotly(name="chart_1", figure=fig, display="inline")],
    ).send()