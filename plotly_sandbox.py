"""
dev_sandbox.py — quick harness for solver/presentation development.
Run with: python dev_sandbox.py
"""
from agent.toolkit import Toolkit

toolkit = Toolkit()

# Define a roster change
toolkit.execute("define_roster", {
    "entries": [
        {"skills": ["account_services", "floral"],      "count": 3},
        {"skills": ["account_services", "bakery"],      "count": 5},
        {"skills": ["account_services", "escalations"], "count": 7},  # +2 vs default
        {"skills": ["account_services"],                "count": 16},
        {"skills": ["online_orders", "photo"],          "count": 7},
        {"skills": ["online_orders", "bakery"],         "count": 1},
        {"skills": ["online_orders", "escalations"],    "count": 2},
        {"skills": ["online_orders"],                   "count": 13},
    ]
})

# Run the solver
toolkit.execute("run_solve", {"label": "Add 2 Escalations"})

solve = toolkit._context._solves[0]


import plotly.graph_objects as go


print(solve.df)

import pandas as pd
df = solve.df.copy()

df = (df.groupby(["slot", "skill"], as_index=False)
        .agg({"demand": "sum", "supply": "mean", "shortfall": "sum"}))

skills = ["account_services", "online_orders", "bakery", "floral", "photo", "escalations"]
from plotly.colors import sample_colorscale
SKILL_COLORSCALE = sample_colorscale("Blues", len(skills))
skill_color_map = {skill: color for skill, color in zip(skills, SKILL_COLORSCALE)}


def make_chart(y_var):

    fig = go.Figure()

    for i, skill in enumerate(skills):
        skill_df = df[df["skill"] == skill].sort_values(["slot"])

        fig.add_trace(go.Scatter(
            x=skill_df["slot"],
            y=skill_df[y_var],
            name=skill,
            mode="lines",
            line=dict(width=0.5, color=skill_color_map[skill]),
            stackgroup="one",
            fill="tozeroy" if i == 0 else "tonexty",
            hovertemplate="%{x}: %{y}<extra>" + skill.replace("_", " ").title() + "</extra>",
        ))

    n = len(skills)

    any_button = dict(
        label="Any",
        method="update",
        args=[{
            "visible": [True] * n,
            "stackgroup": ["one"] * n,
            "fill": ["tozeroy"] + ["tonexty"] * (n - 1),
        }],
    )

    skill_buttons = [
        dict(
            label=skill.replace("_", " ").title(),
            method="update",
            args=[{
                "visible": [j == i for j in range(n)],
                "stackgroup": ["one"] * n,
                "fill": ["tozeroy"] * n,
            }],
        )
        for i, skill in enumerate(skills)
    ]

    fig.update_layout(
        title=f"{y_var} by Skill (8am–8pm)",
        xaxis=dict(title="Slot", tickmode="linear", dtick=1),
        yaxis=dict(title=y_var),
        template="simple_white",
        hovermode="x unified",
        updatemenus=[dict(
            type="dropdown",
            direction="down",
            x=0.0,
            xanchor="left",
            y=1.15,
            yanchor="top",
            showactive=True,
            buttons=[any_button] + skill_buttons,
        )],
    )
    return fig
demand_fig = make_chart("demand")
supply_fig = make_chart("supply")

#make vertically stacked subplot
from plotly.subplots import make_subplots
fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, subplot_titles=["Demand by Skill", "Supply by Skill"])
for trace in demand_fig.data:
    fig.add_trace(trace, row=1, col=1)
for trace in supply_fig.data:
    fig.add_trace(trace, row=2, col=1)

import chainlit as cl

@cl.on_chat_start
async def start():
    figs = []
    #f1 = cl.Plotly(name="chart_1", figure=fig, display="inline")   # default: in the message flow
    f2 = cl.Plotly(name="chart_1", figure=fig, display="side")     # right-hand side panel
    f3 = cl.Plotly(name="chart_1", figure=fig, display="side") 
    #figs.append(f1)
    figs.append(f2)
    figs.append(f3)
    await cl.Message(content="This message has a chart", elements=figs).send()
fig.write_html("chart_dev.html")

#       day  slot             skill  demand  supply  shortfall  day_of_week  hour
# 0       0    16  account_services       4       4          0            0     8
# 1       0    17  account_services       4       4          0            0     8
# 2       0    18  account_services       4       6          0            0     9
# 3       0    19  account_services       5       6          0            0     9
# 4       0    20  account_services       6       6          0            0    10
# ...   ...   ...               ...     ...     ...        ...          ...   ...
# 1003    6    35       escalations       3       3          0            6    17
# 1004    6    36       escalations       2       3          0            6    18
# 1005    6    37       escalations       2       2          0            6    18
# 1006    6    38       escalations       2       2          0            6    19
# 1007    6    39       escalations       2       0          2            6    19

