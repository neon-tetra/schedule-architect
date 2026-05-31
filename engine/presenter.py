from engine.context import ScenarioContext
from engine.solve_result import SolveResult

class LLMPresenter:

    def __init__(self, result: SolveResult) -> None:
        self._result = result

    def present(self) -> str:
        if self._result is None:
            return "No solve result available."

        presentation = self.summary_header()
        presentation += "\n\n" + self.shortfall_table()
        # presentation += "\n\n" + self.coverage_by_skill()
        # presentation += "\n\n" + self.worst_periods()
        return presentation

    def summary_header(self) -> str:
        return f"Solve Status: {self._result.status}\nTotal Shortfall Slots: {self._result.shortfall.sum()}"

    def shortfall_table(self) -> str:
        lines = ["Shortfall by Day and Skill:"]
        lines.append(f"{'Day':<10} {'Skill':<10} {'Shortfall':<10}")
        for (day, skill_id), shortfall in sorted(self._result.shortfall.items()):
            lines.append(f"{day:<10} {skill_id:<10} {shortfall:<10}")
        return "\n".join(lines)

    # Deferred methods for deeper insights
    # def coverage_by_skill(self) -> str: ...
    # def worst_periods(self) -> str: ...