from pydantic import BaseModel
from domain import QueueProfile, SlotMatrix, Roster
from engine.solve_result import SolveResult


class ScenarioContext(BaseModel):
    """Shared mutable state for a single scheduling scenario.

    Built piece by piece via Define/Derive commands before solve is invoked.
    Each field is optional — completeness is validated at solve time.
    """

    name: str = "DefaultScenario"

    queues: dict[str, QueueProfile] = {}       # keyed by skill_id
    demand: SlotMatrix | None = None  #Revisit this - demand, supply, shortfall, future matrices 
                                      #all the same shape - implies ownership under queue profile?
    current_roster: Roster | None = None

    # Deferred
    # schedule_types: dict[str, ScheduleType] = {}
    solve_result: SolveResult | None = None

    def invalidate_solve_results(self) -> None:
        self.solve_result = None

    # Deferred
    # def is_ready_to_solve(self) -> bool: ...