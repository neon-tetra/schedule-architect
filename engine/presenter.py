from engine.solve_result import SolveResult


class LLMPresenter:

    def __init__(self, result: SolveResult) -> None:
        self._result = result

    def present(self) -> str:
        presentation = self.summary_header()
        presentation += "\n\n" + self.shortfall_table()
        return presentation

    def summary_header(self) -> str:
        #raise NotImplementedError
        return "Summary Header"

    def shortfall_table(self) -> str:
        table_data = self._build_shortfall_table_data()
        return f"Shortfall Table:\n{table_data}"
        #raise NotImplementedError  # text rendering to follow

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
        # Collapse both matrices from 30-min slots to 1-hour buckets
        shortfall_hourly = self._result.shortfall.collapse_to_hours(agg="sum")
        demand_hourly = self._result.demand.collapse_to_hours(agg="max")

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