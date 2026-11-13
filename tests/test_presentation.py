"""
test_presentation.py — smoke test for the presentation layer.

The presentation modules take a SolveRun produced by Toolkit's run_solve, so the
end-to-end check needs the solver (external `dfor` project, see CLAUDE.md) and
is skipped when solver.scheduler cannot be imported.
"""
import pytest


def test_presentation_modules_import():
    from presentation import theme
    from presentation.kpi_chart import build_kpi_chart
    from presentation.volume_chart import build_volume_chart

    assert callable(build_kpi_chart)
    assert callable(build_volume_chart)
    assert theme.SKILL_ORDER_RAW


def test_volume_chart_from_solve():
    try:
        from agent.toolkit import Toolkit
    except ImportError as exc:
        pytest.skip(f"solver not importable here: {exc}")

    toolkit = Toolkit()
    toolkit.execute("run_solve", {"label": "Test_Initial_Run"})
    solve_run = toolkit._context._solves[0]

    from presentation.volume_chart import build_volume_chart

    fig = build_volume_chart(solve_run, "bakery", "tuesday")
    assert fig.data
