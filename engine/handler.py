from engine.commands import DefineQueueProfile, DeriveErlang, DefineRoster, Solve, ReadResult
from engine.result import CommandResult
from engine.context import ScenarioContext
from domain import QueueProfile, Roster, SlotMatrix
from solver.erlang import ErlangC
from solver import ModelBuilder


class Handler:
    """Executes commands against a ScenarioContext."""

    def __init__(self, context: ScenarioContext) -> None:
        self._context = context
        self._model_builder = ModelBuilder()

    # ── Define ────────────────────────────────────────────────────────────────

    def handle_define_queue_profile(self, cmd: DefineQueueProfile) -> CommandResult:
        env = QueueProfile(
            skill_id=cmd.skill_id,
            weekly_volume=cmd.weekly_volume,
            aht_seconds=cmd.aht_seconds,
            aht_std_seconds=cmd.aht_std_seconds,
            operating_hours=cmd.operating_hours,
            day_weights=cmd.day_weights,
            interval_weights=cmd.interval_weights,
        )
        self._context.queues[cmd.skill_id] = env
        return CommandResult.ok(f"Call environment defined for skill '{cmd.skill_id}'.")

    def handle_define_roster(self, cmd: DefineRoster) -> CommandResult:
        roster = Roster(entries=cmd.entries)
        self._context.current_roster = roster
        return CommandResult.ok(f"Roster defined: {roster.total_agents} agents across {len(roster.entries)} groups.")

    # ── Derive ────────────────────────────────────────────────────────────────

    def handle_derive_erlang(self, cmd: DeriveErlang) -> CommandResult:
        if not self._context.queues:
            return CommandResult.fail("No call environments defined.")

        demand_values: dict[tuple[int, int, str], int] = {}
        for skill_id, env in self._context.queues.items():
            result = ErlangC.requirements_curve(
                env=env,
                target_service_level=cmd.target_sl,
                answer_within_seconds=cmd.answer_within_seconds,
                shrinkage=cmd.shrinkage,
            )
            demand_values.update(result.values)

        self._context.demand = SlotMatrix(label="demand", values=demand_values)
        skills_derived = list(self._context.queues.keys())
        return CommandResult.ok(
            f"Erlang requirements derived for {len(skills_derived)} skill(s): {', '.join(skills_derived)}."
        )

    # ── Solve ─────────────────────────────────────────────────────────────────

    def handle_solve(self, cmd: Solve) -> CommandResult:
        roster = self._context.current_roster
        queues = self._context.queues
        demand = self._context.demand

        self._context.invalidate_solve_results()
        result = self._model_builder.build_and_solve(roster, queues, demand)
        self._context.solve_result = result
        return CommandResult.ok(f"Solve complete. Status: {result.status}. Shortfall slots: {result.shortfall.sum()}.")

    # ── Read ──────────────────────────────────────────────────────────────────

    def handle_read_result(self, cmd: ReadResult) -> CommandResult:
        if self._context.solve_result is None:
            return CommandResult.fail("No solve result available. Run solve first.")
        from engine.presenter import LLMPresenter
        presenter = LLMPresenter(self._context)
        return CommandResult.ok("Result ready.", data={"presentation": presenter.present()})

    # Deferred
    # def handle_read_context(self, cmd: ReadContext) -> CommandResult: ...