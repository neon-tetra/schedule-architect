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
print(solve.df)

# import plotly.graph_objects as go
# import chainlit as cl

# x = ["8AM", "9AM", "10AM", "11AM", "12PM", "1PM", "2PM", "3PM", "4PM", "5PM", "6PM", "7PM", "8PM"]
# y = [4, 4, 5, 6, 7, 8, 7, 6, 5, 4, 4, 3, 2]
# colors = ['lightslategray'] * len(x)
# colors[3] = 'crimson'  # Highlight the 11AM slot

# fig = go.Figure(data=[go.Bar(
#     x=x,
#     y=y,
#     marker_color=colors # marker color can be a single color value or an iterable
# )])


# @cl.on_chat_start
# async def start():
#     figs = []
#     for template in ["plotly", "plotly_white", "plotly_dark", "ggplot2", "seaborn", "simple_white", "none"]:
#         fig.update_layout(template=template, title_text = template)
#         figs.append(cl.Plotly(name=f"chart_{template}", figure=fig, display="inline"))    
#     await cl.Message(content="This message has a chart", elements=figs).send()