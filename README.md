# schedule-architect

A workforce scheduling agent that translates natural language inputs into optimized shift schedules using a structured command engine and CP-SAT constraint programming.

Designed architecture-first, built layer by layer.

---

## Architecture

The system is organized into five layers, designed before implementation and documented as living UML artifacts in `/docs`.

![Component Diagram](docs/architecture_component.png)

| Layer | Responsibility |
|---|---|
| **Domain** | Core entities — skills, queue profiles, slot matrices, rosters |
| **Engine** | Command dispatcher, handler, scenario context, and result presenter |
| **Solver** | Erlang C demand derivation and CP-SAT model builder |
| **Agent** | LLM session layer — prompt assembly, conversation management, tool wrappers |
| **Caller** | Entry point — wires context, dispatcher, and agent session into a live REPL |

Full design documents: [`/docs`](./docs)

---

## AI-Assisted Development

This project was developed using a hybrid workflow: architecture-first design (UML), followed by iterative implementation using GitHub Copilot and agent-assisted scaffolding. All generated code was reviewed, tested, and integrated with full understanding of the system it sits in.

This reflects how I work in real engineering environments — using AI tools to accelerate development while maintaining full ownership of architecture, correctness, and system behavior.

---

## MVP Features

- Define skills and queue profiles via structured commands
- Derive Erlang C staffing requirements from call volume and SLA targets
- Define an agent roster from skill groups and headcounts
- CP-SAT schedule optimization minimizing coverage shortfall
- Solve result bundled as demand / supply / shortfall slot matrices
- LLM-readable result presentation via `ReadResult` command
- Live conversational agent session via Anthropic Claude with full tool use
- Prompt caching — static system prompt prefix cached across turns to minimize token cost
- `chat.py` REPL entry point for interactive scenario building

---

## Roadmap

| MVP ✓ | V2 |
|---|---|
| Domain entities | Constraint template registry |
| Command dispatcher + handler | Bespoke constraint authoring via agent |
| Erlang C derivation | Weighted and conditional shortfall penalties |
| CP-SAT solve | Coverage ratio and floor constraints |
| `ReadResult` + `LLMPresenter` | Parameterizable objective function |
| Shortfall table presentation | Batch scenario commands |
| Agent session + tool use | Multi-scenario session management |
| Prompt caching | Schedule types and shift templates |
| Live conversational REPL | Full simulation and schedule evaluation |

---

## Project Structure

```
schedule-architect/
│
├── main.py                         # Headless entry point (no agent)
├── chat.py                         # Conversational agent REPL entry point
├── requirements.txt
│
├── domain/                         # Core data models (no dependencies)
│   ├── skill.py
│   ├── call_environment.py         # QueueProfile
│   ├── erlang.py                   # SlotMatrix
│   ├── roster.py                   # Roster, RosterEntry
│   └── schedule.py                 # ScheduleType, SolveResult
│
├── engine/                         # Orchestration layer
│   ├── commands.py                 # ModelCommand union + command types
│   ├── command_result.py           # CommandResult
│   ├── context.py                  # ScenarioContext
│   ├── dispatcher.py               # Dispatcher
│   ├── handler.py                  # Handler
│   ├── presenter.py                # LLMPresenter
│   └── solve_result.py             # SolveResult
│
├── solver/                         # Optimisation layer
│   ├── erlang.py                   # Erlang C staffing calculations
│   ├── model_builder.py            # CP-SAT model construction + solve
│   └── var_registry.py             # Solver variable registry
│
├── agent/                          # LLM agent session layer
│   ├── session.py                  # AgentSession — full turn lifecycle
│   ├── tools.py                    # AgentTools — @beta_tool wrappers
│   ├── prompt_builder.py           # SystemPromptBuilder — static/dynamic sections + caching
│   └── conversation.py             # ConversationManager — history + trim
│
├── scenarios/
│   └── default.py                  # Default scenario definition
│
└── docs/
    └── uml/
        ├── domain_classes.puml
        ├── engine_classes.puml
        ├── solver_classes.puml
        ├── dispatch_activity.puml
        ├── agent_session.puml
        └── agent_activity_classes.puml
```

---

## Getting Started

```bash
pip install -r requirements.txt

# Headless solve (no agent)
python main.py

# Conversational agent session
$env:ANTHROPIC_API_KEY = "your_key_here"   # PowerShell
# export ANTHROPIC_API_KEY="your_key_here" # bash
python chat.py
```

---

## V2 Vision

The next major milestone is a **constraint template registry** — a bounded vocabulary of named, parameterizable constraint patterns that the agent can select, configure, and compose at runtime. Rather than generating arbitrary CP-SAT code, the agent fills in typed dataclass templates that map to known solver primitives. This keeps the model auditable and the agent's surface area well-defined, while enabling genuinely bespoke optimization problems to be authored through conversation.

Example targets:
> *"There must be at least one photo agent starting at 8am every day"*
> *"If escalation coverage drops below 10% of total agents, double the shortfall penalty"*

---

## License

MIT