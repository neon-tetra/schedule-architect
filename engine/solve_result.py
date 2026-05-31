from pydantic import BaseModel
from domain import SlotMatrix

class SolveResult(BaseModel): #status, solve_time_seconds, demand, supply, shortfall
    """Output of the solve process, representing the computed schedule and related info."""

    status: str
    solve_time_seconds: float
    demand: SlotMatrix
    supply: SlotMatrix
    shortfall: SlotMatrix

    # Deferred
    # schedule: Schedule