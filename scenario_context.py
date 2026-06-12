from domain import QueueProfile, RosterEntry, Roster, SolveResult

MAX_SOLVE_HISTORY = 5

class ScenarioContext:

    def __init__(self, profiles: list[QueueProfile], roster: Roster):  # Roster not list
        self.profiles = profiles
        self.roster   = roster                                          # Roster object
        self._solves: list[SolveResult] = []
        self._run_counter = 0

    # ── Roster ────────────────────────────────────────────────────────────────

    def update_roster(self, roster: Roster):                           # Roster not list
        self.roster = roster

    # ── Solves ────────────────────────────────────────────────────────────────

    def next_run_id(self) -> str:
        self._run_counter += 1
        return f"run_{self._run_counter:02d}"

    def add_solve(self, result: SolveResult):
        self._solves.append(result)
        if len(self._solves) > MAX_SOLVE_HISTORY:
            self._solves.pop(0)

    def recent_solves(self) -> list[SolveResult]:
        return list(self._solves)

    # ── Dynamic prompt content ────────────────────────────────────────────────

    def get_detailed_summary(self) -> str:
        lines = ["## Current Roster"]
        for e in self.roster.entries:
            lines.append(f"  {' + '.join(e.skills)}: {e.count} agents")

        lines.append("\n## Recent Solves")
        if not self._solves:
            lines.append("  No solves run yet.")
        for r in self._solves:
            lines.append(
                f"  {r.run_id}: '{r.label}' | "
                f"{r.total_agents} agents | "
                f"${r.monthly_cost:,.0f}/mo | "
                f"{r.coverage_pct:.1f}% coverage"
            )
        return "\n".join(lines)