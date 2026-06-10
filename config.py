import anthropic

anthropic_client = anthropic.AsyncAnthropic()
MODEL      = "claude-opus-4-5"
MAX_TOKENS = 8096
TOOL_SCHEMAS = []  # stub