from engine import ScenarioContext, Dispatcher
from engine.commands import Solve, ReadResult
from scenarios.default import DEFAULT_COMMANDS


def main():

    context = ScenarioContext(name="DefaultScenario")
    dispatcher = Dispatcher(context)

    for cmd in DEFAULT_COMMANDS:
        result = dispatcher.dispatch(cmd)
        status = "✓" if result.success else "✗"
        print(f"{status} {cmd.type}: {result.message}")

    result = dispatcher.dispatch(Solve())
    print(f"\n{'✓' if result.success else '✗'} solve: {result.message}")

    result = dispatcher.dispatch(ReadResult())
    if result.success:
        print(f"\n{result.data['presentation']}")
    else:
        print(f"\n✗ read_result: {result.message}")


if __name__ == "__main__":
    main()