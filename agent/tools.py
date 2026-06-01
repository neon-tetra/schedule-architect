from anthropic import beta_tool
from engine.dispatcher import Dispatcher
from engine.commands import (
    DefineQueueProfile,
    DeriveErlang,
    DefineRoster,
    Solve,
    ReadResult,
)


class AgentTools:
    """
    Wraps engine Commands as @beta_tool decorated methods for use
    with the Anthropic tool_runner. Each method:
      - accepts the same arguments as the corresponding Command
      - constructs the Command
      - calls dispatcher.dispatch(cmd)
      - returns json.dumps(result.data)

    Docstrings on each method are the agent-facing descriptions
    Claude uses to decide when to call each tool.
    """

    _dispatcher: Dispatcher

    def get_tools(self) -> list:
        """Return the list of decorated tools exposed to the agent."""
        pass

    @beta_tool
    def define_queue_profile(
        self,
        skill_id: str,
        weekly_volume: float,
        aht_seconds: float,
        aht_std_seconds: float,
        operating_hours: tuple,
        day_weights: list,
        interval_weights: list,
    ) -> str:
        """Define a queue profile for a skill including volume, handle time, and operating hours."""
        pass

    @beta_tool
    def derive_erlang(
        self,
        target_sl: float,
        answer_within_seconds: float,
        shrinkage: float,
    ) -> str:
        """Derive per-slot staffing demand for all queues using Erlang C."""
        pass

    @beta_tool
    def define_roster(self, entries: list) -> str:
        """Define the agent roster including shift patterns and skill assignments."""
        pass

    @beta_tool
    def solve(self) -> str:
        """Run the optimisation solver against current queues, demand and roster."""
        pass

    @beta_tool
    def read_result(self) -> str:
        """Read and return the current solve result in a formatted presentation."""
        pass
