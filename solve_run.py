from pydantic import BaseModel
from slot_matrix import SlotMatrix


class SolveRun(BaseModel):
    """The complete record of a single model run.

    Stores the full demand, supply, and shortfall matrices from the solver.
    KPI scalar fields (coverage_pct, total_agents, monthly_cost etc.)
    are deferred — to be added once the solver is fully wired.
    """

    run_id:    str
    label:     str
    demand:    SlotMatrix
    supply:    SlotMatrix
    shortfall: SlotMatrix
