import asyncio
from debug_logger import DebugLogger
from mediator import MediatorLoop
from scenario_context import ScenarioContext
from events import Event, EventSource, EventType
from scenarios.default import DEFAULT_PROFILES, DEFAULT_ROSTER
from toolkit import Toolkit
from agent_session import AgentSession

class ChatSession:

    def __init__(self):
        self._queue    = asyncio.Queue()
        context  = ScenarioContext(DEFAULT_PROFILES, DEFAULT_ROSTER)
        toolkit  = Toolkit(context)
        session  = AgentSession(context, toolkit)
        mediator = MediatorLoop(self._queue, session, context)
        asyncio.create_task(mediator.run())

    async def send(self, text: str):
        await self._queue.put(Event(
            source=EventSource.CHAINLIT,
            type=EventType.USER_MESSAGE,
            data={"text": text}
        ))