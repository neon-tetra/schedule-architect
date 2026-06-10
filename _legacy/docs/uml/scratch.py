from pydantic import BaseModel
import chainlit as cl

class Event(BaseModel):
    type: str
    sender: str
    payload: dict
    timestamp: float


#Deciding here...


async def on_message(message: cl.Message):
    event = Event(
        type="message",
        sender="user",
        payload={"content": message.content},
        timestamp=message.timestamp,
    )
    print(event.model_dump_json())

#On program init...
#Build the users session.  Anthropic client, scenario context, yadda.
#Then the loop, capturing input
#Handler implements logic

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import chainlit as cl


# --- Event envelope ---

class Sender(str, Enum):
    CHAINLIT = "chainlit"
    ANTHROPIC = "anthropic"

class EventType(str, Enum):
    USER_MESSAGE = "user_message"
    # future: TEXT_DELTA, TOOL_USE, TOOL_RESULT, TURN_COMPLETE, ...

@dataclass
class Event:
    sender: Sender
    event_type: EventType
    payload: Any
    seq: int


# --- Per-session state ---

class ServerSession:
    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue()
        self._seq: int = 0
        # conversation history, ScenarioContext, etc. will live here

    def make_event(self, sender: Sender, event_type: EventType, payload: Any) -> Event:
        self._seq += 1
        return Event(sender=sender, event_type=event_type, payload=payload, seq=self._seq)


# --- Session bootstrap ---

async def server_session_init() -> ServerSession:
    session = ServerSession()
    asyncio.create_task(mediator_loop(session))
    return session


# --- Mediator loop (the consumer) ---

async def mediator_loop(session: ServerSession):
    while True:
        event = await session.queue.get()

        if event.event_type == EventType.USER_MESSAGE:

            # ANTHROPIC STUFF HERE
            # - build messages list from conversation history
            # - open streaming tool runner
            # - iterate events, push TEXT_DELTA / TOOL_USE events back onto queue
            #   or handle directly and stream to cl.Message
            pass

        session.queue.task_done()


# --- Chainlit hooks (thin producers, nothing else) ---

@cl.on_chat_start
async def on_chat_start():
    session = await server_session_init()
    cl.user_session.set("session", session)
    await cl.Message(content="Schedule Architect ready.").send()


@cl.on_message
async def on_message(message: cl.Message):
    session: ServerSession = cl.user_session.get("session")
    event = session.make_event(
        sender=Sender.CHAINLIT,
        event_type=EventType.USER_MESSAGE,
        payload=message.content,
    )
    await session.queue.put(event)

