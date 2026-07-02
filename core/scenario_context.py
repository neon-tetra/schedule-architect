import polars as pl

from core.solve_run import SolveRun
from core.frames import QUEUE_PROFILE_SCHEMA, ROSTER_SCHEMA

MAX_SOLVE_HISTORY = 5

class ScenarioContext:

    def __init__(self, profiles: pl.DataFrame, roster: pl.DataFrame):
        assert set(profiles.schema.keys()) == QUEUE_PROFILE_SCHEMA.keys(), "QueueProfile DataFrame schema mismatch."
        assert set(roster.schema.keys())   == ROSTER_SCHEMA.keys(), "Roster DataFrame schema mismatch."
        self.profiles = profiles
        self.roster   = roster
        self._solves: list[SolveRun] = []
        self._run_counter = 0

    # ── Roster ────────────────────────────────────────────────────────────────

    def update_roster(self, roster: pl.DataFrame):
        self.roster = roster

    # ── Solves ────────────────────────────────────────────────────────────────

    def next_run_id(self) -> str:
        self._run_counter += 1
        return f"run_{self._run_counter:02d}"

    def add_solve(self, result: SolveRun):
        self._solves.append(result)
        if len(self._solves) > MAX_SOLVE_HISTORY:
            self._solves.pop(0)

    def recent_solves(self) -> list[SolveRun]:
        return list(self._solves)

    # ── Dynamic prompt content ────────────────────────────────────────────────

    def get_detailed_summary(self) -> str:
        raise NotImplementedError("Detailed summary generation is not yet implemented.")

    def get_recent_solves_summary(self) -> str:
        lines = ["## Recent Solves"]
        if not self._solves:
            lines.append("  No solves run yet.")
        for r in self._solves:
            lines.append(f"  {r.run_id}: '{r.label}'")
        return "\n".join(lines)