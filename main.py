from engine import ScenarioContext, Dispatcher, QueryStatus
from engine.commands import Solve
from engine.presenter import LLMPresenter
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

    result = dispatcher.retrieve(QueryStatus())
    if result.success:
        if context.solve_result is not None:
            presentation = LLMPresenter(context.solve_result).present()
            print(f"\n{presentation}")
            open("output_presentation.txt", "w").write(presentation)

        if result.data and result.data.get("roster") is not None and context.current_roster is not None:
            roster_data = result.data["roster"]
            print(f"\n📋 Roster Breakdown:\n{context.current_roster.summary(context.queues)}")
            if roster_data["monthly_cost"] is not None:
                print(f"\n💰 Total monthly roster cost: ${roster_data['monthly_cost']:,.0f}")
    else:
        print(f"\n✗ query_status: {result.message}")


if __name__ == "__main__":
    main()