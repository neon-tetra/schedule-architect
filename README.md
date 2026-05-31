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
├── domain/          # Core entities (Skill, QueueProfile, SlotMatrix, Roster, SolveResult)
├── engine/          # Dispatcher, Handler, ScenarioContext, commands, LLMPresenter
├── solver/          # ErlangC, ModelBuilder, VarRegistry
├── scenarios/       # Saved scenario configurations
├── data/            # Reference data and interval weights
├── docs/            # UML architecture documents (PlantUML source)
└── README.md
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