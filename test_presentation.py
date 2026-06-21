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
solver = solve_run.solver  # assuming you stored CpSolver on SolveRun

# 1) Which schedule variant got picked per agent?
print("\n=== Chosen schedule variant per agent ===")
agents = sorted({m["agent"] for _, m in vr.items() if m.get("type") == "schedule_variant"})
for a in agents[:5]:
    z_vars = vr.query(type="schedule_variant", agent=a)
    chosen = []
    for v in z_vars:
        if solver.Value(v) == 1:
            md = vr.meta(v)  # or however you retrieve metadata for a var
            chosen.append(md["schedule_variant"])
    print(a, chosen)

# 2) First agent: day/slot present + intensity + skill picks
a = agents[0]
print(f"\n=== Detail for agent {a} ===")
for d in range(7):
    rows = []
    for sl in range(48):
        p = solver.Value(vr.get(type="agent_slot_present", agent=a, day=d, slot=sl))
        inten = solver.Value(vr.get(type="agent_slot_intensity", agent=a, day=d, slot=sl))
        skill_vars = vr.query(type="agent_skill_slot_present", agent=a, day=d, slot=sl)
        chosen_skills = []
        for sv in skill_vars:
            if solver.Value(sv) == 1:
                chosen_skills.append(vr.meta(sv)["skill"])
        rows.append((sl, p, inten, chosen_skills))
    print(f"Day {d}:")
    print(rows)

# 3) Global invariant checks
print("\n=== Invariant checks ===")
viol = 0
for a in agents:
    for d in range(7):
        for sl in range(48):
            p = solver.Value(vr.get(type="agent_slot_present", agent=a, day=d, slot=sl))
            inten = solver.Value(vr.get(type="agent_slot_intensity", agent=a, day=d, slot=sl))
            skill_vars = vr.query(type="agent_skill_slot_present", agent=a, day=d, slot=sl)
            s = sum(solver.Value(x) for x in skill_vars)
            if s != p:
                viol += 1
            if p == 0 and inten != 0:
                print("WARN absent but intensity>0", a, d, sl, inten)
print("violations:", viol)