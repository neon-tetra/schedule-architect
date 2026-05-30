from engine.commands import (
    ModelCommand,
    DefineSkill,
    DefineCallEnvironment,
    DeriveErlang,
    DefineRoster,
    Solve,
)
from engine.result import CommandResult
from engine.context import ScenarioContext
from engine.handler import Handler


class Dispatcher:
    """Thin router — receives a ModelCommand and delegates to the correct Handler method.
    
    Never touches ScenarioContext directly. All logic lives in Handler.
    """

    def __init__(self, context: ScenarioContext) -> None:
        self._handler = Handler(context)
        self._dispatch_table: dict[str, callable] = {
            "define_skill":            self._handler.handle_define_skill,
            "define_call_environment": self._handler.handle_define_environment,
            "derive_erlang":           self._handler.handle_derive_erlang,
            "define_roster":           self._handler.handle_define_roster,
            "solve":                  self._handler.handle_solve,
            # Deferred:
            # "read_result":  self._handler.handle_read_result,
            # "read_context": self._handler.handle_read_context,
        }

    def dispatch(self, cmd: ModelCommand) -> CommandResult:
        handler_fn = self._dispatch_table.get(cmd.type)
        if handler_fn is None:
            return CommandResult.fail(f"Unknown command type: '{cmd.type}'")
        return handler_fn(cmd)