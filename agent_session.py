import re
from config import MODEL, MAX_TOKENS, TOOL_SCHEMAS

SUMMARY_TAG = r'<<summary>>(.*?)<</summary>>'

class AgentSession:

    def __init__(self):
        self._messages = []
        self._turn     = 0

    # ── Public interface ──────────────────────────────────────────────

    @property
    def current_turn(self) -> int:
        return self._turn

    def add_user_message(self, text: str):
        self._turn += 1
        self._messages.append({
            "role":    "user",
            "content": text
        })

    def add_assistant_message(self, text: str):
        """Store assistant turn. Receives summary text only — full response already streamed to UI."""
        self._messages.append({
            "role":    "assistant",
            "content": text
        })

    def add_tool_result(self, tool_use_id: str, result: dict):
        self._messages.append({
            "role": "user",
            "content": [{
                "type":        "tool_result",
                "tool_use_id": tool_use_id,
                "content":     result
            }]
        })

    def build_payload(self) -> dict:
        return {
            "model":      MODEL,
            "max_tokens": MAX_TOKENS,
            "system":     self._build_system_prompt(),
            "messages":   self._messages,
            "tools":      TOOL_SCHEMAS
        }

    # ── Internal ───────────────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        # stub — will be tutorial-path-aware via current_turn
        return (
            "You are schedule-architect, a workforce planning assistant.\n\n"
            "End every response with a <<summary>>one-sentence recap of what you said "
            "and any actions taken<</summary>> tag. This tag will be stripped from the "
            "display and used only to compress conversation history."
        )
