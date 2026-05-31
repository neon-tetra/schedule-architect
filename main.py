from engine import ScenarioContext, Dispatcher
from engine.commands import Solve
from scenarios.default import DEFAULT_COMMANDS


def main():

    context = ScenarioContext(name="DefaultScenario")
    dispatcher = Dispatcher(context)

    for cmd in DEFAULT_COMMANDS:
        result = dispatcher.dispatch(cmd)
        status = "✓" if result.success else "✗"
        print(f"{status} {cmd.type}: {result.message}")

    result = dispatcher.dispatch(Solve())

    print(f"\nSolver status: {result.status}")
    print(f"Objective (total shortfall slots): {result.objective}")
    import csv
    # CSV dump of decision variables
    with open("output_schedule.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["agent", "day", "shift", "works"])
        for var_name, value in result.vars.items():
            parts = var_name.split("_")
            writer.writerow([*parts[:-2], parts[-2], parts[-1], value])

    print("Schedule written to output_schedule.csv")


if __name__ == "__main__":
    main()