class PromptSection:
    heading: str
    content: str
    dynamic: bool


class SystemPromptBuilder:
    """
    Assembles a system prompt from ordered sections.
    Static sections are assembled first (stable, cache-friendly prefix).
    Dynamic sections follow (rebuilt each turn — context state etc).
    A CACHE_BOUNDARY marker is inserted between them so the calling
    layer can split the prompt for Anthropic prompt caching.
    """

    _static_sections: list[PromptSection]
    _dynamic_sections: list[PromptSection]

    def add_static_section(self, heading: str, content: str) -> "SystemPromptBuilder":
        """Add a static section to the system prompt."""
        pass

    def add_dynamic_section(self, heading: str, content: str) -> "SystemPromptBuilder":
        """Add a dynamic section to the system prompt."""
        pass

    def build(self) -> str:
        """Build the full system prompt."""
        pass

    def _build_static_prefix(self) -> str:
        """Build the static section prefix for prompt caching."""
        pass

    def _build_dynamic_suffix(self) -> str:
        """Build the dynamic section suffix."""
        pass
