import os
import asyncio
import chainlit as cl

from engine.context import ScenarioContext
from engine.dispatcher import Dispatcher
from engine.presenter import LLMPresenter
from agent.session import AgentSession
from scenarios.default import DEFAULT_COMMANDS

#Temporary - show 'thinking' bar while agent thinks -
#need to redo session.py to get it to show tool calls and reasoning

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

    # Show a thinking indicator while the (synchronous) agent turn runs
    async with cl.Step(name="Thinking…", type="run") as step:
        response_text = await asyncio.to_thread(session.run_turn, message.content)
        step.output = "Done"

    # Send the agent's narrative response
    await cl.Message(content=response_text).send()

    # If a solve result exists on the context, render the grid as a code block
    context: ScenarioContext = session._context
    if context.solve_result is not None:
        presentation = LLMPresenter(context.solve_result).present()
        await cl.Message(
            content=f"```\n{presentation}\n```",
            language="text",
        ).send()