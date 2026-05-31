from __future__ import annotations
from pydantic import BaseModel

from domain.call_environment import QueueProfile
from domain.erlang import SlotMatrix
from domain.roster import Roster


class ScheduleType(BaseModel):
    """A named shift template defining which intervals are covered. Deferred."""

    id: str
    name: str

    # Deferred
    # start_slot: int
    # end_slot: int
    # covered_slots: list[int]

    # def label(self) -> str: ...


class SolveResult(BaseModel):
    status: str
    solve_time_seconds: float
    roster: Roster
    queues: dict[str, QueueProfile]
    demand: SlotMatrix
    supply: SlotMatrix
    shortfall: SlotMatrix

    class Config:
        arbitrary_types_allowed = True
