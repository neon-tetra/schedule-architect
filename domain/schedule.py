from __future__ import annotations
from pydantic import BaseModel


class ScheduleType(BaseModel):
    """A named shift template defining which intervals are covered. Deferred."""

    id: str
    name: str

    # Deferred
    # start_slot: int
    # end_slot: int
    # covered_slots: list[int]

    # def label(self) -> str: ...


class ScheduleResult(BaseModel):
    """Summary output of a completed solve run.
    
    status reflects the CP-SAT solver outcome.
    Performance metrics are computed post-solve from actual scheduled agents
    by re-evaluating ErlangC.service_level() per slot — not stored in the model.
    """

    status: str                          # "OPTIMAL", "FEASIBLE", "INFEASIBLE"
    total_agent_slots: int               # total scheduled agent-slots across the week
    solve_time_seconds: float
    coverage_shortfall_slots: int        # slots where erlang minimum could not be met
    mean_awt_seconds: float              # demand-weighted average wait time across all slots/skills
    sl_by_skill: dict[str, float]        # achieved weekly service level per skill_id