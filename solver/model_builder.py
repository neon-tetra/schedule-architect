from engine.context import ScenarioContext
from domain import ScheduleResult


class ModelBuilder:
    """Builds and solves a CP-SAT scheduling model from a completed ScenarioContext.
    
    MVP implementation is intentionally monolithic — all model construction,
    constraint generation, and solving happens inside build_and_solve().
    Internal structure is deferred until the engine layer above it is complete.
    """

    def build_and_solve(self, context: ScenarioContext) -> ScheduleResult:
        """Read context, build CP-SAT model, solve, return result."""
        raise NotImplementedError

    # Deferred — future decomposition of build_and_solve internals:
    # def _add_variables(self) -> None: ...
    # def _add_constraints(self) -> None: ...
    # def _set_objective(self) -> None: ...