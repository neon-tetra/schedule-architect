# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

```powershell
# Install dependencies
pip install -r requirements.txt

# Set API key (PowerShell)
$env:ANTHROPIC_API_KEY = "your_key_here"

# Launch the Chainlit UI
chainlit run app.py
```

There are no automated tests or lint scripts configured.

### `dfor` dependency (one-time venv setup)

`solver/` builds its CP-SAT model through `dfor` — a sibling project at
`active/dfor/`, developed in place rather than installed as a package. It's
made importable (`from problem import Problem`, `import model_view`, etc.,
with no `sys.path` code needed in this repo) via a `.pth` file:

```
schedule-architect/.venv/Lib/site-packages/dfor.pth
```

containing a single line, the absolute path to the dfor directory:

```
C:\neon_tetra\active\dfor
```

This lives inside `.venv`, which is gitignored, so it does **not** survive a
fresh clone or a rebuilt venv — recreate this file (same path, same single
line) any time the venv is rebuilt from `requirements.txt`. If `dfor` ever
gets packaged/published properly, this step goes away in favor of a normal
`pip install`.

## Architecture overview

Schedule Architect is a conversational workforce planning agent. The user directs a call centre staffing scenario through natural language; the agent calls tools to mutate the model, runs a CP-SAT optimiser, and surfaces results as Plotly charts mid-conversation.

### Current branch: `refactor/event-queue-mediator`

The codebase is mid-refactor. The previous architecture (a synchronous, direct-call stack) lives in `_legacy/` and is the reference implementation. The refactor replaces it with an async event-queue/mediator pattern. The root-level `domain/`, `engine/`, `agent/`, and `solver/` directories are currently empty stubs — they will be populated as the refactor progresses.

### Event flow (new architecture)

```
Chainlit browser
    → app.py          (Chainlit hooks — on_chat_start / on_message)
    → chat_session.py (ChatSession — creates Queue + MediatorLoop, returns immediately)
    → events.py       (Event dataclass with EventSource + EventType enums)
    → mediator.py     (MediatorLoop — async event loop, handler dispatch table)
    → agent_session.py (AgentSession — owns conversation history, builds API payload)
    → Anthropic API
```

The gateway (`app.py`) puts an `Event` onto the queue and returns immediately. `MediatorLoop.run()` is a persistent `asyncio` task that consumes events one at a time. Anthropic streaming callbacks also post events back onto the queue — text deltas are written directly to the Chainlit message stream, while `FINAL_RESPONSE` and `TOOL_REQUEST` events go through the mediator loop. `DebugLogger` wraps the queue to log every enqueue/dequeue at DEBUG level.

### Conversation compression

`AgentSession` instructs the model to wrap every response in `<<summary>>...</summary>>` tags. `MediatorLoop._handle_final_response()` strips this tag from the displayed message and stores only the summary text in conversation history. This keeps history compact without a separate summarisation call.

### Prompt caching (legacy pattern, to be ported)

`SystemPromptBuilder` in `_legacy/agent/prompt_builder.py` splits the system prompt at a `CACHE_BOUNDARY` marker. Everything before the boundary is sent with `cache_control: {"type": "ephemeral"}` so the static role/behaviour sections are cached across turns; the dynamic scenario state section is appended fresh each turn.

### Command / Query separation (legacy pattern, to be ported)

`_legacy/engine/dispatcher.py` separates two kinds of engine calls:
- `dispatch(cmd: ModelCommand)` — state-mutating commands (`define_queue_profile`, `derive_erlang`, `define_roster`, `solve`)
- `retrieve(query: ModelQuery)` — read-only queries (`query_status`)

This distinction is preserved in tool naming and should be maintained when porting the engine layer.

### Key files

| File | Role |
|---|---|
| `app.py` | Chainlit entry point — hooks only, no logic |
| `chat_session.py` | Wires queue + mediator; one instance per browser session |
| `mediator.py` | `MediatorLoop` — the central async event dispatcher |
| `agent_session.py` | Conversation history + Anthropic payload assembly |
| `events.py` | `Event`, `EventType`, `EventSource` definitions |
| `config.py` | `MODEL`, `MAX_TOKENS`, `TOOL_SCHEMAS` constants |
| `debug_logger.py` | Queue wrapper that logs every event at DEBUG level |
| `_legacy/` | Full working implementation — reference for porting |
| `docs/` | C4 architecture diagrams + agent turn sequence diagram (PlantUML) |
