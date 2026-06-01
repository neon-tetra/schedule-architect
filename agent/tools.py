import json

from anthropic import beta_tool
from engine.dispatcher import Dispatcher
from engine.commands import (
    DefineQueueProfile,
    DeriveErlang,
    DefineRoster,
    Solve,
    ReadResult,
)
from domain.roster import RosterEntry


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

    def __init__(self, dispatcher: Dispatcher):
        self._dispatcher = dispatcher

    def get_tools(self) -> list:
        """Return the list of decorated tool methods exposed to the agent."""
        return [
            self.define_queue_profile,
            self.derive_erlang,
            self.define_roster,
            self.solve,
            self.read_result,
        ]

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
        cmd = DefineQueueProfile(
            skill_id=skill_id,
            weekly_volume=weekly_volume,
            aht_seconds=aht_seconds,
            aht_std_seconds=aht_std_seconds,
            operating_hours=operating_hours,
            day_weights=day_weights,
            interval_weights=interval_weights,
        )
        result = self._dispatcher.dispatch(cmd)
        return json.dumps({"success": result.success, "message": result.message})

    @beta_tool
    def derive_erlang(
        self,
        target_sl: float,
        answer_within_seconds: float,
        shrinkage: float,
    ) -> str:
        """Derive per-slot staffing demand for all queues using Erlang C."""
        cmd = DeriveErlang(
            target_sl=target_sl,
            answer_within_seconds=answer_within_seconds,
            shrinkage=shrinkage,
        )
        result = self._dispatcher.dispatch(cmd)
        return json.dumps({"success": result.success, "message": result.message})

    @beta_tool
    def define_roster(
        self,
        entries: list,
    ) -> str:
        """
        Define the agent roster. entries is a list of objects with:
          - skills: list of skill_id strings the agent group covers
          - count: number of agents in this group
        Example: [{"skills": ["billing", "collections"], "count": 4}]
        """
        roster_entries = [RosterEntry(**e) for e in entries]
        cmd = DefineRoster(entries=roster_entries)
        result = self._dispatcher.dispatch(cmd)
        return json.dumps({"success": result.success, "message": result.message})

    @beta_tool
    def solve(self) -> str:
        """Run the optimisation solver against current queues, demand and roster."""
        result = self._dispatcher.dispatch(Solve())
        return json.dumps({"success": result.success, "message": result.message})

    @beta_tool
    def read_result(self) -> str:
        """Read and return the current solve result in a formatted presentation."""
        result = self._dispatcher.dispatch(ReadResult())
        return json.dumps({"success": result.success, "message": result.message, "presentation": result.data})