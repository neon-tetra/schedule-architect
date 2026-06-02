import os
import asyncio
import pandas as pd
import chainlit as cl

from engine.context import ScenarioContext
from engine.dispatcher import Dispatcher
from engine.presenter import LLMPresenter
from agent.session import AgentSession
from scenarios.default import DEFAULT_COMMANDS

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _build_session() -> AgentSession:
    """Initialise engine and agent session. Runs once per user session."""
    context = ScenarioContext(name="DefaultScenario")
    dispatcher = Dispatcher(context)
    for cmd in DEFAULT_COMMANDS:
        dispatcher.dispatch(cmd)
    return AgentSession(
        dispatcher=dispatcher,
        context=context,
        api_key=os.environ["ANTHROPIC_API_KEY"],
    )


def _build_result_elements(context: ScenarioContext) -> list:
    """
    Build Chainlit elements from the current solve result.
    Returns a list of cl.Dataframe elements — one shortfall grid per skill,
    plus a summary table across all skills.
    """
    if context.solve_result is None:
        return []

    data = LLMPresenter(context.solve_result).present_json()
    elements = []

    # ── Per-skill shortfall grids (days x hours) ──────────────────────────
    for skill_id, skill_data in data["by_skill"].items():
        rows = []
        for day_name, day_data in skill_data["by_day"].items():
            row = {"Day": day_name}
            for hour_label, cell in day_data["by_hour"].items():
                sf = cell["shortfall"]
                dm = cell["demand"]
                pct = cell["shortfall_pct"]
                row[hour_label] = f"{sf} ({pct}%)" if dm > 0 else "-"
            rows.append(row)

        df = pd.DataFrame(rows).set_index("Day")
        elements.append(
            cl.Dataframe(
                data=df,
                display="inline",
                name=f"Shortfall — {skill_id}",
            )
        )

    # ── Summary table across all skills ───────────────────────────────────
    summary_rows = []
    for skill_id, skill_data in data["by_skill"].items():
        summary_rows.append({
            "Skill": skill_id,
            "Total Shortfall": skill_data["total_shortfall"],
            "Total Demand": skill_data["total_demand"],
            "Shortfall %": f"{skill_data['shortfall_pct']}%",
            "Worst Day": skill_data.get("worst_day", "-"),
        })

    summary_df = pd.DataFrame(summary_rows).set_index("Skill")
    elements.append(
        cl.Dataframe(
            data=summary_df,
            display="inline",
            name="Summary",
        )
    )

    return elements


@cl.on_chat_start
async def on_chat_start():
    session = await asyncio.to_thread(_build_session)
    cl.user_session.set("agent", session)
    await cl.Message(
        content=(
            "**Schedule Architect** ready. "
            f"Session `{session.session_id[:8]}` — "
            "scenario loaded with default queues and roster.\n\n"
            "Ask me to run the model, adjust the roster, or describe the current scenario."
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    session: AgentSession = cl.user_session.get("agent")

    async with cl.Step(name="Thinking…", type="run") as step:
        response_text = await asyncio.to_thread(session.run_turn, message.content)
        step.output = "Done"

    await cl.Message(content=response_text).send()

    # Render solve result as DataFrames if one exists
    #Rendering all side by side and without totals or headers - will revisit
    context: ScenarioContext = session._context
    elements = _build_result_elements(context)
    if elements:
        await cl.Message(
            content=f"**Solve results** — {len(elements) - 1} skill(s) + summary",
            elements=elements,
        ).send()