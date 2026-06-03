import asyncio
import json

import chainlit as cl
import plotly.graph_objects as go
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
from engine.context import ScenarioContext
from engine.presenter import LLMPresenter

class AgentTools:
    """
    Wraps engine Commands as @beta_tool decorated functions for use
    with the Anthropic tool_runner. Each tool is defined as a closure
    inside get_tools() so that @beta_tool sees a clean signature without
    'self', while still capturing self._dispatcher from the enclosing scope.

    Docstrings on each function are the agent-facing descriptions
    Claude uses to decide when to call each tool.
    """

    def __init__(self, dispatcher: Dispatcher, context: ScenarioContext):
        self._dispatcher = dispatcher
        self._context = context

    def _build_chart_figure(self, chart_type: str):
        data = LLMPresenter(self._context.solve_result).present_json()
        by_skill = sorted(data["by_skill"].items())
        skills = [skill_id for skill_id, _ in by_skill]

        if chart_type == "shortfall_by_skill":
            values = [skill_data["total_shortfall"] for _, skill_data in by_skill]
            fig = go.Figure(data=[go.Bar(x=skills, y=values, name="Shortfall")])
            fig.update_layout(
                title="Total shortfall by skill",
                xaxis_title="Skill",
                yaxis_title="Agent-intervals",
            )
            return fig

        if chart_type == "shortfall_pct_by_skill":
            values = [skill_data["shortfall_pct"] for _, skill_data in by_skill]
            fig = go.Figure(data=[go.Bar(x=skills, y=values, name="Shortfall %")])
            fig.update_layout(
                title="Shortfall percentage by skill",
                xaxis_title="Skill",
                yaxis_title="Shortfall %",
            )
            return fig

        if chart_type == "demand_vs_shortfall":
            demand = [skill_data["total_demand"] for _, skill_data in by_skill]
            shortfall = [skill_data["total_shortfall"] for _, skill_data in by_skill]
            fig = go.Figure(
                data=[
                    go.Bar(x=skills, y=demand, name="Demand"),
                    go.Bar(x=skills, y=shortfall, name="Shortfall"),
                ]
            )
            fig.update_layout(
                barmode="group",
                title="Demand versus shortfall by skill",
                xaxis_title="Skill",
                yaxis_title="Agent-intervals",
            )
            return fig

        raise ValueError(
            "Unsupported chart_type. Use one of: shortfall_by_skill, "
            "shortfall_pct_by_skill, demand_vs_shortfall."
        )

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
        async def solve() -> str:
            """Run the CP-SAT optimisation solver against the current queues, demand, and roster."""
            result = await asyncio.to_thread(self._dispatcher.dispatch, Solve())
            return json.dumps({"success": result.success, "message": result.message})

        @beta_tool
        def read_result() -> str:
            """Read and return the current solve result including shortfall by skill, demand, 
            and monthly roster cost. Returns full day-by-hour breakdown per skill."""
            result = self._dispatcher.dispatch(ReadResult())
            if not result.success:
                return json.dumps({"success": False, "message": result.message})
            return json.dumps({"success": True, **(result.data.get("result", {}))})

        @beta_tool
        async def show(
            chart_type: str = "shortfall_by_skill",
            result_label: str | None = None,
        ) -> str:
            """
            Render and send an inline Plotly chart for the current solve result.
            Supported chart_type values: shortfall_by_skill, shortfall_pct_by_skill,
            demand_vs_shortfall.
            """
            if self._context.solve_result is None:
                return json.dumps({"chart_sent": False, "message": "No solve result available. Run solve first."})

            result_label = result_label or "current"
            if result_label != "current":
                return json.dumps({
                    "chart_sent": False,
                    "message": f"Result label '{result_label}' is not available in this session.",
                })

            try:
                fig = self._build_chart_figure(chart_type)
            except ValueError as exc:
                return json.dumps({"chart_sent": False, "message": str(exc)})

            await cl.Message(
                content="",
                elements=[cl.Plotly(name=chart_type, figure=fig, display="inline")]
            ).send()

            return json.dumps({"chart_sent": True, "chart_type": chart_type, "label": result_label})

        @beta_tool
        def read_roster() -> str:
            """Read the current roster composition — agent groups, skill combinations, 
            headcount per group, per-agent cost, and total monthly cost."""
            roster = self._context.current_roster
            queues = self._context.queues
            if roster is None:
                return json.dumps({"success": False, "message": "No roster defined."})
            entries = [
                {
                    "skills": e.skills,
                    "count": e.count,
                    "monthly_cost_per_agent": e.monthly_cost(queues) if queues else None,
                }
                for e in roster.entries
            ]
            total_cost = roster.total_monthly_cost(queues) if queues else None
            return json.dumps({
                "success": True,
                "total_agents": roster.total_agents,
                "monthly_cost": total_cost,
                "entries": entries,
            })
        return [define_queue_profile, derive_erlang, define_roster, solve, read_result, show, read_roster]