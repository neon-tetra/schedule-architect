from engine import ScenarioContext, Dispatcher
from engine.commands import DefineSkill, DefineCallEnvironment, DeriveErlang, DefineRoster
from scenarios.default import ( # Messy for now, ideally we go straight from pydantic json to command object
    SKILL_EN_ID, SKILL_EN_NAME,
    SKILL_ES_ID, SKILL_ES_NAME,
    ENV_EN_WEEKLY_VOLUME, ENV_EN_AHT_SECONDS, ENV_EN_AHT_STD_SECONDS,
    ENV_EN_OPERATING_HOURS, ENV_EN_DAY_WEIGHTS, ENV_EN_INTERVAL_WEIGHTS,
    ENV_ES_WEEKLY_VOLUME, ENV_ES_AHT_SECONDS, ENV_ES_AHT_STD_SECONDS,
    ENV_ES_OPERATING_HOURS, ENV_ES_DAY_WEIGHTS, ENV_ES_INTERVAL_WEIGHTS,
    DEFAULT_TARGET_SL, DEFAULT_ANSWER_WITHIN_SECONDS,
    DEFAULT_SHRINKAGE, DEFAULT_ROSTER_ENTRIES,
)
from solver.model_builder import ModelBuilder

def main():
    context = ScenarioContext(name="DefaultScenario")
    dispatcher = Dispatcher(context)

    commands = [
        DefineSkill(id=SKILL_EN_ID, name=SKILL_EN_NAME),
        DefineSkill(id=SKILL_ES_ID, name=SKILL_ES_NAME),
        DefineCallEnvironment(
            skill_id=SKILL_EN_ID,
            weekly_volume=ENV_EN_WEEKLY_VOLUME,
            aht_seconds=ENV_EN_AHT_SECONDS,
            aht_std_seconds=ENV_EN_AHT_STD_SECONDS,
            operating_hours=ENV_EN_OPERATING_HOURS,
            day_weights=ENV_EN_DAY_WEIGHTS,
            interval_weights=ENV_EN_INTERVAL_WEIGHTS,
        ),
        DefineCallEnvironment(
            skill_id=SKILL_ES_ID,
            weekly_volume=ENV_ES_WEEKLY_VOLUME,
            aht_seconds=ENV_ES_AHT_SECONDS,
            aht_std_seconds=ENV_ES_AHT_STD_SECONDS,
            operating_hours=ENV_ES_OPERATING_HOURS,
            day_weights=ENV_ES_DAY_WEIGHTS,
            interval_weights=ENV_ES_INTERVAL_WEIGHTS,
        ),
        DeriveErlang(
            target_sl=DEFAULT_TARGET_SL,
            answer_within_seconds=DEFAULT_ANSWER_WITHIN_SECONDS,
            shrinkage=DEFAULT_SHRINKAGE,
        ),
        DefineRoster(
            entries=DEFAULT_ROSTER_ENTRIES,
        ),
    ]

    for cmd in commands:
        result = dispatcher.dispatch(cmd)
        status = "✓" if result.success else "✗"
        print(f"{status} {cmd.type}: {result.message}")
    
    # Build and solve model
    model_builder = ModelBuilder()
    schedule_result = model_builder.build_and_solve(context)

    print(f"\nSolver status: {schedule_result.status}")
    print(f"Objective (total shortfall slots): {schedule_result.objective}")
    import csv
    # CSV dump of decision variables
    with open("output_schedule.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["agent", "day", "shift", "works"])
        for var_name, value in schedule_result.vars.items():
            parts = var_name.split("_")
            writer.writerow([*parts[:-2], parts[-2], parts[-1], value])

    print("Schedule written to output_schedule.csv")


if __name__ == "__main__":
    main()