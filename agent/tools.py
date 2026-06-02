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
    Wraps engine Commands as @beta_tool decorated functions for use
    with the Anthropic tool_runner. Each tool is defined as a closure
    inside get_tools() so that @beta_tool sees a clean signature without
    'self', while still capturing self._dispatcher from the enclosing scope.

    Docstrings on each function are the agent-facing descriptions
    Claude uses to decide when to call each tool.
    """

    def __init__(self, dispatcher: Dispatcher):
        self._dispatcher = dispatcher

    def get_tools(self) -> list:
        """Build and return the list of beta_tool decorated functions exposed to the agent."""

        @beta_tool
        def define_queue_profile(
            skill_id: str,
            weekly_volume: float,
            aht_seconds: float,
            aht_std_seconds: float,
            operating_hours: tuple,
            day_weights: list,
            interval_weights: list,
            monthly_cost: float = 0.0,
        ) -> str:
            """Define a queue profile for a skill including volume, handle time, operating hours, and monthly cost per agent."""
            cmd = DefineQueueProfile(
                skill_id=skill_id,
                weekly_volume=weekly_volume,
                aht_seconds=aht_seconds,
                aht_std_seconds=aht_std_seconds,
                operating_hours=operating_hours,
                day_weights=day_weights,
                interval_weights=interval_weights,
                monthly_cost=monthly_cost,
            )
            result = self._dispatcher.dispatch(cmd)
            return json.dumps({"success": result.success, "message": result.message})

        @beta_tool
        def derive_erlang(
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
            entries: list,
        ) -> str:
            """
            Define the agent roster. entries is a list of objects with:
              - skills: list of skill_id strings the agent group covers
              - count: number of agents in this group
            Example: [{"skills": ["account_services", "escalations"], "count": 4}]
            Each agent may have exactly one primary skill (account_services or online_orders)
            and at most one secondary skill (photo, floral, bakery, or escalations).
            """
            roster_entries = [RosterEntry(**e) for e in entries]
            cmd = DefineRoster(entries=roster_entries)
            result = self._dispatcher.dispatch(cmd)
            return json.dumps({"success": result.success, "message": result.message})

        @beta_tool
        def solve() -> str:
            """Run the CP-SAT optimisation solver against the current queues, demand, and roster."""
            result = self._dispatcher.dispatch(Solve())
            return json.dumps({"success": result.success, "message": result.message})

        @beta_tool
        def read_result() -> str:
            """Read and return the current solve result as a formatted presentation including shortfall by skill."""
            result = self._dispatcher.dispatch(ReadResult())
            return json.dumps({"success": result.success, "message": result.message, **(result.data or {})})

        return [define_queue_profile, derive_erlang, define_roster, solve, read_result]