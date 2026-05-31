from __future__ import annotations

from collections import defaultdict
from pydantic import BaseModel


class SlotMatrix(BaseModel):
    label: str
    values: dict[tuple[int, int, str], int]  # (day, slot, skill_id) -> int

    def get(self, day: int, slot: int, skill: str) -> int:
        return self.values.get((day, slot, skill), 0)

    def sum(self) -> int:
        return sum(self.values.values())

    def collapse_to_hours(self) -> "SlotMatrix":
        """Bucket 30-min slots into hours by slot // 2. Values are summed."""
        hourly: dict[tuple[int, int, str], int] = defaultdict(int)
        for (day, slot, skill), val in self.values.items():
            hourly[(day, slot // 2, skill)] += val
        return SlotMatrix(label=self.label, values=dict(hourly))

    def __sub__(self, other: "SlotMatrix") -> "SlotMatrix":
        all_keys = self.values.keys() | other.values.keys()
        return SlotMatrix(
            label=f"{self.label}_minus_{other.label}",
            values={
                k: max(0, self.values.get(k, 0) - other.values.get(k, 0))
                for k in all_keys
            },
        )

    class Config:
        arbitrary_types_allowed = True
