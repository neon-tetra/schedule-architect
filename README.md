# schedule-architect

A workforce scheduling agent that translates natural language inputs into optimized shift schedules using a structured command engine and CP-SAT constraint programming.

Designed architecture-first, built layer by layer.

---

## Architecture

The system is organized into four layers, designed before implementation and documented as living UML artifacts in `/docs`.

![Component Diagram](docs/architecture_component.png)

| Layer | Responsibility |
|---|---|
| **Domain** | Core entities — skills, queue profiles, slot matrices, rosters |
| **Engine** | Command dispatcher, handler, scenario context, and result presenter |
| **Solver** | Erlang C demand derivation and CP-SAT model builder |
| **Caller** | LLM agent — submits commands, reads results |

Full design documents: [`/docs`](./docs)

---

## AI-Assisted Development

This project was developed using a hybrid workflow: architecture-first design (UML), followed by iterative implementation using GitHub Copilot and agent-assisted scaffolding. All generated code was manually reviewed, refined, and integrated within a deliberate system design.

This reflects how I work in real engineering environments — using AI tools to accelerate development while maintaining full ownership of architecture, correctness, and system behavior.

---

## MVP Features

- Define skills and queue profiles via structured commands
- Derive Erlang C staffing requirements from call volume and SLA targets
- Define an agent roster from skill groups and headcounts
- CP-SAT schedule optimization minimizing coverage shortfall
- Solve result bundled as demand / supply / shortfall slot matrices
- LLM-readable result presentation via `ReadResult` command

---

## Roadmap

| MVP | Planned |
|---|---|
| Domain entities | Schedule types and shift templates |
| Command dispatcher + handler | `AdjustRoster` command |
| Erlang C derivation | `AdjustTargets` command |
| CP-SAT solve | Shift start menu (lever) |
| `ReadResult` + `LLMPresenter` | Multi-scenario session management |
| Shortfall table presentation | Full simulation and schedule evaluation |

---

## Project Structure

```
schedule-architect/
│
├── main.py                         # Entry point
│
├── domain/                         # Core data models (no dependencies)
│   ├── queue_profile.py            # QueueProfile
│   ├── roster.py                   # Roster, RosterEntry
│   └── slot_matrix.py              # SlotMatrix
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
├── solver/                         # Optimisation layer (external dependency)
│   ├── erlang.py                   # Erlang C staffing calculations
│   ├── model_builder.py            # CP-SAT model construction + solve
│   └── var_registry.py             # Solver variable registry
│
├── agent/                          # ← new — agent session layer
│   ├── session.py                  # AgentSession
│   ├── tools.py                    # AgentTools (@beta_tool wrappers)
│   ├── prompt_builder.py           # SystemPromptBuilder
│   └── conversation.py             # ConversationManager
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
        ├── agent_session.puml      # ← new
        └── agent_activity.puml     # ← new
```

---

## Getting Started

```bash
pip install -r requirements.txt
python main.py
```

> Full setup and usage examples coming as MVP implementation progresses.

---

## License

MIT