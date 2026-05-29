from pydantic import BaseModel
from domain import Skill, CallEnvironment, ErlangResult, Roster, ScheduleType, ScheduleResult


class ScenarioContext(BaseModel):
    """Shared mutable state for a single scheduling scenario.
    
    Built piece by piece via Define/Derive commands before solve is invoked.
    Each field is optional — completeness is validated at solve time.
    """

    name: str = "DefaultScenario"

    # Defined entities
    skills: dict[str, Skill] = {}
    call_environments: dict[str, CallEnvironment] = {}  # keyed by skill_id

    # Derived — implicit defaults, last derived value per skill
    current_erlang: dict[str, ErlangResult] = {}        # keyed by skill_id
    current_roster: Roster | None = None

    # Named registry — explicit output_id references
    registry: dict[str, ErlangResult | Roster] = {}

    # Deferred
    # schedule_types: dict[str, ScheduleType] = {}
    # schedule_result: ScheduleResult | None = None

    class Config:
        arbitrary_types_allowed = True

    def invalidate_solve_results(self) -> None:
        """Clear any existing solve output. Called before any Define/Derive command."""
        pass  # Deferred until ScheduleResult is implemented

    # Deferred
    # def is_ready_to_solve(self) -> bool: ...