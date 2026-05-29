# schedule-architect

A workforce scheduling agent that translates natural language inputs into optimized shift schedules using a structured command engine and CP-SAT constraint programming.

Designed architecture-first, built layer by layer.

---

## Architecture

The system is organized into four layers, designed before implementation and documented as living UML artifacts in `/docs`.

![Component Diagram](docs/architecture_component.png)

| Layer | Responsibility |
|---|---|
| **Domain** | Core entities — skills, call environments, Erlang results, rosters |
| **Engine** | Command dispatcher, handler, and scenario context |
| **Solver** | CP-SAT model builder and optimizer |
| **Caller** | LLM agent — submits commands, reads results |

Full design documents: [`/docs`](./docs)

---

## AI-Assisted Development

This project was developed using a hybrid workflow: architecture-first design (UML), followed by iterative implementation using GitHub Copilot and agent-assisted scaffolding. All generated code was manually reviewed, refined, and integrated within a deliberate system design.

This reflects how I work in real engineering environments — using AI tools to accelerate development while maintaining full ownership of architecture, correctness, and system behavior.

---

## MVP Features

- Define skills and call environments via structured commands
- Derive Erlang C staffing requirements from call volume and SLA targets
- Derive an initial agent roster from staffing requirements
- LLM-driven session via a typed command API
- CP-SAT schedule optimization against derived roster constraints

---

## Roadmap

| MVP | Planned |
|---|---|
| Domain entities | Schedule types and shift templates |
| Command dispatcher + handler | LLM-driven constraint injection |
| Erlang C derivation | Multi-scenario session management |
| Roster derivation | Model variable and objective tuning |
| CP-SAT solve (hardcoded model) | Full ModelBuilder command vocabulary |
| Read result command | Simulation and schedule evaluation |

---

## Project Structure

```
schedule-architect/
├── domain/          # Core entities (Skill, CallEnvironment, ErlangResult, Roster)
├── engine/          # Dispatcher, Handler, ScenarioContext, commands
├── solver/          # ModelBuilder and CP-SAT integration
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