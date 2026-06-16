from __future__ import annotations
from pydantic import BaseModel
from typing import Optional

class QueueProfile(BaseModel):
    skill_id:         str
    skill_name:       str
    weekly_volume:    float
    aht_seconds:      float
    aht_std_seconds:  float
    operating_hours:  tuple[int, int]
    day_weights:      list[float]
    interval_weights: list[float]
    monthly_cost:     float = 0.0
    target_sl:        float = 0.80
    shrinkage:        float = 0.0
    answer_within_seconds: float = 20.0

    
class RosterEntry(BaseModel):
    """A single agent archetype — a skill set and a headcount."""

    skills: list[str]
    count: int
    monthly_cost: Optional[float] = None





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

    def summary(self, queues: dict[str, QueueProfile] | None = None) -> str:
        """Return a human-readable breakdown of the roster by entry type."""
        lines = []
        for e in self.entries:
            skill_str = " + ".join(e.skills)
            lines.append(f"{skill_str}: {e.count} agents, ${e.monthly_cost:.2f}/agent/month")
        return "\n".join(lines)
    
    @property
    def total_monthly_cost(self) -> float:
        """Calculate total monthly cost of the roster."""
        return sum(e.count * e.monthly_cost for e in self.entries)