#Step 1 - Create a stacked area chart , from 8am to 8pm , with each skill as slight color gradient
#Step 2 - Create dropdown with all skills + All - when a skill is selected, the overall area chart remains in background/ghosted, selected
#skill appears in front
#Step 3 - add per-day animation widget

#Thinking about this for a moment
#We have a chart object - lets just focus on this volume chart.
#Agent says - give me run6 , volume chart, focus floral monday.  <<run6_volumechart_floral_monday>>
#We have our presentation object
#Imagine handler/dispatch with config options







# #Group by hour, sum demand and shortfall, calculate coverage_pct
# hourly = solve.df.groupby("hour").agg({"demand": "sum", "shortfall": "sum"}).reset_index()
# hourly["coverage_pct"] = (hourly["demand"] - hourly["shortfall"]) / hourly["demand"] 
# print(hourly)


# COVERAGE_COLORSCALE = [
#     [0.0,  "#d94801"],
#     [0.5,  "#fd8d3c"],
#     [0.75, "#f0f0f0"],
#     [0.80, "#9ecae1"],
#     [1.0,  "#08519c"],
# ]

# #x = hour, y = demand, color = coverage_pct
# fig = go.Figure(data=[go.Bar(
#     x=hourly["hour"],
#     y=hourly["demand"],
#     marker=dict(
#         color=hourly["coverage_pct"],
#         colorscale=COVERAGE_COLORSCALE,
#         cmin=0.0,
#         cmax=1.0,
#     ),
# )])
# fig.update_layout(template="seaborn")
# fig.write_html("chart_dev.html")

# def make_grid_coords(count, cols=5):
#     xs = [i % cols for i in range(count)]
#     ys = [-(i // cols) for i in range(count)]  # negative so it fills top-down
#     return xs, ys

# print(solve.roster)

# #entries=[RosterEntry(skills=['account_services', 'floral'], count=3), 
# # RosterEntry(skills=['account_services', 'bakery'], count=5), 
# # RosterEntry(skills=['account_services', 'escalations'], count=7),
# # RosterEntry(skills=['account_services'], count=16), 
# # RosterEntry(skills=['online_orders', 'photo'], count=7), 
# # RosterEntry(skills=['online_orders', 'bakery'], count=1), 
# # RosterEntry(skills=['online_orders', 'escalations'], count=2), 
# # RosterEntry(skills=['online_orders'], count=13)]

# #Make a grid of subplots, one per primary(accounts,order) + secondary(floral, bakery, escalations, photo) skill
# from plotly.subplots import make_subplots

# fig = make_subplots(
#     rows=2, cols=5,
#     column_widths=[0.35, 0.16, 0.16, 0.16, 0.16],  # primary skill col wider
#     row_heights=[0.5, 0.5],
#     subplot_titles=[
#         "Account Services", "+ Photo", "+ Floral", "+ Bakery", "+ Escalations",
#         "Online Orders", "+ Photo", "+ Floral", "+ Bakery", "+ Escalations"
#     ],
#     vertical_spacing=0.08,
# )
# for i, entry in enumerate(solve.roster.entries):
#     primary = entry.skills[0]
#     secondary = entry.skills[1] if len(entry.skills) > 1 else "none"
#     row = 1 if primary == "account_services" else 2
#     col = {
#         "none": 1,
#         "photo": 2,
#         "floral": 3,
#         "bakery": 4,
#         "escalations": 5
#     }[secondary]
#     if secondary == "none":
#         cols = 10
#     else:
#         cols = 5
#     xs, ys = make_grid_coords(entry.count, cols=cols)
#     fig.add_trace(go.Scatter(x=xs, y=ys, mode="markers", marker_size=20, marker_symbol="square"), row=row, col=col)
#     #Set axes - manual for now, y is 0 to -3, x is 0 to 4 - except primary skills, those have double x axis
#     if secondary == "none":
#         fig.update_xaxes(range=[-0.5, 9.5], row=row, col=col)
#     else:
#         fig.update_xaxes(range=[-0.5, 4.5], row=row, col=col)
#     fig.update_yaxes(range=[-3.5, 0.5], row=row, col=col)
#     fig.update_xaxes(visible=False)
#     fig.update_yaxes(visible=False)
# fig.update_layout(template="seaborn", showlegend=False, height=600, width=1000)

# fig.write_html("roster_dev.html")


# # import plotly.graph_objects as go

# # hours = list(range(8, 20))
# # skills = ["all", "account_services", "online_orders", "escalations"]

# # volume = {
# #     "all":              [120, 180, 240, 290, 310, 295, 280, 260, 230, 200, 160, 110],
# #     "account_services": [ 60,  90, 120, 140, 150, 140, 130, 120, 110,  90,  70,  50],
# #     "online_orders":    [ 45,  65,  90, 110, 120, 115, 110, 100,  90,  80,  65,  45],
# #     "escalations":      [ 15,  25,  30,  40,  40,  40,  40,  40,  30,  30,  25,  15],
# # }

