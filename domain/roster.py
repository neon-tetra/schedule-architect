from __future__ import annotations
from pydantic import BaseModel


class RosterEntry(BaseModel):
    """A single agent archetype — a skill set and a headcount."""

    skills: list[str]
    count: int

    @classmethod
    def from_string(cls, s: str) -> RosterEntry:
        """Parse a compact string representation e.g. 'billing,collections:4'."""
        raise NotImplementedError


class Roster(BaseModel):
    """A full agent roster composed of one or more RosterEntry archetypes."""

    entries: list[RosterEntry]

    @property
    def total_agents(self) -> int:
        """Sum of headcount across all entries."""
        return sum(e.count for e in self.entries)

    @classmethod
    def from_string(cls, s: str) -> Roster:
        """Parse a multi-line compact string representation."""
        raise NotImplementedError

    def summary(self) -> str:
        """Return a human-readable summary of the roster."""
        raise NotImplementedError