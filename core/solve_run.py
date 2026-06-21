from pydantic import BaseModel, model_validator
from core.slot_matrix import SlotMatrix
from core.domain import Roster
import pandas as pd
from solver.var_registry import VarRegistry

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
    roster:    Roster
    df_interval: pd.DataFrame = None
    df_roster:   pd.DataFrame = None
    var_registry: VarRegistry = None #ugly but useful
    model_config = {"arbitrary_types_allowed": True}
    

    @model_validator(mode="after")
    def build_df_interval(self):
        rows = []
        for (d, sl, sk), dem in self.demand.values.items():
            rows.append({
                "day":      d,
                "slot":     sl,
                "skill":    sk,
                "demand":   dem,
                "supply":   self.supply.get(d, sl, sk),
                "shortfall": self.shortfall.get(d, sl, sk),
            })
        self.df_interval = pd.DataFrame(rows)
        #add helper cols for display day of week, and hour
        #monday = 0, sunday = 6
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        self.df_interval["day_of_week"] = self.df_interval["day"].apply(lambda x: days[x % 7])
        #hour = hour/2 rounded down
        self.df_interval["hour"] = (self.df_interval["slot"] // 2)
        return self
    
    @model_validator(mode="after")
    def build_df_roster(self):
        rows = []
        for entry in self.roster.entries:
            rows.append({
                "skills": ", ".join(entry.skills),
                "count": entry.count,
                "monthly_cost": entry.monthly_cost,
            })
        self.df_roster = pd.DataFrame(rows)
        return self