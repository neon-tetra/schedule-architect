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
        raw_queue      = asyncio.Queue()
        queue          = DebugLogger(raw_queue)
        context        = ScenarioContext(DEFAULT_PROFILES, DEFAULT_ROSTER)
        toolkit        = Toolkit(context)
        session        = AgentSession(context)
        self._mediator = MediatorLoop(queue, session, context)
        asyncio.create_task(self._mediator.run())

    async def send(self, text: str):
        await self._mediator.queue.put(Event(
            source=EventSource.CHAINLIT,
            type=EventType.USER_MESSAGE,
            data={"text": text}
        ))