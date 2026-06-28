from core.domain import Roster, QueueProfile
from core.slot_matrix import SlotMatrix
from core.solve_run import SolveRun
from solver.var_registry import VarRegistry
from solver.shifts import generate_variants
from ortools.sat.python.cp_model import CpModel, CpSolver, OPTIMAL, FEASIBLE
from pydantic import BaseModel, model_validator


#schedule.days[i].slots[j] -> activity level 0,1,2
#schedule.uid = f"pattern{pattern_index}_variant{variant_index}"
class ScheduleVariant(BaseModel):
    schedule_uid: str
    workweek_pattern: tuple[int, ...]
    shift_variant_id: str
    schedule: list[list[int]]  # [DAY][SLOT] -> activity level 0,1,2


class ModelBuilder:
    """Builds and solves a CP-SAT scheduling model from a completed ScenarioContext.

    MVP implementation is intentionally monolithic — all model construction,
    constraint generation, and solving happens inside build_and_solve().
    Internal structure is deferred until the engine layer above it is complete.
    """

    def build_and_solve(self, roster: Roster, queues: dict[str, QueueProfile], demand: SlotMatrix) -> SolveRun:
        """Read context, build CP-SAT model, solve, return result."""

        DEBUG = True

        if DEBUG:
            print("Entered build_and_solve", flush=True)

        AGENT_UPPER_BOUND    = 20
        VALID_SHIFT_STARTS   = [8, 9, 10, 11]
        SHIFT_DURATION_SLOTS = 17
        DAYS                 = range(0, 7)
        SLOTS                = range(0, 48)
        VALID_WORK_WEEK_PATTERNS = [
            (2,3,4,5,6), (3,4,5,6,0), (4,5,6,0,1),
            (5,6,0,1,2), (6,0,1,2,3), (0,1,2,3,4), (1,2,3,4,5)
        ]
        SCALED_UB = AGENT_UPPER_BOUND * 2
        shift_variants = generate_variants(VALID_SHIFT_STARTS, SHIFT_DURATION_SLOTS, .2)
        #schedule_variants = (pattern, variant) -> [DAY][SLOT]        

        self._model = CpModel()

        schedule_variants = []
        schedule_variant_slots = []

        for pattern_index, pattern in enumerate(VALID_WORK_WEEK_PATTERNS): #note for later - construct as flat arrays so polars consumes it faster
            for variant_index, variant in enumerate(shift_variants):
                schedule_uid = f"pattern{pattern_index}_variant{variant_index}"
                schedule_variants.append({
                    "schedule_uid": schedule_uid,
                })

                schedule = []
                for day in DAYS:
                    if day in pattern:
                        schedule.append(list(variant.slot_activity))
                    else:
                        schedule.append([0] * 48)

                for day in DAYS:
                    for slot in SLOTS:
                        activity = schedule[day][slot]
                        schedule_variant_slots.append({
                            "schedule_uid": schedule_uid,
                            "day": day,
                            "slot": slot,
                            "activity": activity,
                        })
        import polars as pl

        df_schedule_variants = pl.DataFrame(schedule_variants)
        df_schedule_variant_slots = pl.DataFrame(schedule_variant_slots)

        #agents df
        agents = []
        id_counter = 0
        for entry in roster.entries:
            for i in range(entry.count):
                agents.append({
                    "agent_id": f"agent_{id_counter}",
                    "skill": entry.skills[0],
                })
                #if len(entry.skills) > 1:
                  #  agents.append({ # primary only for now
                  #      "agent_id": f"agent_{id_counter}",
                  #      "skill": entry.skills[1],
                   # })
                id_counter += 1
        
        df_agents = pl.DataFrame(agents)

        #demand df
        demand_rows = []
        for (day, slot, skill), dem in demand.values.items():
            demand_rows.append({
                "day": day,
                "slot": slot,
                "skill": skill,
                "demand": dem,
            })
        #just assuming all of this will work - all the relational/byref stuff
        #one 
        df_demand = pl.DataFrame(demand_rows)

        #hypothetical function:
        #def give_me_bools(num_bools: int) -> list[BoolVar]:
            #return [self._model.NewBoolVar(f"bool_{i}") for i in range(num_bools)]

        df_decision_agent_schedule = (df_agents
                                      .lazy()
                                      .join(df_schedule_variants.lazy(), how="cross")
                                      .unique(subset=["agent_id", "schedule_uid"])
                                      .collect()
        )

        vars_ = [self._model.new_bool_var("") for row in df_decision_agent_schedule.iter_rows(named=True)]

        df_decision_agent_schedule = (df_decision_agent_schedule
                                      .with_columns(pl.Series("decision_agent_schedule", vars_))
        )
        
        df_decision_agent_schedule_grouped = (df_decision_agent_schedule
                                             .group_by("agent_id")
                                             .agg(pl.col("decision_agent_schedule"))
        )

        for row in df_decision_agent_schedule_grouped.iter_rows(named=True):
            self._model.add_at_most_one(row["decision_agent_schedule"])
        
        df_interval = (df_demand
                       .lazy()
                       .filter(pl.col("demand") > 0)
                       .collect()
        )
        supply_vars_    = [self._model.new_int_var(0, SCALED_UB, "") for row in df_interval.iter_rows(named=True)]
        shortfall_vars_ = [self._model.new_int_var(0, SCALED_UB, "") for row in df_interval.iter_rows(named=True)]

        df_interval = (df_interval
                       .with_columns(pl.Series("supply",    supply_vars_))
                       .with_columns(pl.Series("shortfall", shortfall_vars_))
        )

        df_ir_1 = (df_interval
                   .lazy()
                   .join(df_schedule_variant_slots.lazy(),  on=["day", "slot"],  how="left")
                   .join(df_decision_agent_schedule.lazy(), on=["schedule_uid", "skill"], how="left")
                   .filter(pl.col("activity") > 0)
                   .filter(pl.col("skill").is_in(["online_orders","account_services"]))
                   .collect()
        )

        df_ir_2 = (
            df_ir_1
            .with_columns(
                pl.map_batches(
                    ["decision_agent_schedule", "activity"],
                    lambda x: pl.Series([a * b for a, b in zip(x[0], x[1])], dtype=pl.Object),
                    return_dtype=pl.Object,
                ).alias("agent_slot_activity")
            )
            .group_by(["skill", "day", "slot"])
            .agg(
                pl.col("agent_slot_activity"),
                pl.col("supply").first(),
                pl.col("shortfall").first(),
                pl.col("demand").first(),
            )
        )



        print("Pause here")
        for row in df_ir_2.iter_rows(named=True):
            self._model.add(row["supply"] == sum(row["agent_slot_activity"]))
            self._model.add_max_equality(row["shortfall"], [row["demand"] - row["supply"], 0])

        #minimize over shortfall vars
        self._model.Minimize(sum(df_ir_2["shortfall"]))

        
        solver = CpSolver()
        solver.parameters.max_time_in_seconds = 120
        solver.parameters.num_search_workers = 8
        solver.parameters.log_search_progress = True
        solver.parameters.cp_model_presolve = True
        status = solver.Solve(self._model)
        print(f"Solver status: {solver.StatusName(status)}")

        def resolve(col: str) -> pl.Expr:
            return pl.col(col).map_batches(
                lambda s: pl.Series([solver.value(v) for v in s], dtype=pl.Int64),
                return_dtype=pl.Int64,
            ).alias(col)

        if status in (OPTIMAL, FEASIBLE):
            # 1. demand/supply/shortfall per slot, as real numbers
            df_interval_resolved = df_interval.with_columns(
                resolve("supply"),
                resolve("shortfall"),
            )
            df_interval_resolved.write_csv("df_interval_resolved.csv")

            # 2. which agent/schedule pairs actually got selected
            df_agent_schedules_resolved = (
                df_decision_agent_schedule
                .with_columns(resolve("decision_agent_schedule"))
                .filter(pl.col("decision_agent_schedule") == 1)
            )
            df_agent_schedules_resolved.write_csv("df_agent_schedules.csv")

            # 3. per-agent, per-slot contribution detail
            df_ir_1_resolved = (
                df_ir_1
                .with_columns(resolve("decision_agent_schedule"))
                .with_columns((pl.col("decision_agent_schedule") * pl.col("activity")).alias("agent_slot_activity"))
                .filter(pl.col("decision_agent_schedule") == 1)
            )
            df_ir_1_resolved.write_csv("df_agent_slot_detail.csv")
        else:
            print(f"Skipping CSV export — solver status was {solver.StatusName(status)}, not OPTIMAL/FEASIBLE")
        


