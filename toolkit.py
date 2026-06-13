import json
from pydantic import BaseModel
from scenario_context import ScenarioContext
from domain import RosterEntry, Roster

# ── Input DTOs ────────────────────────────────────────────────────────────────

class DefineRosterInput(BaseModel):
    entries: list[dict]   # [{skills: [...], count: int}, ...]

class RunSolveInput(BaseModel):
    label: str            # e.g. "Initial Run" or "Add 2 Photo + 2 Floral"

# ── Shared status result (returned after every tool call) ─────────────────────

class StatusResult(BaseModel):
    run_id:       str | None = None
    label:        str | None = None
    roster:       str        = ""
    recent_solves: str       = ""

    def to_tool_string(self) -> str:
        lines = [f"Roster:\n{self.roster}"]
        if self.recent_solves:
            lines.append(f"Recent Solves:\n{self.recent_solves}")
        if self.run_id:
            lines.append(f"Last solve: {self.run_id} '{self.label}'")
        return "\n\n".join(lines)

# ── Toolkit ───────────────────────────────────────────────────────────────────

class Toolkit:

    def __init__(self, context: ScenarioContext):
        self._context = context

    # TODO: (A) enrich this output with queue profile data and solve history formatting
    #       (B) consider a separate condensed summary variant for mid-session use
    def get_detailed_summary(self) -> str:
        return self._context.get_detailed_summary()

    def get_recent_solves_summary(self) -> str:
        """Returns a formatted summary of recent solve results for inclusion in the dynamic
        section of the system prompt. Rebuilt each turn so Claude always sees current results."""
        solves = self._context.recent_solves()
        if not solves:
            return "## Recent Solves\n  No solves run yet."
        lines = ["## Recent Solves"]
        for r in solves:
            lines.append(
                f"  {r.run_id}: '{r.label}' | {r.total_agents} agents | "
                f"${r.monthly_cost:,.0f}/mo | {r.coverage_pct:.1f}% coverage"
            )
        return "\n".join(lines)

    def get_tool_list(self) -> list[dict]:
        return [
            {
                "name": "define_roster",
                "description": "Replace the entire agent roster with a new set of entries.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "entries": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "skills": {"type": "array", "items": {"type": "string"}},
                                    "count":  {"type": "integer"}
                                },
                                "required": ["skills", "count"]
                            }
                        }
                    },
                    "required": ["entries"]
                }
            },
            {
                "name": "run_solve",
                "description": "Run the workforce optimisation solver against the current roster. Give the run a short descriptive label, e.g. 'Initial Run' or 'Add 2 Photo + 2 Floral'.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"}
                    },
                    "required": ["label"]
                }
            },
            {
                "name": "query_status",
                "description": "Get the current roster and recent solve results.",
                "input_schema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]

    def execute(self, tool_name: str, tool_input: dict) -> str:
        if tool_name == "define_roster":
            return self._define_roster(DefineRosterInput(**tool_input))
        elif tool_name == "run_solve":
            return self._run_solve(RunSolveInput(**tool_input))
        elif tool_name == "query_status":
            return self._query_status()
        return json.dumps({"error": f"unknown tool: {tool_name}"})

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _define_roster(self, inp: DefineRosterInput) -> str:
        entries = [RosterEntry(**e) for e in inp.entries]
        roster  = Roster(entries=entries)
        self._context.update_roster(roster)
        return self._status().to_tool_string()

    def _run_solve(self, inp: RunSolveInput) -> str:
        # stub — solver call goes here, result stored in context
        # NOTE: solver is sync — CP-SAT solves in <100ms, no async needed
        run_id = self._context.next_run_id()
        return self._status(run_id=run_id, label=inp.label).to_tool_string()

    def _query_status(self) -> str:
        return self._status().to_tool_string()

    # ── Status builder (shared by all handlers) ───────────────────────────────

    def _status(self, run_id: str | None = None, label: str | None = None) -> StatusResult:
        roster_str = self._context.roster.summary(
            {p.skill_id: p for p in self._context.profiles}
        )
        solves_str = "\n".join(
            f"  {r.run_id}: '{r.label}' | {r.total_agents} agents | "
            f"${r.monthly_cost:,.0f}/mo | {r.coverage_pct:.1f}% coverage"
            for r in self._context.recent_solves()
        ) or "No solves yet."

        return StatusResult(
            run_id=run_id,
            label=label,
            roster=roster_str,
            recent_solves=solves_str,
        )