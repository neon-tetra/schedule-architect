"""
test_solver.py — isolated smoke test for solver/scheduler.py.

Exercises exactly the roster -> Erlang C -> build_and_solve path that
Toolkit._run_solve uses, but stops short of the SolveRun/Toolkit wiring
(currently mid-rework — see core/solve_run.py vs build_and_solve's actual
return shape). Lets solver changes (hints, slot resolution, etc.) be tested
without tripping over that unrelated integration gap.

Run: python test_solver.py
"""
import polars as pl

from core.frames import INTERVAL_SCHEMA
from core.scenarios.default import DF_QUEUE_PROFILES, DF_STARTING_ROSTER
from solver.erlang import ErlangC
from solver.scheduler import build_and_solve

df_intervals = pl.DataFrame(schema=INTERVAL_SCHEMA)
for profile in DF_QUEUE_PROFILES.iter_rows(named=True):
    curve = ErlangC.requirements_curve(env=profile)
    df_intervals = df_intervals.vstack(curve)

result = build_and_solve(
    roster=DF_STARTING_ROSTER,
    queues=DF_QUEUE_PROFILES,
    intervals=df_intervals,
)

print(result)
