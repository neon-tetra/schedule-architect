from __future__ import annotations

from domain import SolveResult
from engine.context import ScenarioContext

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class LLMPresenter:
    def __init__(self, context: ScenarioContext):
        self._context = context
        self._result: SolveResult = context.solve_result

    def present(self) -> str:
        sections = [
            self.summary_header(),
            self.shortfall_table(),
            self.coverage_by_skill(),
            self.worst_periods(),
        ]
        return "\n\n".join(s for s in sections if s)

    def summary_header(self) -> str:
        r = self._result
        lines = [
            f"Solve Status:     {r.status}",
            f"Solve Time:       {r.solve_time_seconds:.2f}s",
            f"Total Shortfall:  {r.shortfall.sum()} agent-slots",
            f"Roster Size:      {r.roster.total_agents} agents",
            "",
            "Shortfall by skill:",
        ]
        for skill_id, _profile in r.queues.items():
            skill_shortfall = sum(
                v for (d, s, sk), v in r.shortfall.values.items() if sk == skill_id
            )
            skill_demand = sum(
                v for (d, s, sk), v in r.demand.values.items() if sk == skill_id
            )
            pct = (skill_shortfall / skill_demand * 100) if skill_demand else 0
            lines.append(f"  {skill_id:<25} {skill_shortfall:>5} slots  ({pct:.1f}% of demand)")
        return "\n".join(lines)

    def shortfall_table(self) -> str:
        """
        For each skill: a table with rows=days, columns=hours (collapsed),
        showing shortfall count. Includes Total # and Total % rows.
        Uses tabulate for formatting.
        """
        try:
            from tabulate import tabulate
        except ImportError:
            return "[shortfall_table: tabulate not installed]"

        r = self._result
        demand_h = r.demand.collapse_to_hours()
        shortfall_h = r.shortfall.collapse_to_hours()

        all_hours = sorted(set(slot for (_, slot, _) in shortfall_h.values.keys()))
        hour_labels = [f"{h}:00" for h in all_hours]

        sections = []
        for skill_id in r.queues:
            rows = []
            total_shortfall_by_hour = {h: 0 for h in all_hours}
            total_demand_by_hour = {h: 0 for h in all_hours}

            for day in range(7):
                row = [DAY_NAMES[day]]
                for h in all_hours:
                    sf = shortfall_h.get(day, h, skill_id)
                    dm = demand_h.get(day, h, skill_id)
                    row.append(sf if dm > 0 else "-")
                    total_shortfall_by_hour[h] += sf
                    total_demand_by_hour[h] += dm
                rows.append(row)

            total_num_row = ["Total #"] + [total_shortfall_by_hour[h] for h in all_hours]
            total_pct_row = ["Total %"] + [
                f"{(total_shortfall_by_hour[h] / total_demand_by_hour[h] * 100):.0f}%"
                if total_demand_by_hour[h] else "-"
                for h in all_hours
            ]
            rows.append(total_num_row)
            rows.append(total_pct_row)

            table = tabulate(rows, headers=[""] + hour_labels, tablefmt="simple")
            sections.append(f"{skill_id}\n{table}")

        return "\n\n".join(sections)

    def coverage_by_skill(self) -> str:
        return ""

    def worst_periods(self) -> str:
        return ""
