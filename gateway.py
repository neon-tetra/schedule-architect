import asyncio
import chainlit as cl
from mediator import MediatorLoop
from events import Event, EventSource, EventType

@cl.on_chat_start
async def on_chat_start():
    queue = asyncio.Queue()
    cl.user_session.set("queue", queue)
    mediator = MediatorLoop(queue)
    asyncio.create_task(mediator.run())

@cl.on_message
async def on_message(message: cl.Message):
    queue = cl.user_session.get("queue")
    await queue.put(Event(
        source=EventSource.CHAINLIT,
        type=EventType.USER_MESSAGE,
        data={"text": message.content}
    ))