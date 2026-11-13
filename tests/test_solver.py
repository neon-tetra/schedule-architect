"""
test_solver.py — isolated smoke test for solver/scheduler.py.

Exercises exactly the roster -> Erlang C -> build_and_solve path that
Toolkit._run_solve uses, but stops short of the SolveRun/Toolkit wiring
(currently mid-rework — see core/solve_run.py vs build_and_solve's actual
return shape). Lets solver changes (hints, slot resolution, etc.) be tested
without tripping over that unrelated integration gap.

Run: pytest tests/test_solver.py
"""
import polars as pl
import pytest

from core.frames import INTERVAL_SCHEMA
from core.scenarios.default import DF_QUEUE_PROFILES, DF_STARTING_ROSTER
from solver.erlang import ErlangC


def _build_intervals() -> pl.DataFrame:
    df_intervals = pl.DataFrame(schema=INTERVAL_SCHEMA)
    for profile in DF_QUEUE_PROFILES.iter_rows(named=True):
        curve = ErlangC.requirements_curve(env=profile)
        df_intervals = df_intervals.vstack(curve)
    return df_intervals


def test_erlang_intervals():
    df_intervals = _build_intervals()
    assert df_intervals.height > 0
    assert df_intervals.schema.keys() == INTERVAL_SCHEMA.keys()


def test_build_and_solve():
    # solver.scheduler needs the external `dfor` project (see CLAUDE.md) and is
    # mid-rework, so it may not import; skip rather than fail in that case.
    try:
        from solver.scheduler import build_and_solve
    except ImportError as exc:
        pytest.skip(f"solver.scheduler not importable here: {exc}")

    result = build_and_solve(
        roster=DF_STARTING_ROSTER,
        queues=DF_QUEUE_PROFILES,
        intervals=_build_intervals(),
    )
    assert result is not None
