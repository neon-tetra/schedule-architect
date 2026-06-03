from __future__ import annotations

import plotly.graph_objects as go

from engine.retrieval import RetrievalResult


class ChartBuilder:
    """
    Builds Plotly figures from RetrievalResult data.

    Each method takes a RetrievalResult and returns a go.Figure.
    chart_type is a closed vocabulary — agents pick from supported_charts().

    Current implementation delegates to _legacy_build() which contains
    the original _build_chart_figure logic from AgentTools.
    This is marked for replacement — new chart methods should read
    directly from RetrievalResult.data rather than re-querying context.
    """

    SUPPORTED_CHARTS = [
        "shortfall_by_skill",
        "shortfall_pct_by_skill",
        "demand_vs_shortfall",
    ]

    def supported_charts(self) -> list[str]:
        """Return the list of supported chart types."""
        return self.SUPPORTED_CHARTS

    def build(self, chart_type: str, result: RetrievalResult) -> go.Figure:
        """
        Build and return a Plotly figure for the given chart_type.
        Raises ValueError if chart_type is not supported.

        TODO: Replace _legacy_build() with methods that read from
        RetrievalResult.data directly.
        """
        if chart_type not in self.SUPPORTED_CHARTS:
            raise ValueError(
                f"Unsupported chart_type '{chart_type}'. "
                f"Use one of: {', '.join(self.SUPPORTED_CHARTS)}."
            )
        # Stub — implementation to follow
        raise NotImplementedError(f"Chart type '{chart_type}' not yet implemented.")
