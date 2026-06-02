import uuid

from anthropic import Anthropic
from anthropic import beta_tool

from engine.dispatcher import Dispatcher
from engine.context import ScenarioContext
from agent.tools import AgentTools
from agent.prompt_builder import SystemPromptBuilder, CACHE_BOUNDARY
from agent.conversation import ConversationManager, SUMMARISE_AFTER_TURNS

MODEL_DEFAULT = "claude-opus-4-5"


class AgentSession:
    """
    Owns the full agent turn lifecycle. On each call to run_turn():
      1. Appends the user message to conversation history
      2. Reads ScenarioContext to populate dynamic prompt sections
      3. Assembles system prompt via SystemPromptBuilder
      4. Retrieves message history from ConversationManager
      5. Calls the Anthropic API with tool_use support
      6. Appends assistant response to conversation history
      7. Returns response text to caller
      8. Prints full solve presentation to stdout if a solve was read this turn

    AgentSession owns SystemPromptBuilder, ConversationManager and
    AgentTools. It holds a reference to Dispatcher (does not own it).
    ScenarioContext is read for dynamic prompt sections only — it is
    owned and written by Dispatcher/Handler in the engine layer.
    """

    def __init__(
        self,
        dispatcher: Dispatcher,
        context: ScenarioContext,
        api_key: str,
        model: str = MODEL_DEFAULT,
    ):
        self.session_id = str(uuid.uuid4())
        self.model = model
        self._client = Anthropic(api_key=api_key)
        self._context = context
        self._builder = SystemPromptBuilder()
        self._conversation = ConversationManager()
        self._tools = AgentTools(dispatcher, context)
        self._last_presentation: str | None = None  # set by dispatcher hook, printed post-turn

        self._builder.add_static_section(
            "Role",
            "You are a workforce scheduling assistant. You help operations managers "
            "model call centre staffing scenarios. You have access to tools to define "
            "queue profiles, derive staffing demand via Erlang C, define agent rosters, "
            "run the optimisation solver, and read results. Work step by step. "
            "Confirm what you have done after each tool call before proceeding.",
        )
        self._builder.add_static_section(
            "Behaviour",
            "Always use tools to make changes to the scenario — never invent numbers. "
            "If the user asks for a solve, ensure queue profiles, demand, and a roster "
            "are all defined first. If anything is missing, ask before proceeding. "
            "When presenting results, be concise and highlight shortfall by skill and "
            "suggest targeted roster changes. The full grid has been printed separately "
            "for the user — focus your commentary on the most actionable insights.",
        )

    def run_turn(self, user_message: str) -> str:
        """Run a single user turn through the full agent lifecycle."""

        self._conversation.add_user_message(user_message)

        if self._conversation.turn_count >= SUMMARISE_AFTER_TURNS:
            self._conversation.summarise(self._client)
        else:
            self._conversation.trim()

        self._builder.add_dynamic_section(
            "Current Scenario State",
            self._summarise_context(),
        )

        prompt = self._builder.build()
        system = self._build_system_blocks(prompt)
        messages = self._conversation.get_messages()
        tools = self._get_tools()

        final_message = self._client.beta.messages.tool_runner(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=messages,
            tools=tools,
        ).until_done()

        # Print the full ASCII presentation to the user if a read_result happened this turn.
        # This is done here rather than inside the tool so it doesn't enter conversation history.
        if self._context.solve_result is not None:
            from engine.presenter import LLMPresenter
            presentation = LLMPresenter(self._context.solve_result).present()
            print(f"\n{presentation}\n")

        final_text = next(
            (block.text for block in final_message.content if block.type == "text"),
            "",
        )
        self._conversation.add_assistant_message(final_text)
        return final_text

    def _get_tools(self) -> list:
        return self._tools.get_tools()

    def _build_system_blocks(self, prompt: str) -> list[dict]:
        if CACHE_BOUNDARY in prompt:
            static, dynamic = prompt.split(CACHE_BOUNDARY, 1)
            return [
                {
                    "type": "text",
                    "text": static.strip(),
                    "cache_control": {"type": "ephemeral"},
                },
                {
                    "type": "text",
                    "text": dynamic.strip(),
                },
            ]
        return [{"type": "text", "text": prompt.strip()}]

    def _summarise_context(self) -> str:
        """Read ScenarioContext and return a plain-text summary for the dynamic prompt section."""
        ctx = self._context
        lines = [f"Scenario: {ctx.name}"]

        if ctx.queues:
            lines.append(f"Queues defined: {', '.join(ctx.queues.keys())}")
        else:
            lines.append("Queues defined: none")

        lines.append("Demand derived: " + ("yes" if ctx.demand else "no"))
        lines.append("Roster defined: " + ("yes" if ctx.current_roster else "no"))

        if ctx.current_roster:
            lines.append(f"Roster size: {ctx.current_roster.total_agents} agents")
            lines.append("Roster composition:")
            lines.append(ctx.current_roster.summary())

        if ctx.current_roster and ctx.queues:
            cost = ctx.current_roster.total_monthly_cost(ctx.queues)
            lines.append(f"Roster monthly cost: ${cost:,.0f}")

        if ctx.solve_result:
            lines.append(f"Last solve: {ctx.solve_result.status}, "
                         f"shortfall {ctx.solve_result.shortfall.sum()} agent-slots")
        else:
            lines.append("Last solve: none")

        return "\n".join(lines)

    # deferred: swap_model(self, model: str) -> None