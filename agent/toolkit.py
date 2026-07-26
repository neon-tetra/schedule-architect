import json
import polars as pl
from pydantic import BaseModel
from   core.scenario_context import ScenarioContext
from   core.solve_run        import SolveRun
from   core.frames           import INTERVAL_SCHEMA
from solver.erlang           import ErlangC
from solver.scheduler        import build_and_solve

from core.scenarios.default import DF_QUEUE_PROFILES, DF_STARTING_ROSTER

# ── Input DTOs ────────────────────────────────────────────────────────────────

class DefineRosterInput(BaseModel):
    entries: list[dict]   # [{skills: [...], count: int}, ...]

class RunSolveInput(BaseModel):
    label: str            # e.g. "Initial Run" or "Add 2 Photo + 2 Floral"

# ── Shared status result (returned after every tool call) ─────────────────────

class StatusResult(BaseModel):
    run_id:        str | None = None
    label:         str | None = None
    roster:        str        = ""
    recent_solves: str        = ""

    def to_tool_string(self) -> str:
        lines = [f"Roster:\n{self.roster}"]
        if self.recent_solves:
            lines.append(f"Recent Solves:\n{self.recent_solves}")
        if self.run_id:
            lines.append(f"Last solve: {self.run_id} '{self.label}'")
        return "\n\n".join(lines)

# ── Toolkit ───────────────────────────────────────────────────────────────────

class Toolkit:

    def __init__(self):
        self._context = ScenarioContext(profiles=DF_QUEUE_PROFILES, roster=DF_STARTING_ROSTER)

    # TODO: (A) enrich this output with queue profile data and solve history formatting
    #       (B) consider a separate condensed summary variant for mid-session use
    def get_detailed_summary(self) -> str:
        return self._context.get_detailed_summary()

    def get_recent_solves_summary(self) -> str:
        return self._context.get_recent_solves_summary()

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
        # NOTE: sync/blocking — CP-SAT solves in <100ms, no async needed
        run_id = self._context.next_run_id()
        queues = self._context.profiles

        # Derive demand across all queues via Erlang C
        df_intervals = pl.DataFrame(
            schema=INTERVAL_SCHEMA,
        )
        #for each row in profiles polars df
        for profile in queues.iter_rows(named=True):
            curve = ErlangC.requirements_curve(env=profile)
            df_intervals = df_intervals.vstack(curve)

        

        # Build and solve
        result = build_and_solve(
            roster=self._context.roster,
            queues=queues,
            intervals=df_intervals,
        )
        result.run_id = run_id
        result.label  = inp.label
        self._context.add_solve(result)

        return self._status(run_id=run_id, label=inp.label).to_tool_string()

    def _query_status(self) -> str:
        return self._status().to_tool_string()

    # ── Status builder (shared by all handlers) ───────────────────────────────

    def _status(self, run_id: str | None = None, label: str | None = None) -> StatusResult:
        # self._context.roster is a plain DataFrame (see ScenarioContext),
        # not a Roster object -- no such wrapper class exists in this
        # codebase yet. A real per-skill summary (using profiles) is
        # unbuilt, matching get_detailed_summary()'s NotImplementedError
        # above; this is just the crash-free stand-in.
        roster_str = str(self._context.roster)
        solves_str = "\n".join(
            f"  {r.run_id}: '{r.label}'"
            for r in self._context.recent_solves()
        ) or "No solves yet."

        return StatusResult(
            run_id=run_id,
            label=label,
            roster=roster_str,
            recent_solves=solves_str,
        )
    
    def _get_last_solve(self) -> SolveRun | None:
        recent = self._context.recent_solves()
        return recent[0] if recent else None

# import polars as pl
# class RemoveRosterEntryInput(BaseModel):
#     primary_skill:   str
#     secondary_skill: str | None = None
#     model_config = {"extra": "forbid"}

# def _remove_roster_entry(self, inp: RemoveRosterEntryInput) -> str:
#     self._context.roster = self._context.roster.filter(
#         ~(
#             (pl.col("primary_skill") == inp.primary_skill) &
#             (
#                 pl.col("secondary_skill").is_null() if inp.secondary_skill is None
#                 else pl.col("secondary_skill") == inp.secondary_skill
#             )
#         )
#     )
#     return self._status().to_tool_string()
# class AddRosterEntryInput(BaseModel):
#     primary_skill:   str
#     secondary_skill: str | None = None
#     count:           int

#     model_config = {"extra": "forbid"}

# class DefineRosterInput(BaseModel):
#     entries: list[RosterEntryInput]

#     @field_validator("entries")
#     @classmethod
#     def at_least_one(cls, v):
#         if not v:
#             raise ValueError("Roster must have at least one entry")
#         return v
    
# def _define_roster(self, inp: DefineRosterInput) -> str:
#     roster_df = pl.DataFrame(
#         [e.model_dump() for e in inp.entries],
#         schema=ROSTER_SCHEMA,
#     )
#     self._context.update_roster(roster_df)
#     return self._status().to_tool_string()