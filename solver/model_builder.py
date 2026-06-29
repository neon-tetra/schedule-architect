from core.domain import Roster, QueueProfile
from core.slot_matrix import SlotMatrix
from solver.shifts import generate_variants
from ortools.sat.python.cp_model import CpModel, CpSolver, OPTIMAL, FEASIBLE
from ortools.sat.python import cp_model
import polars as pl
class ModelBuilder:

    def _add_vars(self, df: pl.DataFrame, fn, col_name: str, **kwargs) -> pl.DataFrame:
        kwargs.setdefault("name", "")
        vars_ = [fn(**kwargs) for _ in range(df.height)]
        return df.with_columns(pl.Series(col_name, vars_, dtype=pl.Object))
    
    def _add_constraints(self, df: pl.DataFrame, fn, args_builder) -> pl.DataFrame:
        for row in df.iter_rows(named=True):
            fn(*args_builder(row))
        return df

    def build_and_solve(self, roster: Roster, queues: dict[str, QueueProfile], demand: SlotMatrix):

        AGENT_UPPER_BOUND    = 20
        SCALED_UB = AGENT_UPPER_BOUND * 2

        self._model = CpModel()

        df_schedule_variant_slots = self._build_schedule_variants()
        df_schedule_variants = (df_schedule_variant_slots
                                .select("schedule_id")
                                .unique(pl.col("schedule_id"))
        )

        col_agent_ids = []
        col_agent_skills = []
        agent_id = 0
        for entry in roster.entries:
            for _ in range(entry.count):
                for skill in entry.skills:
                    col_agent_ids.append(agent_id)
                    col_agent_skills.append(skill)
                agent_id += 1

        df_agents = (
            pl.DataFrame({"agent_id": col_agent_ids, "skill": col_agent_skills})
            .filter(pl.col("skill").is_in(["online_orders", "account_services"]))  # 2 skills for now
        )

        #demand df
        df_demand = pl.DataFrame(
            [{"day": d, 
              "slot": s, 
              "skill": sk, 
              "demand": v} for (d, s, sk), v in demand.values.items()]
        )

        df_decision_agent_schedule = (df_agents
                                      .lazy()
                                      .join(df_schedule_variants.lazy(), how="cross")
                                      .unique(subset=["agent_id", "schedule_id"])
                                      .collect()
                                      .pipe(self._add_vars,
                                            col_name="decision_agent_schedule", 
                                            fn=self._model.new_bool_var
                                      )
        )

        (df_decision_agent_schedule
            .group_by(["agent_id"]).agg(pl.col("decision_agent_schedule"))
            .pipe(self._add_constraints, 
                fn=self._model.add_at_most_one, 
                args_builder=lambda row: [row["decision_agent_schedule"]],
            )
        )
        
        df_interval = (df_demand
                       .filter(pl.col("demand") > 0)
                       .pipe(self._add_vars, col_name="supply",    fn=self._model.new_int_var, lb=0, ub=SCALED_UB)
                       .pipe(self._add_vars, col_name="shortfall", fn=self._model.new_int_var, lb=0, ub=SCALED_UB)
        )

        df_interval_by_agent = (
            df_interval
            .lazy()
            .join(df_schedule_variant_slots.lazy(), on=["day", "slot"], how="left")
            .join(df_decision_agent_schedule.lazy(), on=["schedule_id", "skill"], how="left")
            .filter(pl.col("activity") > 0)
            .filter(pl.col("skill").is_in(["online_orders", "account_services"]))
            .collect()
            .group_by(["skill", "day", "slot"])
            .agg(pl.col("decision_agent_schedule"),
                 pl.col("activity"),
                 pl.col("supply").first(),
                 pl.col("shortfall").first(),
                 pl.col("demand").first(),
            )
            .pipe(self._add_constraints,
                  fn=self._model.add,
                  args_builder=lambda r: (
                      cp_model.LinearExpr.WeightedSum(r["decision_agent_schedule"],
                                                      [int(a) for a in r["activity"]],
                      ) - r["supply"] == 0,
                  ),
            )
            .pipe(self._add_constraints,
                  fn=self._model.add_max_equality,
                  args_builder=lambda r: (
                    r["shortfall"],
                    [int(r["demand"]) - r["supply"], 0],
                ),
            )
        )

        df_decision_agent_schedule = (
             df_decision_agent_schedule
            .group_by(["agent_id"])
            .agg(pl.col("schedule_id"), 
                   pl.col("decision_agent_schedule"), 
                   pl.col("skill").first()
            )
            .pipe(self._add_vars, 
                col_name="selected_schedule",
                    fn=self._model.new_int_var,
                    lb=0,
                    ub=df_schedule_variants.height-1,
            )            
           .pipe(self._add_constraints,
               fn=self._model.add,
                   args_builder=lambda r: (
                       r["selected_schedule"] == cp_model.LinearExpr.WeightedSum(
                           r["decision_agent_schedule"],
                           [s for s in r["schedule_id"]],
                       ),
                   )
           )
        )

        self._model.Minimize(sum(df_interval_by_agent["shortfall"]))
        
        solver = CpSolver()
        solver.parameters.max_time_in_seconds = 120
        solver.parameters.num_search_workers = 8
        solver.parameters.log_search_progress = True
        solver.parameters.cp_model_presolve = True
        status = solver.Solve(self._model)


    def _build_schedule_variants(self) -> pl.DataFrame:

        slots = pl.Series("slot", list(range(0, 48)))

        VALID_WORK_WEEK_PATTERNS = [
            (2,3,4,5,6), (3,4,5,6,0), (4,5,6,0,1),
            (5,6,0,1,2), (6,0,1,2,3), (0,1,2,3,4), (1,2,3,4,5)
        ]
        work_week_patterns = (pl.DataFrame({"day": VALID_WORK_WEEK_PATTERNS})
                            .with_row_index("id")
                            .explode("day")
        )

        ctx = pl.SQLContext(eager=True)
        ctx.register("slots", slots)
        ctx.register("work_week_patterns", work_week_patterns)

        sql = """
WITH shift_variants AS (
   SELECT  shift_start.slot      AS shift_start
        ,  first_break.slot      AS first_break
        ,        lunch.slot      AS lunch
        , second_break.slot      AS second_break
        ,  shift_start.slot + 17 AS shift_end
        , ROW_NUMBER() AS shift_id
      FROM slots AS shift_start
CROSS JOIN slots AS first_break
CROSS JOIN slots AS lunch
CROSS JOIN slots AS second_break
     WHERE  first_break.slot >= shift_start.slot + 3
       AND        lunch.slot >= first_break.slot + 3
       AND second_break.slot >=       lunch.slot + 3
       AND second_break.slot <= shift_start.slot + 14
       AND  shift_start.slot IN (16, 18, 20, 22)
),
schedule_variants AS (
    SELECT ROW_NUMBER() AS schedule_id
        , wwp.id AS work_week_id
        , wwp.day
        ,  sv.shift_id
        ,  sv.shift_start
        ,  sv.first_break
        ,  sv.lunch
        ,  sv.second_break
      FROM work_week_patterns AS wwp
CROSS JOIN shift_variants     AS sv
),
shift_slots AS (
    SELECT sv.shift_id 
         ,  s.slot
         , CASE WHEN s.slot = sv.first_break  THEN 1
                WHEN s.slot = sv.lunch        THEN 0
                WHEN s.slot = sv.second_break THEN 1
                WHEN s.slot BETWEEN sv.shift_start AND sv.shift_end THEN 2
                ELSE 0
            END AS activity
      FROM shift_variants AS sv
CROSS JOIN slots AS s
),
schedule_slots AS (
    SELECT  sv.schedule_id
        ,   sv.day
        ,  vss.slot
        ,  vss.activity
      FROM schedule_variants AS sv
INNER JOIN shift_slots       AS vss ON sv.shift_id = vss.shift_id
)
SELECT * FROM schedule_slots;
        """

        df = ctx.execute(sql)
        unique_schedule_ids = df.select("schedule_id").unique(pl.col("schedule_id"))
        sample_ids = unique_schedule_ids.sample(unique_schedule_ids.height*.05, seed=42)
        result = df.join(sample_ids, on="schedule_id", how="inner")
        return result