# # fig = go.Figure()

# # for i, skill in enumerate(skills):
# #     opacity = 1.0 if skill == "all" else 0.3
# #     fig.add_trace(go.Bar3d(
# #         x=hours,
# #         y=[i] * len(hours),
# #         z=[0] * len(hours),
# #         dx=0.8,
# #         dy=0.8,
# #         dz=volume[skill],
# #         name=skill,
# #         opacity=opacity,
# #     ))

# # fig.update_layout(
# #     title="Call Volume by Skill — Hourly",
# #     scene=dict(
# #         xaxis=dict(title="Hour"),
# #         yaxis=dict(
# #             title="Skill",
# #             tickvals=list(range(len(skills))),
# #             ticktext=skills,
# #         ),
# #         zaxis=dict(title="Volume"),
# #         camera=dict(eye=dict(x=1.8, y=-1.8, z=0.8)),
# #     ),
# #     legend=dict(title="Skill"),
# # )

# import plotly.graph_objects as go

# def make_bar(x, y, z_top, dx=0.6, dy=0.6, color="blue", opacity=1.0):
#     """Draw a single rectangular bar as a Mesh3d prism."""
#     # 8 vertices: bottom face then top face
#     x0, x1 = x, x + dx
#     y0, y1 = y, y + dy
#     z0, z1 = 0, z_top

#     vx = [x0, x1, x1, x0, x0, x1, x1, x0]
#     vy = [y0, y0, y1, y1, y0, y0, y1, y1]
#     vz = [z0, z0, z0, z0, z1, z1, z1, z1]

#     # 6 faces, each split into 2 triangles (i, j, k = vertex indices)
#     i = [0, 0, 0, 4, 4, 2]
#     j = [1, 2, 4, 5, 6, 6]
#     k = [2, 3, 5, 6, 7, 7]

#     return go.Mesh3d(
#         x=vx, y=vy, z=vz,
#         i=i, j=j, k=k,
#         color=color,
#         opacity=opacity,
#         flatshading=True,
#         showlegend=False,
#     )

# fig = go.Figure()

# fig.add_trace(make_bar(x=0, y=0, z_top=50,  color="#08519c"))
# fig.add_trace(make_bar(x=1, y=0, z_top=120, color="#08519c"))

# fig.update_layout(
#     scene=dict(
#         xaxis=dict(title="Hour"),
#         yaxis=dict(title="Skill"),
#         zaxis=dict(title="Volume"),
#         camera=dict(eye=dict(x=1.8, y=-1.8, z=0.8)),
#     ),
# )

# fig.write_html("chart_dev.html")

# import plotly.graph_objects as go

# fig = go.Figure()

# fig.add_trace(go.Bar(name="account_services", x=[8,9,10,11], y=[60,90,120,140], opacity=1.0))
# fig.add_trace(go.Bar(name="online_orders",    x=[8,9,10,11], y=[45,65,90,110],  opacity=0.2))
# fig.add_trace(go.Bar(name="escalations",      x=[8,9,10,11], y=[15,25,30,40],   opacity=0.2))

# fig.update_layout(
#     updatemenus=[dict(
#         type="buttons",
#         buttons=[
#             dict(
#                 label="Account Services",
#                 method="restyle",
#                 args=[{"opacity": [1.0, 0.2, 0.2]}],  # one value per trace
#             ),
#             dict(
#                 label="Online Orders",
#                 method="restyle",
#                 args=[{"opacity": [0.2, 1.0, 0.2]}],
#             ),
#             dict(
#                 label="Escalations",
#                 method="restyle",
#                 args=[{"opacity": [0.2, 0.2, 1.0]}],
#             ),
#         ]
#     )]
# )

# fig.write_html("chart_dev.html")



# #import plotly.graph_objects as go
# #import chainlit as cl

# # x = ["8AM", "9AM", "10AM", "11AM", "12PM", "1PM", "2PM", "3PM", "4PM", "5PM", "6PM", "7PM", "8PM"]
# # y = [4, 4, 5, 6, 7, 8, 7, 6, 5, 4, 4, 3, 2]
# # colors = ['lightslategray'] * len(x)
# # colors[3] = 'crimson'  # Highlight the 11AM slot

# # fig = go.Figure(data=[go.Bar(
# #     x=x,
# #     y=y,
# #     marker_color=colors # marker color can be a single color value or an iterable
# # )])


# # @cl.on_chat_start
# # async def start():
# #     figs = []
# #     for template in ["plotly", "plotly_white", "plotly_dark", "ggplot2", "seaborn", "simple_white", "none"]:
# #         fig.update_layout(template=template, title_text = template)
# #         figs.append(cl.Plotly(name=f"chart_{template}", figure=fig, display="inline"))    
# #     await cl.Message(content="This message has a chart", elements=figs).send()