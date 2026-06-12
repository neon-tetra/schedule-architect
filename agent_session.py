import re
from enum import IntEnum
from prompts import OVERVIEW, SCENARIO_DESCRIPTION, ROLE_FINAL, ROLE_MIDDLE, ROLE_BEGINNING
from toolkit import Toolkit
MODEL      = "claude-opus-4-5"
MAX_TOKENS = 8096

SUMMARY_TAG = r'<<summary>>(.*?)<</summary>>'

class Stage(IntEnum):
    BEGINNING = 1
    MIDDLE    = 2
    FINAL     = 3


class AgentSession:
    def __init__(self, toolkit: Toolkit):
        self._messages          = []
        self._turn              = 0
        self._stage             = Stage.BEGINNING
        self._toolkit           = toolkit
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

    def add_tool_result(self, tool_use_id: str, result: str):  # str not dict
        self._messages.append({
            "role": "user",
            "content": [{
                "type":        "tool_result",
                "tool_use_id": tool_use_id,
                "content":     result   # string, Anthropic is happy
            }]
        })

    def handle_tool_use(self, tool_use_id: str, tool_name: str, tool_input: dict, full_content: list):
        # Deliberately sync/blocking — tool execution is fast (no external I/O expected).
        # If that changes (e.g. solver becomes async), make this async def and await accordingly.
        self.add_assistant_tool_use(full_content)
        result = self._toolkit.execute(tool_name, tool_input)
        self.add_tool_result(tool_use_id, result)

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
        dynamic = "\n\n".join([
            self._tool_list(),
            self._recent_tool_results(),
        ])
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

    def _tool_list(self) -> str:
        # stub — will derive from toolkit object
        return "[tool list]"

    def _recent_tool_results(self) -> str:
        # stub — will derive from recent tool call history
        return "[recent tool results]"
    def add_assistant_tool_use(self, content: list):
        """Store assistant turn that ended in a tool use — preserves full content block."""
        self._messages.append({
            "role":    "assistant",
            "content": content   # raw content list from Anthropic, tool_use block intact
        })