from enum import Enum
from dataclasses import dataclass, field


class EventSource(Enum):
    CHAINLIT  = "chainlit"
    ANTHROPIC = "anthropic"


class EventType(Enum):
    # Chainlit → Mediator
    CHAT_START   = "chat_start"
    USER_MESSAGE = "user_message"

    # Anthropic → Mediator
    TEXT_DELTA    = "text_delta"
    TOOL_USE      = "tool_use"
    TURN_COMPLETE = "turn_complete"
    STREAM_ERROR  = "stream_error"


@dataclass
class Event:
    source: EventSource
    type:   EventType
    data:   dict = field(default_factory=dict)
    # data payloads by type:
    #   USER_MESSAGE  — {"text": str}
    #   TEXT_DELTA    — {"text": str}
    #   TOOL_USE      — {"tool_use_id": str, "tool_name": str, "input": dict}
    #   TURN_COMPLETE — {"stop_reason": str}
    #   STREAM_ERROR  — {"error": str}