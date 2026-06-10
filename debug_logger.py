import logging
import asyncio
from events import Event

class DebugLogger:

    def __init__(self, queue: asyncio.Queue):
        self._queue = queue
        self._logger = logging.getLogger("schedule-architect")
        self._logger.setLevel(logging.DEBUG)
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                "%(asctime)s  %(levelname)-8s  %(message)s",
                datefmt="%H:%M:%S",
            ))
            self._logger.addHandler(handler)

    async def put(self, event: Event):
        self._logger.debug(f"→ ENQUEUE  {event.type.name:<20} source={event.source.name}")
        await self._queue.put(event)

    async def get(self) -> Event:
        event = await self._queue.get()
        self._logger.debug(f"← DEQUEUE  {event.type.name:<20} source={event.source.name}")
        return event