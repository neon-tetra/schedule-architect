class ResponseParser:

    # ── Stateful streaming mode ───────────────────────────────────────
    def __init__(self):
        self._buffer  = ""
        self._in_tag  = False

    def feed(self, token: str) -> str:
        """Return the passthrough text for this token (empty string if suppressed)."""
        raise NotImplementedError

    # ── Stateless full-parse mode ─────────────────────────────────────
    @classmethod
    def parse(cls, full_text: str) -> list[Segment]:
        """Parse a complete response into ordered text and tag segments."""
        raise NotImplementedError