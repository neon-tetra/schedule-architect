from __future__ import annotations
from pydantic import BaseModel
from typing import Union, Literal
from domain import RosterEntry


class DefineSkill(BaseModel):
    """Define a named skill in the scenario context."""
    type: Literal["define_skill"] = "define_skill"
    id: str
    name: str


class DefineCallEnvironment(BaseModel):
    """Define call volume and distribution characteristics for a skill."""
    type: Literal["define_call_environment"] = "define_call_environment"
    skill_id: str
    weekly_volume: float
    aht_seconds: float
    aht_std_seconds: float
    operating_hours: tuple[int, int] = (8, 20)
    day_weights: list[float]
    interval_weights: list[float]


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


class ReadResult(BaseModel):
    """Return a formatted presentation of the current solve result."""
    type: Literal["read_result"] = "read_result"


# Deferred
# class ReadContext(BaseModel):
#     type: Literal["read_context"] = "read_context"


ModelCommand = Union[
    DefineSkill,
    DefineCallEnvironment,
    DeriveErlang,
    DefineRoster,
    Solve,
    ReadResult,
]