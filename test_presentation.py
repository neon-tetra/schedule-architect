
from agent.toolkit import Toolkit
toolkit = Toolkit()
toolkit.execute("run_solve", {"label": "Test_Initial_Run"})
solve = toolkit._context._solves[0]
from presentation import theme
from presentation.volume_chart import build_volume_chart
fig = build_volume_chart(solve, "bakery","tuesday")
#write html
fig.write_html("volume_chart.html", include_plotlyjs="cdn", full_html=True, auto_play=False)