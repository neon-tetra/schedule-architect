from engine.commands import (
    ModelCommand,
    DefineQueueProfile,
    DeriveErlang,
    DefineRoster,
    Solve,
)
from engine.command_result import CommandResult
from engine.context import ScenarioContext
from engine.handler import Handler
from engine.retrieval import ModelQuery, RetrievalResult


class Dispatcher:
    """Thin router — receives a ModelCommand and delegates to the correct Handler method.
    
    Never touches ScenarioContext directly. All logic lives in Handler.
    """

    def __init__(self, context: ScenarioContext) -> None:
        self._handler = Handler(context)
        self._dispatch_table: dict[str, callable] = {
            "define_queue_profile":    self._handler.handle_define_queue_profile,
            "derive_erlang":           self._handler.handle_derive_erlang,
            "define_roster":           self._handler.handle_define_roster,
            "solve":                   self._handler.handle_solve,
            # Deferred
            # "read_context": self._handler.handle_read_context,
        }
        self._retrieval_table: dict[str, callable] = {
            "query_status": self._handler.handle_query_status,
        }

    def dispatch(self, cmd: ModelCommand) -> CommandResult:
        handler_fn = self._dispatch_table.get(cmd.type)
        if handler_fn is None:
            return CommandResult.fail(f"Unknown command type: '{cmd.type}'")
        return handler_fn(cmd)

    def retrieve(self, query: ModelQuery) -> RetrievalResult:
        handler_fn = self._retrieval_table.get(query.type)
        if handler_fn is None:
            return RetrievalResult.fail(f"Unknown query type: '{query.type}'")
        return handler_fn(query)