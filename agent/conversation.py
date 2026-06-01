class ConversationManager:
    """
    Owns the messages array sent to the Anthropic API each turn.
    Responsible for appending user and assistant messages and
    trimming history when it grows too large.
    """

    def __init__(self, max_turns: int = 20):
        self._messages: list[dict] = []
        self._max_turns = max_turns

    def add_user_message(self, content: str) -> None:
        """Append a user message to the conversation."""
        self._messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        """Append an assistant message to the conversation."""
        self._messages.append({"role": "assistant", "content": content})

    def get_messages(self) -> list[dict]:
        """Return the current message history."""
        return list(self._messages)

    def trim(self) -> None:
        """
        Trim conversation history when it exceeds the configured limit.
        Drops the oldest messages in pairs (user + assistant) to preserve
        role alternation. The most recent max_turns messages are kept.
        """
        if len(self._messages) > self._max_turns:
            excess = len(self._messages) - self._max_turns
            # round up to nearest 2 to always drop complete pairs
            excess = excess + (excess % 2)
            self._messages = self._messages[excess:]

    # deferred: summarise(self, client) -> None