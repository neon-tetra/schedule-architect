from anthropic import Anthropic
from engine.dispatcher import Dispatcher
from engine.context import ScenarioContext
from agent.tools import AgentTools
from agent.prompt_builder import SystemPromptBuilder
from agent.conversation import ConversationManager


class AgentSession:
    """
    Owns the full agent turn lifecycle. On each call to run_turn():
      1. Appends the user message to conversation history
      2. Reads ScenarioContext to populate dynamic prompt sections
      3. Assembles system prompt via SystemPromptBuilder
      4. Retrieves message history from ConversationManager
      5. Calls tool_runner with assembled prompt, messages and tools
      6. Appends assistant response to conversation history
      7. Returns response text to caller

    AgentSession owns SystemPromptBuilder, ConversationManager and
    AgentTools. It holds a reference to Dispatcher (does not own it).
    ScenarioContext is read for dynamic prompt sections only — it is
    owned and written by Dispatcher/Handler in the engine layer.
    """

    session_id: str
    model: str
    _client: Anthropic
    _builder: SystemPromptBuilder
    _conversation: ConversationManager
    _tools: AgentTools

    def run_turn(self, user_message: str) -> str:
        """Run a single user turn through the agent session lifecycle."""
        pass

    def _get_tools(self) -> list:
        """Return tool callables used for tool_runner execution."""
        pass

    # deferred: swap_model(self, model: str) -> None
