from engine.commands import DefineSkill, DefineCallEnvironment, DeriveErlang, DefineRoster
from engine.result import CommandResult
from engine.context import ScenarioContext
from domain import Skill, CallEnvironment, Roster


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
        # self._model_builder = ModelBuilder()  # Deferred

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
        raise NotImplementedError

    # ── Solve (deferred) ──────────────────────────────────────────────────────

    # def handle_solve(self, cmd: Solve) -> CommandResult: ...

    # ── Read (deferred) ───────────────────────────────────────────────────────

    # def handle_read_result(self, cmd: ReadResult) -> CommandResult: ...
    # def handle_read_context(self, cmd: ReadContext) -> CommandResult: ...