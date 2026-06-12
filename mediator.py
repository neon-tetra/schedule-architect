import re
import asyncio
import chainlit as cl
from anthropic import AsyncAnthropic
from debug_logger import DebugLogger
from events import Event, EventSource, EventType
from agent_session import AgentSession
#from scenario_context import ScenarioContext
#from solver import Solver
#from presenter import Presenter
from scenario_context import ScenarioContext
from toolkit import Toolkit
anthropic_client = AsyncAnthropic()


class MediatorLoop:

    def __init__(self, queue: asyncio.Queue, session: AgentSession, context: ScenarioContext, toolkit: Toolkit):
        self._queue   = DebugLogger(queue)
        self._session = session
        self._context = context
        self._toolkit = toolkit
        # self._context = ScenarioContext()
        # self._solver  = Solver()
        # self._presenter = Presenter()
        self._handlers = {
            EventType.USER_MESSAGE:   self._handle_user_message,
            EventType.TOOL_REQUEST:   self._handle_tool_request,
            EventType.FINAL_RESPONSE: self._handle_final_response,
        }

    async def run(self):
        while True:
            event: Event = await self._queue.get()
            handler = self._handlers.get(event.type)
            if handler:
                await handler(event)

    # ── Anthropic streaming ──────────────────────────────────────────────

    async def _stream_anthropic(self):
        self._active_message = cl.Message(content="")
        await self._active_message.send()
        payload = self._session.build_payload()
        async with anthropic_client.messages.stream(**payload) as stream:
            async for chunk in stream:
                if chunk.type == "content_block_delta" and chunk.delta.type == "text_delta":
                    await self._active_message.stream_token(chunk.delta.text)
                elif chunk.type == "message_delta":
                    if chunk.delta.stop_reason == "tool_use":
                        full_message = await stream.get_final_message()
                        tool_block = next(
                            b for b in full_message.content
                            if b.type == "tool_use"
                        )
                        await self._queue.put(Event(
                            source=EventSource.ANTHROPIC,
                            type=EventType.TOOL_REQUEST,
                            data={
                                "tool_name":    tool_block.name,
                                "tool_use_id":  tool_block.id,
                                "input":        tool_block.input,
                                "full_content": full_message.content,
                            }
                        ))
                    else:
                        await self._queue.put(Event(
                            source=EventSource.ANTHROPIC,
                            type=EventType.FINAL_RESPONSE,
                            data={"stop_reason": chunk.delta.stop_reason}
                        ))

    # ── Handlers ─────────────────────────────────────────────────────

    async def _handle_user_message(self, event: Event):
        self._session.add_user_message(event.data["text"])
        await self._stream_anthropic()

    async def _handle_tool_request(self, event: Event):
        tool_name    = event.data["tool_name"]
        tool_input   = event.data["input"]
        tool_use_id  = event.data["tool_use_id"]
        full_content = event.data["full_content"]

        self._session.add_assistant_tool_use(full_content)

        result = self._toolkit.execute(tool_name, tool_input)
        self._session.add_tool_result(tool_use_id, result)
        await self._stream_anthropic()

    async def _handle_final_response(self, event: Event):
        full_text = self._active_message.content
        match = re.search(r'<<summary>>(.*?)<</summary>>', full_text, re.DOTALL)
        if match:
            summary    = match.group(1).strip()
            clean_text = re.sub(r'\s*<<summary>>.*?<</summary>>', '', full_text, flags=re.DOTALL).strip()
            self._active_message.content = clean_text
        else:
            summary = full_text
        await self._active_message.update()
        self._session.add_assistant_message(summary)
        self._active_message = None

