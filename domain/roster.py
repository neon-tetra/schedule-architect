from __future__ import annotations
from typing import TYPE_CHECKING
from pydantic import BaseModel

if TYPE_CHECKING:
    from domain.queue_profile import QueueProfile


class RosterEntry(BaseModel):
    """A single agent archetype — a skill set and a headcount."""

    skills: list[str]
    count: int

    @classmethod
    def from_string(cls, s: str) -> RosterEntry:
        """Parse a compact string representation e.g. 'billing,collections:4'."""
        raise NotImplementedError

    def monthly_cost(self, queues: dict[str, QueueProfile]) -> float:
        return sum(queues[s].monthly_cost for s in self.skills if s in queues)


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
            if queues:
                cost_per = e.monthly_cost(queues)
                line_total = cost_per * e.count
                lines.append(f"  {e.count:>3}x  {skill_str:<45}  ${cost_per:>6,.0f}/agent   ${line_total:>8,.0f}/mo")
            else:
                lines.append(f"  {e.count:>3}x  {skill_str}")
        return "\n".join(lines)

    def total_monthly_cost(self, queues: dict[str, QueueProfile]) -> float:
        return sum(e.monthly_cost(queues) * e.count for e in self.entries)