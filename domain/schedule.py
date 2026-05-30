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
    """Summary output of a completed solve run."""

    status: str                 # "OPTIMAL", "FEASIBLE", "INFEASIBLE"
    total_agent_slots: int      # total scheduled agent-slots across the week
    solve_time_seconds: float