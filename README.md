# schedule-architect

A conversational workforce planning agent for call centre operations. It introduces the user to a scheduling scenario, guides them through building and optimising a staffing model, and surfaces results as interactive charts — all through natural language.

Designed architecture-first, built layer by layer.

---

## What It Does

Schedule Architect puts the user in the seat of a workforce planner working a real call centre scenario. The agent knows the domain, holds the model state, and helps them understand the tradeoffs.

A typical session looks like this:

> The agent opens with a structured welcome — here's the scenario, here's what we know, here's where to start.
> The user directs the session: adjust roster headcount, change skill assignments, set service level targets.
> The agent translates that into a structured model, runs the CP-SAT optimiser, and surfaces the results as charts and commentary directly in the conversation.
> From there it's a loop — the agent identifies the worst coverage gaps, suggests what to change, the user adjusts, and the model re-solves. Each iteration is visible, reasoned, and grounded in the numbers.

The goal isn't to produce a perfect schedule in one shot. It's to give a workforce planner a genuinely useful thinking partner.

---

## Architecture

The system is organised into six layers, designed before implementation and documented as living UML artifacts in `/docs`.

![Component Diagram](docs/architecture_component.png)

| Layer | Responsibility |
|---|---|
| **Domain** | Core entities — skills, queue profiles, slot matrices, rosters |
| **Engine** | Command dispatcher, handler, scenario context, retrieval layer |
| **Solver** | Erlang C demand derivation and CP-SAT model builder |
| **Agent** | LLM session layer — prompt assembly, conversation management, tool wrappers |
| **Presentation** | Chart building — Plotly figures from retrieval results |
| **Caller** | Entry point — wires context, dispatcher, and agent session into a live Chainlit app |

Full design documents: [`/docs`](./docs)

---

## AI-Assisted Development

This project was developed using a hybrid workflow: architecture-first design (UML), followed by iterative implementation using GitHub Copilot and agent-assisted scaffolding. All generated code was reviewed, understood, and integrated deliberately.

This reflects how I work in real engineering environments — using AI tools to accelerate development while maintaining full ownership of architecture, correctness, and system behavior.

---

## MVP Features

- Guided opening — scripted welcome sets the scenario before any API call is made
- Guardrailed scenario — the user works within a defined call centre model, directing roster changes and targets through natural language
- Define an agent roster from skill groups and headcounts
- Derive Erlang C staffing requirements from call volume, AHT, and SLA targets
- CP-SAT schedule optimisation minimising coverage shortfall across all skills and intervals
- Solve result surfaced as interactive Plotly charts, mid-conversation, as a side effect of the agent's tool loop
- `QueryStatus` retrieval — agent orients itself each turn with a single call: roster, cost, and latest solve summary
- Retrieval / tool / memory architecture following Anthropic's vocabulary — clean separation between state-mutating commands and read-only retrievals
- Prompt caching — static system prompt prefix cached across turns to minimise token cost
- Chainlit front end — charts and conversation in one interface

---

## Roadmap

| MVP ✓ | V2 |
|---|---|
| Domain entities | Constraint template registry |
| Command dispatcher + handler | Bespoke constraint authoring via agent |
| Erlang C derivation | Weighted and conditional shortfall penalties |
| CP-SAT solve | Coverage ratio and floor constraints |
| `QueryStatus` retrieval | Parameterizable objective function |
| Agent session + tool use | Define skills and queue profiles via natural language |
| Prompt caching | Multi-scenario session management |
| Guided conversational session | Schedule types and shift templates |
| Chainlit front end + Plotly charts | Full simulation and schedule evaluation |

---

## Project Structure

```
schedule-architect/
│
├── app.py                          # Chainlit entry point
├── requirements.txt
├── .env.example
├── test_solver.py                  # Solver smoke test (roster -> Erlang C -> solve)
├── test_presentation.py            # Presentation smoke test
│
├── core/                           # Scenario state and data frames
│   ├── frames.py                   # Polars frame schemas
│   ├── scenario_context.py         # ScenarioContext
│   ├── solve_run.py                # SolveRun
│   └── scenarios/
│       └── default.py              # Default scenario definition
│
├── solver/                         # Optimisation layer
│   ├── erlang.py                   # Erlang C staffing calculations
│   ├── scheduler.py                # CP-SAT model construction + solve (uses dfor)
│   ├── shift_patterns.py           # Shift pattern definitions
│   ├── model_design.md
│   └── scheduler planning.txt
│
├── agent/                          # LLM agent session layer
│   ├── agent_session.py            # AgentSession — turn lifecycle
│   ├── toolkit.py                  # Toolkit — tool wrappers
│   ├── prompts.py                  # System prompt sections
│   └── response_parser.py          # Response parsing
│
├── presentation/                   # Presentation layer
│   ├── kpi_chart.py
│   ├── volume_chart.py
│   ├── theme.py
│   └── plotly_sandbox.py
│
├── scratch/                        # Scratch files and experiment output
│
└── docs/                           # Architecture diagrams (UML / C4)
```

---

## Getting Started

`dfor` is a required dependency (the CP-SAT model layer used by `solver/`). It is not on PyPI: get it from https://github.com/neon-tetra/dfor and make it importable (e.g. `pip install -e <path-to-dfor>`).

```bash
pip install -r requirements.txt

# Solver smoke test (no agent)
python test_solver.py

# Conversational agent session
$env:ANTHROPIC_API_KEY = "your_key_here"   # PowerShell
# export ANTHROPIC_API_KEY="your_key_here" # bash
chainlit run app.py
```

---

## V2 Vision

The next major milestone is a **constraint template registry** — a bounded vocabulary of named, parameterizable constraint patterns that the agent can select, configure, and compose at runtime. This moves the system from a guided scenario into a genuinely open workforce planning tool.

Example targets:
> *"There must be at least one photo agent starting at 8am every day"*
> *"If escalation coverage drops below 10% of total agents, double the shortfall penalty"*

---

## License

MIT
