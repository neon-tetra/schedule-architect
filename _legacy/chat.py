import asyncio
import os
from engine.context import ScenarioContext
from engine.dispatcher import Dispatcher
from agent.session import AgentSession
from scenarios.default import DEFAULT_COMMANDS


async def main():
    context = ScenarioContext(name="DefaultScenario")
    dispatcher = Dispatcher(context)

    for cmd in DEFAULT_COMMANDS:
        dispatcher.dispatch(cmd)

    session = AgentSession(
        dispatcher=dispatcher,
        context=context,
        api_key=os.environ["ANTHROPIC_API_KEY"],
    )

    print(f"Session {session.session_id} ready. Type 'quit' to exit.\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("quit", "exit"):
            break
        if not user_input:
            continue
        response = await session.run_turn(user_input)
        print(f"\nAssistant: {response}\n")


if __name__ == "__main__":
    asyncio.run(main())