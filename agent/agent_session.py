from anthropic import AsyncAnthropic

from enum import IntEnum
from agent.prompts import OVERVIEW, SCENARIO_DESCRIPTION, ROLE_FINAL, ROLE_MIDDLE, ROLE_BEGINNING
from agent.toolkit import Toolkit
from agent.response_parser import ResponseParser
MODEL      = "claude-opus-4-5"
MAX_TOKENS = 8096

class Stage(IntEnum):
    BEGINNING = 1
    MIDDLE    = 2
    FINAL     = 3


class AgentSession:
    def __init__(self):
        self._messages          = []
        self._turn              = 0
        self._stage             = Stage.BEGINNING
        self._toolkit           = Toolkit() #For now - automatically load default scenario to toolkit
        self._client            = AsyncAnthropic()
        # Eagerly loaded at session start via toolkit — locks starting conditions
        # into the static (cached) section of the system prompt. This is intentional:
        # the result of a dynamic lookup at init time, not recomputed each turn.
        self._scenario_desc     = self._build_scenario_description()
    # ── Public interface ──────────────────────────────────────────────

    @property
    def current_turn(self) -> int:
        return self._turn

    @property
    def stage(self) -> Stage:
        return self._stage

    @stage.setter
    def stage(self, value: Stage):
        self._stage = value

    def add_user_message(self, text: str):
        self._turn += 1
        self._messages.append({
            "role":    "user",
            "content": text
        })

        if self._turn >= 5:
            self._stage = Stage.FINAL
        elif self._turn >= 3:
            self._stage = Stage.MIDDLE

    def add_assistant_message(self, text: str):
        """Store assistant turn. Receives summary text only — full response already streamed to UI."""
        self._messages.append({
            "role":    "assistant",
            "content": text
        })

    def add_tool_result(self, tool_use_id: str, result: str):
        self._messages.append({
            "role": "user",
            "content": [{
                "type":        "tool_result",
                "tool_use_id": tool_use_id,
                "content":     result 
            }]
        })

    def add_assistant_tool_use(self, content: list):
        """Store assistant turn that ended in a tool use — preserves full content block."""
        self._messages.append({
            "role":    "assistant",
            "content": content   # raw content list from Anthropic, tool_use block intact
        })

    # def handle_tool_use(self, tool_use_id: str, tool_name: str, tool_input: dict, full_content: list) -> str: #Retired
    #     # Deliberately sync/blocking — tool execution is fast (no external I/O expected).
    #     # If that changes (e.g. solver becomes async), make this async def and await accordingly.
    #     self.add_assistant_tool_use(full_content)
    #     result = self._toolkit.execute(tool_name, tool_input)
    #     self.add_tool_result(tool_use_id, result)
    #     return result

    def build_payload(self) -> dict:
        return {
            "model":      MODEL,
            "max_tokens": MAX_TOKENS,
            "system":     self._build_system_prompt(),
            "messages":   self._messages,
            "tools":      self._toolkit.get_tool_list()  
        }

    # ── Prompt assembly ───────────────────────────────────────────────

    def _build_system_prompt(self) -> list[dict]:
        sections = [
            self._overview(),
            self._scenario_desc,
            self._role_final(),
        ]
        if self._stage <= Stage.MIDDLE:
            sections.append(self._role_middle())
        if self._stage == Stage.BEGINNING:
            sections.append(self._role_beginning())

        static  = "\n\n".join(sections)
        dynamic = self._recent_solves()
        return self._as_cached_blocks(static, dynamic)

    def _as_cached_blocks(self, static: str, dynamic: str) -> list[dict]:
        return [
            {"type": "text", "text": static,  "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": dynamic},
        ]

    # ── Static prompt sections (built once or stage-invariant) ────────

    def _build_scenario_description(self) -> str:
        # stub — will derive from scenario config; returns static placeholder for now
        return self._toolkit.get_detailed_summary() + "\n\n" + SCENARIO_DESCRIPTION

    def _overview(self) -> str:
        return OVERVIEW

    def _role_final(self) -> str:
        return ROLE_FINAL

    def _role_middle(self) -> str:
        return ROLE_MIDDLE

    def _role_beginning(self) -> str:
        return ROLE_BEGINNING

    # ── Dynamic prompt sections (rebuilt each turn) ───────────────────

    def _recent_solves(self) -> str:
        return self._toolkit.get_recent_solves_summary()


    async def run_turn(self, text: str, on_token: callable): #This is doing way too much but we'll decompose it later
        self.add_user_message(text)
        parser = ResponseParser()
        try:
            while True:
                raw_response_text = ""
                async with self._client.messages.stream(**self.build_payload()) as stream:
                    async for chunk in stream:
                        if chunk.type == "content_block_delta" and chunk.delta.type == "text_delta":      # Streamed token
                            raw_response_text += chunk.delta.text
                            passthrough_token = parser.feed(chunk.delta.text)
                            if passthrough_token:
                                await on_token(passthrough_token)
                        elif chunk.type == "message_delta" and chunk.delta.stop_reason == "tool_use":     # Tool use request
                            full_message = await stream.get_final_message()
                            tool_blocks = [b for b in full_message.content if b.type == "tool_use"]
                            self.add_assistant_tool_use(full_message.content)
                            for tool_block in tool_blocks:
                                result = self._toolkit.execute(tool_block.name, tool_block.input)
                                self.add_tool_result(tool_block.id, result)
                            break
                        elif chunk.type == "message_delta" and chunk.delta.stop_reason == "end_turn":     # End of response
                            parsed = ResponseParser.parse(raw_response_text)
                            self.add_assistant_message(parsed.summary)
                            return parsed
        except Exception as e:
            self._dump_messages()
            raise e
        
    def _dump_messages(self):
        import json
        import logging
        log = logging.getLogger(__name__)
        log.error("Message history at failure:\n%s",
            json.dumps(self._messages, indent=2, default=str))    