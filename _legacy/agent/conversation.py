import logging

logger = logging.getLogger(__name__)

# Summarise when history exceeds this many turns
SUMMARISE_AFTER_TURNS = 12
# How many recent turns to keep verbatim after summarisation
KEEP_RECENT_TURNS = 4


class ConversationManager:
    """
    Owns the messages array sent to the Anthropic API each turn.
    Responsible for appending user and assistant messages and
    trimming or summarising history when it grows too large.
    """

    def __init__(self, max_turns: int = 20):
        self._messages: list[dict] = []
        self._max_turns = max_turns
        self._summary: str | None = None  # compressed older history

    def add_user_message(self, content: str) -> None:
        """Append a user message to the conversation."""
        self._messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        """Append an assistant message to the conversation."""
        self._messages.append({"role": "assistant", "content": content})

    def get_messages(self) -> list[dict]:
        """
        Return the current message history.
        If a summary exists, it is injected as the first user/assistant
        exchange so the model has context for the compressed older turns.
        """
        if self._summary is None:
            return list(self._messages)

        summary_pair = [
            {
                "role": "user",
                "content": "Here is a summary of our conversation so far:",
            },
            {
                "role": "assistant",
                "content": self._summary,
            },
        ]
        return summary_pair + list(self._messages)

    def trim(self) -> None:
        """
        Trim conversation history when it exceeds the configured limit.
        Drops the oldest messages in pairs (user + assistant) to preserve
        role alternation. The most recent max_turns messages are kept.
        """
        if len(self._messages) > self._max_turns:
            excess = len(self._messages) - self._max_turns
            excess = excess + (excess % 2)
            self._messages = self._messages[excess:]

    async def summarise(self, client) -> None:
        """
        Compress older conversation turns into a summary string, keeping
        only the most recent KEEP_RECENT_TURNS turns verbatim.

        Uses the cheapest available model (haiku) since this is a
        mechanical compression task, not a reasoning task.

        The summary is stored on self._summary and prepended to messages
        by get_messages(). The compressed turns are removed from
        self._messages.

        Does nothing if history is too short to be worth compressing.
        """
        # Need at least KEEP_RECENT_TURNS + something to compress
        if len(self._messages) <= KEEP_RECENT_TURNS + 2:
            return

        to_compress = self._messages[:-KEEP_RECENT_TURNS]
        self._messages = self._messages[-KEEP_RECENT_TURNS:]

        # Build a plain text transcript of the turns to compress
        transcript_parts = []
        for msg in to_compress:
            role = msg["role"].capitalize()
            content = msg["content"]
            # content may be a list of blocks (tool use turns) — flatten to text
            if isinstance(content, list):
                text_blocks = [
                    b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
                ]
                content = " ".join(text_blocks).strip() or "[tool interaction]"
            transcript_parts.append(f"{role}: {content}")

        transcript = "\n".join(transcript_parts)

        summarise_prompt = (
            "The following is a partial transcript of a workforce scheduling "
            "assistant session. Summarise it concisely, preserving:\n"
            "- Which queue profiles and roster were defined\n"
            "- Whether a solve was run and what the key results were\n"
            "- Any roster changes the user requested\n"
            "- Any open questions or decisions not yet resolved\n\n"
            "Transcript:\n"
            f"{transcript}\n\n"
            "Write the summary in third person, past tense. Be concise."
        )

        try:
            response = await client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=512,
                messages=[{"role": "user", "content": summarise_prompt}],
            )
            new_summary = response.content[0].text.strip()

            # If there was already a summary, merge it with the new one
            if self._summary:
                new_summary = f"{self._summary}\n\n{new_summary}"

            self._summary = new_summary
            logger.info(
                "ConversationManager: summarised %d turns, summary length %d chars",
                len(to_compress),
                len(self._summary),
            )

        except Exception as exc:
            # Summarisation is best-effort — if it fails, restore the messages
            # rather than silently losing context
            logger.warning("ConversationManager.summarise failed: %s", exc)
            self._messages = to_compress + self._messages

    @property
    def turn_count(self) -> int:
        """Number of messages currently in the live (non-summarised) buffer."""
        return len(self._messages)

    @property
    def has_summary(self) -> bool:
        return self._summary is not None