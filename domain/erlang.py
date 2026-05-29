from pydantic import BaseModel


class ErlangResult(BaseModel):
    """Staffing requirements derived from Erlang C for a single skill."""

    skill_id: str
    target_sl: float
    shrinkage: float
    curve: list[list[int]]  # list of [interval_slot, agents_required] pairs

    @property
    def peak_requirement(self) -> int:
        """Highest agent requirement across all intervals."""
        if not self.curve:
            return 0
        return max(row[1] for row in self.curve)