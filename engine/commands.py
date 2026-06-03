from __future__ import annotations
from pydantic import BaseModel
from typing import Union, Literal
from domain import RosterEntry


class DefineQueueProfile(BaseModel):
    """Define call volume and distribution characteristics for a skill/queue."""
    type: Literal["define_queue_profile"] = "define_queue_profile"
    skill_id: str
    weekly_volume: float
    aht_seconds: float
    aht_std_seconds: float
    operating_hours: tuple[int, int] = (8, 20)
    day_weights: list[float]
    interval_weights: list[float]
    monthly_cost: float
    


class DeriveErlang(BaseModel):
    """Derive Erlang C staffing requirements from the current queue profiles."""
    type: Literal["derive_erlang"] = "derive_erlang"
    target_sl: float = 0.80
    answer_within_seconds: float = 20.0
    shrinkage: float = 0.20


class DefineRoster(BaseModel):
    """Define an agent roster directly."""
    type: Literal["define_roster"] = "define_roster"
    entries: list[RosterEntry]


class Solve(BaseModel):
    """Invoke the CP-SAT solver against the current context."""
    type: Literal["solve"] = "solve"


# Deferred
# class ReadContext(BaseModel):
#     type: Literal["read_context"] = "read_context"


ModelCommand = Union[
    DefineQueueProfile,
    DeriveErlang,
    DefineRoster,
    Solve,
]