from engine.solve_result import SolveResult

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class LLMPresenter:

    def __init__(self, result: SolveResult) -> None:
        self._result = result

    def present(self) -> str:
        presentation = self.summary_header()
        presentation += "\n\n" + self.shortfall_table()
        return presentation

    def summary_header(self) -> str:
        total = self._result.shortfall.sum()
        status = self._result.status
        skills = None
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
        """Build a nested dict of shortfall and demand by skill, day, and hour.

        Returns:
            {
                skill_id: {
                    day: {
                        hour: {
                            "shortfall": int,
                            "demand": int,
                        }
                    }
                }
            }
        """
        
        shortfall_hourly = self._result.shortfall.collapse_to_hours(agg="sum")
        demand_hourly = self._result.demand.collapse_to_hours(agg="sum")

        # ── TO-BE-REVISITED ───────────────────────────────────────────────
        # Combining and aggregating across multiple SlotMatrices is done
        # manually here via parallel key lookups. This pattern will recur
        # across any multi-matrix analysis (coverage ratios, gap summaries etc).
        # Candidate for a zip_with() method or richer dunder support on
        # SlotMatrix once we have a clearer picture of the full range of needs.
        # ─────────────────────────────────────────────────────────────────

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

            # Collect all hours present for this skill
            all_hours = sorted({h for day_data in days.values() for h in day_data if h in OPERATING_HOURS})
            col_w = 8

            # Header row
            hour_headers = "".join(f"{h:02d}:00".rjust(col_w) for h in all_hours)
            header = f"  {'':10}{hour_headers}"

            # Separator
            sep = "  " + "-" * (10 + col_w * len(all_hours))

            # Day rows
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

            # Totals rows
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