import re
from dataclasses import dataclass, field


# ── Segment types ─────────────────────────────────────────────────────────────

@dataclass
class TextSegment:
    content: str

@dataclass
class SummarySegment:
    content: str

@dataclass
class ChartSegment:
    chart_id: str
    data: dict = field(default_factory=dict)

Segment = TextSegment | SummarySegment | ChartSegment


# ── Parsed response container ─────────────────────────────────────────────────

@dataclass
class ParsedResponse:
    segments:     list[Segment]
    display_text: str   # pre-joined text segments — ready for Chainlit
    summary:      str   # <<summary>> content, falls back to display_text if absent


# ── Parser ────────────────────────────────────────────────────────────────────

# All recognised tag names. Adding a new tag type = add it here.
_KNOWN_TAGS = {"summary", "chart"}

class ResponseParser:

    # ── Stateful streaming mode ───────────────────────────────────────────────

    def __init__(self):
        self._buffer = ""   # accumulates characters while inside a << >> block
        self._in_tag = False

    def feed(self, token: str) -> str:
        """
        Accept one streaming token. Returns the text that should be passed
        through to the UI immediately — empty string if the token is suppressed
        because it falls inside a << >> tag block.
        """
        passthrough = ""

        for char in token:
            if not self._in_tag:
                if char == "<" and self._buffer.endswith("<"):
                    # Second < of << — enter tag mode, suppress both chars
                    self._buffer = ""
                    self._in_tag = True
                elif char == "<":
                    # Possibly the start of << — hold it
                    self._buffer = "<"
                else:
                    # Normal character — flush any held buffer and pass through
                    passthrough += self._buffer + char
                    self._buffer = ""
            else:
                if char == ">" and self._buffer.endswith(">"):
                    # Second > of >> — tag closed, discard buffer, exit tag mode
                    self._buffer = ""
                    self._in_tag = False
                else:
                    self._buffer += char

        return passthrough


    # ── Stateless full-parse mode ─────────────────────────────────────────────

    @classmethod
    def parse(cls, full_text: str) -> ParsedResponse:
        """
        Parse a complete response string into an ordered list of segments.
        Extracts <<tag>>content<</tag>> blocks into typed segments; everything
        else becomes TextSegments.
        """
        segments: list[Segment] = []
        # Matches <<tagname>> ... <</tagname>> with optional attributes (future)
        pattern = re.compile(r'<<(\w+)(?::([^>]*))?>>(.+?)<</\1>>', re.DOTALL)
        cursor = 0

        for match in pattern.finditer(full_text):
            # Text before this tag
            if match.start() > cursor:
                text = full_text[cursor:match.start()].strip()
                if text:
                    segments.append(TextSegment(content=text))

            tag_name = match.group(1).lower()
            attribute = match.group(2)          # e.g. chart id, None if absent
            content   = match.group(3).strip()

            if tag_name == "summary":
                segments.append(SummarySegment(content=content))
            elif tag_name == "chart":
                segments.append(ChartSegment(chart_id=attribute or "", data={}))
            else:
                # Unknown tag — treat as plain text so nothing is silently lost
                segments.append(TextSegment(content=content))

            cursor = match.end()

        # Remaining text after the last tag
        if cursor < len(full_text):
            text = full_text[cursor:].strip()
            if text:
                segments.append(TextSegment(content=text))

        # ── Derive convenience fields ─────────────────────────────────────────
        display_text = "\n\n".join(
            s.content for s in segments if isinstance(s, TextSegment)
        )
        summary_segments = [s for s in segments if isinstance(s, SummarySegment)]
        summary = summary_segments[0].content if summary_segments else display_text

        return ParsedResponse(segments=segments, display_text=display_text, summary=summary)