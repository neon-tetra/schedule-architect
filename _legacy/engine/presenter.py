import json
from engine.solve_result import SolveResult

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class LLMPresenter:

    def __init__(self, result: SolveResult) -> None:
        self._result = result

    def present(self) -> str:
        presentation = self.summary_header()
        presentation += "\n\n" + self.shortfall_table()
        return presentation

    def present_json(self) -> dict:
        """Return a compact structured summary for agent consumption.
        
        Carries full day x hour granularity per skill in explicit key-value
        form — no positional encoding. Designed to be stored in tool result
        history rather than rendered as ASCII.
        """
        table_data = self._build_shortfall_table_data()
        skills_summary = {}

        for skill_id, days in table_data.items():
            total_shortfall = 0
            total_demand = 0
            worst_pct = 0
            worst_label = None
            by_day = {}

            for day_idx, hours in days.items():
                day_name = DAY_NAMES[day_idx]
                day_shortfall = 0
                day_demand = 0
                day_worst_pct = 0
                day_worst_hour = None
                hours_out = {}

                for hour, cell in hours.items():
                    sf = cell["shortfall"]
                    dm = cell["demand"]
                    pct = round(100 * sf / dm) if dm > 0 else 0
                    hours_out[f"{hour:02d}:00"] = {
                        "shortfall": sf,
                        "demand": dm,
                        "shortfall_pct": pct,
                    }
                    day_shortfall += sf
                    day_demand += dm
                    if pct > day_worst_pct:
                        day_worst_pct = pct
                        day_worst_hour = f"{hour:02d}:00"

                total_shortfall += day_shortfall
                total_demand += day_demand
                day_pct = round(100 * day_shortfall / day_demand) if day_demand > 0 else 0
                if day_pct > worst_pct:
                    worst_pct = day_pct
                    worst_label = f"{day_name}"

                by_day[day_name] = {
                    "shortfall": day_shortfall,
                    "demand": day_demand,
                    "shortfall_pct": day_pct,
                    "worst_hour": day_worst_hour,
                    "by_hour": hours_out,
                }

            skills_summary[skill_id] = {
                "total_shortfall": total_shortfall,
                "total_demand": total_demand,
                "shortfall_pct": round(100 * total_shortfall / total_demand) if total_demand > 0 else 0,
                "worst_day": worst_label,
                "by_day": by_day,
            }

        return {
            "status": self._result.status,
            "solve_time_seconds": round(self._result.solve_time_seconds, 2),
            "total_shortfall": self._result.shortfall.sum(),
            "by_skill": skills_summary,
        }

    def summary_header(self) -> str:
        total = self._result.shortfall.sum()
        status = self._result.status
        skills = ", ".join(sorted(self._result.shortfall.skills())) if self._result.shortfall.skills() else "none"
        return (
            f"Solve Status:         {status}\n"
            f"Total Shortfall:      {total} agent-intervals\n"
            f"Skills modelled:      {skills}"
        )

    def shortfall_table(self) -> str:
        table_data = self._build_shortfall_table_data()
        return self._render_shortfall_table(table_data)

    # ── Data preparation ──────────────────────────────────────────────────

    def _build_shortfall_table_data(self) -> dict:
        """Build a nested dict of shortfall and demand by skill, day, and hour."""
        shortfall_hourly = self._result.shortfall.collapse_to_hours(agg="sum")
        demand_hourly = self._result.demand.collapse_to_hours(agg="sum")

        table_data: dict = {}
        for (day, hour, skill_id), shortfall_val in shortfall_hourly.values.items():
            demand_val = demand_hourly.values.get((day, hour, skill_id), 0)
            table_data \
                .setdefault(skill_id, {}) \
                .setdefault(day, {}) \
                [hour] = {
                    "shortfall": shortfall_val,
                    "demand": demand_val,
                }
        return table_data

    # ── Rendering ─────────────────────────────────────────────────────────

    def _render_shortfall_table(self, table_data: dict) -> str:
        """Render shortfall table as plain text, one block per skill."""
        OPERATING_HOURS = range(8, 20)

        blocks = []
        for skill_id, days in sorted(table_data.items()):
            all_hours = sorted({h for day_data in days.values() for h in day_data if h in OPERATING_HOURS})
            col_w = 8

            hour_headers = "".join(f"{h:02d}:00".rjust(col_w) for h in all_hours)
            header = f"  {'':10}{hour_headers}"
            sep = "  " + "-" * (10 + col_w * len(all_hours))

            day_rows = []
            col_totals_shortfall = {h: 0 for h in all_hours}
            col_totals_demand    = {h: 0 for h in all_hours}

            for day in range(7):
                if day not in days:
                    continue
                day_data = days[day]
                row = f"  {DAY_NAMES[day]:10}"
                for h in all_hours:
                    cell = day_data.get(h, {"shortfall": 0, "demand": 0})
                    sf = cell["shortfall"]
                    col_totals_shortfall[h] += sf
                    col_totals_demand[h]    += cell["demand"]
                    row += str(sf).rjust(col_w)
                day_rows.append(row)

            total_row_n = f"  {'Total (#)':10}" + "".join(
                str(col_totals_shortfall[h]).rjust(col_w) for h in all_hours
            )
            total_row_pct = f"  {'Total (%)':10}" + "".join(
                (
                    f"{round(100 * col_totals_shortfall[h] / col_totals_demand[h])}%"
                    if col_totals_demand[h] > 0 else "  -"
                ).rjust(col_w)
                for h in all_hours
            )

            block = "\n".join([
                f"{skill_id}",
                header,
                sep,
                *day_rows,
                sep,
                total_row_n,
                total_row_pct,
            ])
            blocks.append(block)

        return "\n\n".join(blocks)