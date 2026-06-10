CACHE_BOUNDARY = "<!-- CACHE_BOUNDARY -->"


class PromptSection:
    def __init__(self, heading: str, content: str, dynamic: bool):
        self.heading = heading
        self.content = content
        self.dynamic = dynamic


class SystemPromptBuilder:
    """
    Assembles a system prompt from ordered sections.
    Static sections are assembled first (stable, cache-friendly prefix).
    Dynamic sections follow (rebuilt each turn — context state etc).
    A CACHE_BOUNDARY marker is inserted between them so the calling
    layer can split the prompt for Anthropic prompt caching.
    """

    def __init__(self):
        self._static_sections: list[PromptSection] = []
        self._dynamic_sections: list[PromptSection] = []

    def add_static_section(self, heading: str, content: str) -> "SystemPromptBuilder":
        """Add a static section to the system prompt. Returns self for chaining."""
        self._static_sections.append(PromptSection(heading, content, dynamic=False))
        return self

    def add_dynamic_section(self, heading: str, content: str) -> "SystemPromptBuilder":
        """Add a dynamic section to the system prompt. Returns self for chaining."""
        self._dynamic_sections.append(PromptSection(heading, content, dynamic=True))
        return self
    
    def build(self) -> str:
        """
        Build the full system prompt.
        Static prefix and dynamic suffix are separated by CACHE_BOUNDARY.
        AgentSession splits on this marker to apply cache_control to the
        static prefix block.
        Dynamic sections are cleared after build — callers must re-add
        them each turn to prevent stale context being served.
        """
        parts = []
        static = self._build_static_prefix()
        dynamic = self._build_dynamic_suffix()

        if static:
            parts.append(static)
        if dynamic:
            parts.append(CACHE_BOUNDARY)
            parts.append(dynamic)

        self._dynamic_sections = []

        return "\n\n".join(parts)

    def _build_static_prefix(self) -> str:
        """Render static sections as headed blocks."""
        return self._render_sections(self._static_sections)

    def _build_dynamic_suffix(self) -> str:
        """Render dynamic sections as headed blocks."""
        return self._render_sections(self._dynamic_sections)

    def _render_sections(self, sections: list[PromptSection]) -> str:
        blocks = []
        for section in sections:
            blocks.append(f"## {section.heading}\n{section.content.strip()}")
        return "\n\n".join(blocks)