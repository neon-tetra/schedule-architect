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
    """Output of a solve run. Deferred."""

    pass