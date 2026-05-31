# Session Notes — schedule-architect

## Current State

Domain layer refactored and committed. Engine layer changes written but not yet committed.

### Domain — done ✅
- `domain/queue_profile.py` — `QueueProfile` (renamed from `CallEnvironment`)
- `domain/slot_matrix.py` — `SlotMatrix` (new, replaces `ErlangResult`)
- `domain/schedule.py` — `SolveResult` (replaces `ScheduleResult`)
- `domain/__init__.py` — updated exports

### Files to delete
- `domain/call_environment.py` — superseded by `queue_profile.py`
- `domain/erlang.py` — `ErlangResult` is gone, logic lives in `solver/erlang.py`

---

## Next Session — Order of Operations

### 1. Engine layer (changes written, ready to commit)
- `engine/context.py` — `queues`, `demand`, `solve_result` fields
- `engine/commands.py` — `ReadResult` promoted, `output_id` removed from `DeriveErlang`, union updated
- `engine/handler.py` — `QueueProfile`, unified demand `SlotMatrix`, `handle_solve` and `handle_read_result` implemented
- `engine/dispatcher.py` — `read_result` wired in

### 2. Solver layer
- `solver/erlang.py` — `requirements_curve` returns `SlotMatrix` keyed by `(day, slot, skill_id)`
- `solver/model_builder.py` — reads `context.demand`, builds `supply` SlotMatrix post-solve, returns `SolveResult`

### 3. New file
- `engine/presenter.py` — `LLMPresenter` with `summary_header()` and `shortfall_table()`

### 4. Entrypoint
- `main.py` — remove CSV writer, dispatch `Solve` then `ReadResult`, print presentation

### 5. Smoke test
- Run `python main.py` end to end, verify output

### 6. Housekeeping
- Add `output_schedule.csv` to `.gitignore`
- Confirm old domain files deleted

---

## Post-MVP Levers (agreed, not yet scoped)

| Command | What it changes | Why it matters |
|---|---|---|
| `AdjustRoster` | Agent count on an existing group, or add a new group | Most direct "hire/train" analog |
| `AdjustTargets` | SL target or shrinkage per skill | "Lower the bar" lever — important for feasibility analysis |
| Shift start menu | Add/remove valid shift start times | Resolves early/late shortfalls the current model can't reach — post-MVP due to model complexity |

---

## Key Design Decisions (for context in new sessions)

- **`SlotMatrix`** is a domain primitive, not a solver artifact — lives in `domain/slot_matrix.py`
- **`SolveResult`** bundles demand + supply + shortfall as three `SlotMatrix` instances — presenter operates on this bundle
- **`LLMPresenter`** has no solver imports — it only reads from `SolveResult`
- **`handle_derive_erlang`** merges per-skill SlotMatrix values into one unified `context.demand` — single matrix for all skills
- **`for_x` filtering methods** on `SlotMatrix` were considered and rejected — thin is better, aggregation via dict comprehension at call site
- **`output_id`** removed from `DeriveErlang` — registry pattern deferred, single demand matrix is sufficient for MVP