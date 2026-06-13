from __future__ import annotations
from collections import defaultdict
from pydantic import BaseModel


class SlotMatrix(BaseModel):
    """A (day, slot, skill_id) -> int mapping representing one week of per-slot values.

    Used for demand (Erlang requirements), supply (staffed agents),
    and shortfall (unmet demand). All three share the same shape.
    """

    label: str
    values: dict[tuple[int, int, str], int]

    def get(self, day: int, slot: int, skill: str) -> int:
        return self.values.get((day, slot, skill), 0)

    def sum(self) -> int:
        return sum(self.values.values())

    def collapse_to_hours(self, agg: str = "sum") -> "SlotMatrix":
        """Bucket 30-min slots into hours by slot // 2.

        agg="sum"  — use for shortfall (cumulative gap across the hour)
        agg="max"  — use for demand and supply (peak headcount within the hour)
        """
        hourly: dict[tuple[int, int, str], int] = defaultdict(int)

        if agg == "sum":
            for (day, slot, skill), val in self.values.items():
                hourly[(day, slot // 2, skill)] += val
        elif agg == "max":
            for (day, slot, skill), val in self.values.items():
                key = (day, slot // 2, skill)
                hourly[key] = max(hourly[key], val)
        else:
            raise ValueError(f"Unknown aggregation '{agg}': use 'sum' or 'max'.")

        return SlotMatrix(label=self.label, values=dict(hourly))

    def skills(self) -> set[str]:
        """Return the set of skill_ids present in this matrix."""
        return {skill_id for (_, _, skill_id) in self.values.keys()}

    def __sub__(self, other: SlotMatrix) -> SlotMatrix:
        all_keys = self.values.keys() | other.values.keys()
        return SlotMatrix(
            label=f"{self.label}_minus_{other.label}",
            values={
                k: max(0, self.values.get(k, 0) - other.values.get(k, 0))
                for k in all_keys
            },
        )
