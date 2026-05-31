from pydantic import BaseModel
from domain import Skill, QueueProfile, SlotMatrix, Roster, ScheduleType, SolveResult


class ScenarioContext(BaseModel):
    """Shared mutable state for a single scheduling scenario.

    Built piece by piece via Define/Derive commands before solve is invoked.
    Each field is optional — completeness is validated at solve time.
    """

    name: str = "DefaultScenario"

    # Defined entities
    skills: dict[str, Skill] = {}
    queues: dict[str, QueueProfile] = {}  # keyed by skill_id

    # Derived
    demand: SlotMatrix | None = None
    current_roster: Roster | None = None

    # Named registry — explicit output_id references
    registry: dict[str, SlotMatrix | Roster] = {}

    # Deferred
    # schedule_types: dict[str, ScheduleType] = {}
    solve_result: SolveResult | None = None

    class Config:
        arbitrary_types_allowed = True

    def invalidate_solve_results(self) -> None:
        """Clear any existing solve output. Called before any Define/Derive command."""
        self.solve_result = None

    # Deferred
    # def is_ready_to_solve(self) -> bool: ...
