from engine.commands import DefineSkill, DefineCallEnvironment, DeriveErlang, DefineRoster, Solve
from engine.result import CommandResult
from engine.context import ScenarioContext
from domain import Skill, CallEnvironment, Roster
from solver.erlang import ErlangC
from solver import ModelBuilder

class Handler:
    """Executes commands against a ScenarioContext.
    
    Methods are grouped by command family:
        - Define:  write entities directly into context
        - Derive:  compute and write derived values into context
        - Solve:   delegate to ModelBuilder (deferred)
        - Read:    read and format results from context (deferred)
    """

    def __init__(self, context: ScenarioContext) -> None:
        self._context = context
        self._model_builder = ModelBuilder()

    # ── Define ────────────────────────────────────────────────────────────────

    def handle_define_skill(self, cmd: DefineSkill) -> CommandResult:
        skill = Skill(id=cmd.id, name=cmd.name)
        self._context.skills[cmd.id] = skill
        return CommandResult.ok(f"Skill '{cmd.name}' defined.")

    def handle_define_environment(self, cmd: DefineCallEnvironment) -> CommandResult:
        env = CallEnvironment(
            skill_id=cmd.skill_id,
            weekly_volume=cmd.weekly_volume,
            aht_seconds=cmd.aht_seconds,
            aht_std_seconds=cmd.aht_std_seconds,
            operating_hours=cmd.operating_hours,
            day_weights=cmd.day_weights,
            interval_weights=cmd.interval_weights,
        )
        self._context.call_environments[cmd.skill_id] = env
        return CommandResult.ok(f"Call environment defined for skill '{cmd.skill_id}'.")

    def handle_define_roster(self, cmd: DefineRoster) -> CommandResult:
        roster = Roster(entries=cmd.entries)
        self._context.current_roster = roster
        return CommandResult.ok(f"Roster defined: {roster.total_agents} agents across {len(roster.entries)} groups.")
    # ── Derive ────────────────────────────────────────────────────────────────

    def handle_derive_erlang(self, cmd: DeriveErlang) -> CommandResult:
        if not self._context.call_environments:
            return CommandResult.fail("No call environments defined.")

        for skill_id, env in self._context.call_environments.items():
            result = ErlangC.requirements_curve(
                env=env,
                target_service_level=cmd.target_sl,
                answer_within_seconds=cmd.answer_within_seconds,
                shrinkage=cmd.shrinkage,
            )
            self._context.current_erlang[skill_id] = result

        skills_derived = list(self._context.current_erlang.keys())
        return CommandResult.ok(
        f"Erlang requirements derived for {len(skills_derived)} skill(s): {', '.join(skills_derived)}."
    )

    # ── Solve ─────────────────────────────────────────────────────────────────

    def handle_solve(self, cmd: Solve) -> CommandResult:
        self._context.invalidate_solve_results()
        result = self._model_builder.build_and_solve(self._context)
        self._context.schedule_result = result
        return CommandResult.ok(
            f"Solve complete — status: {result.status}, "
            f"total agent-slots: {result.total_agent_slots}, "
            f"coverage shortfall: {result.coverage_shortfall_slots} slot(s), "
            f"mean AWT: {result.mean_awt_seconds:.1f}s, "
            f"solve time: {result.solve_time_seconds:.3f}s"
        )

    # ── Read (deferred) ───────────────────────────────────────────────────────

    # def handle_read_result(self, cmd: ReadResult) -> CommandResult: ...
    # def handle_read_context(self, cmd: ReadContext) -> CommandResult: ...