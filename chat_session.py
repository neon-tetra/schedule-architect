import asyncio
from debug_logger import DebugLogger
from mediator import MediatorLoop
from events import Event, EventSource, EventType

class ChatSession:

    def __init__(self):
        raw_queue        = asyncio.Queue()
        self._queue      = DebugLogger(raw_queue)
        self._mediator   = MediatorLoop(self._queue)
        asyncio.create_task(self._mediator.run())

    async def send(self, text: str):
        await self._queue.put(Event(
            source=EventSource.CHAINLIT,
            type=EventType.USER_MESSAGE,
            data={"text": text}
        ))