from engine.commands import DefineSkill, DefineCallEnvironment, DeriveErlang, DefineRoster
from engine.result import CommandResult
from engine.context import ScenarioContext


class Handler:
    """Executes commands against a ScenarioContext.
    
    Methods are grouped by command family:
        - Define:  write entities directly into context
        - Derive:  compute and write derived values into context
        - Solve:   delegate to ModelBuilder (deferred)
        - Read:    read and format results from context (deferred)
    """

    def __init__(self, context: ScenarioContext) -> None:
        self._context = context
        # self._model_builder = ModelBuilder()  # Deferred

    # ── Define ────────────────────────────────────────────────────────────────

    def handle_define_skill(self, cmd: DefineSkill) -> CommandResult:
        raise NotImplementedError

    def handle_define_environment(self, cmd: DefineCallEnvironment) -> CommandResult:
        raise NotImplementedError

    # ── Derive ────────────────────────────────────────────────────────────────

    def handle_derive_erlang(self, cmd: DeriveErlang) -> CommandResult:
        raise NotImplementedError

    def handle_define_roster(self, cmd: DefineRoster) -> CommandResult:
        raise NotImplementedError

    # ── Solve (deferred) ──────────────────────────────────────────────────────

    # def handle_solve(self, cmd: Solve) -> CommandResult: ...

    # ── Read (deferred) ───────────────────────────────────────────────────────

    # def handle_read_result(self, cmd: ReadResult) -> CommandResult: ...
    # def handle_read_context(self, cmd: ReadContext) -> CommandResult: ...