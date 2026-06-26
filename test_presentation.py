""" from solver.shifts import generate_variants, SolvedSchedule
AGENT_UPPER_BOUND    = 20
VALID_SHIFT_STARTS   = [8, 9, 10, 11]   # hours; *2 to convert to slots
SHIFT_DURATION_SLOTS = 17
DAYS                 = range(0, 7)
SLOTS                = range(0, 48)
VALID_OFF_PATTERNS   = [(0,1),(1,2),(2,3),(3,4),(4,5),(5,6),(6,0)]
SCALED_UB = AGENT_UPPER_BOUND * 2
variants = generate_variants(VALID_SHIFT_STARTS, SHIFT_DURATION_SLOTS)
print(f"Generated {len(variants)} variants:")


from agent.toolkit import Toolkit
toolkit = Toolkit()
toolkit.execute("run_solve", {"label": "Test_Initial_Run"})
solve = toolkit._context._solves[0]
from presentation import theme
from presentation.volume_chart import build_volume_chart
fig = build_volume_chart(solve, "bakery","tuesday")
#write html
fig.write_html("volume_chart.html", include_plotlyjs="cdn", full_html=True, auto_play=False) """


from agent.toolkit import Toolkit
toolkit = Toolkit()

toolkit.execute("run_solve", {"label": "Test_Initial_Run"})
from collections import defaultdict

solve_run = toolkit._context._solves[0]
vr = solve_run.var_registry

#output solve dfinterval to csv
df = solve_run.df_interval
df.to_csv("solve_df_interval.csv", index=False)

