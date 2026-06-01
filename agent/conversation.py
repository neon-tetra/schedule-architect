class ConversationManager:
    """
    Owns the messages array sent to the Anthropic API each turn.
    Responsible for appending user and assistant messages and
    trimming history when it grows too large.
    """

    _messages: list[dict]
    _max_turns: int

    def add_user_message(self, content: str) -> None:
        """Append a user message to the conversation."""
        pass

    def add_assistant_message(self, content: str) -> None:
        """Append an assistant message to the conversation."""
        pass

    def get_messages(self) -> list[dict]:
        """Return the current message history."""
        pass

    def trim(self) -> None:
        """Trim conversation history when it exceeds the configured limit."""
        pass

    # deferred: summarise(self, client) -> None
