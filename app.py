import os
import asyncio
import chainlit as cl

from engine.dispatcher import Dispatcher
from engine.context import ScenarioContext
from agent.session import AgentSession
from scenarios.default import DEFAULT_COMMANDS


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
        response_text = await session.run_turn(message.content)
        step.output = "Done"

    await cl.Message(content=response_text).send()