from ortools.sat.python import cp_model
import polars as pl
from core import solve_run
from core.frames import INTERVAL_SCHEMA, QUEUE_PROFILE_SCHEMA, ROSTER_SCHEMA
from core.solve_run import SolveRun

def add_vars(df: pl.DataFrame, fn, col_name: str, **kwargs) -> pl.DataFrame:
    kwargs.setdefault("name", "")
    vars_ = [fn(**kwargs) for _ in range(df.height)]
    return df.with_columns(pl.Series(col_name, vars_, dtype=pl.Object))

def add_constraints(df: pl.DataFrame, fn, args_builder) -> pl.DataFrame:
    for row in df.iter_rows(named=True):
        fn(*args_builder(row))
    return df
"""
Common constraint shapes (for args_builder reference):
  model.add(var == expr)                        → args: (BoundedLinearExpression,)
  model.add(var <= expr)                        → args: (BoundedLinearExpression,)
  model.add_max_equality(target, [v1, v2, ...]) → args: (IntVar, list[IntVar|BoolVar])
  model.add_min_equality(target, [v1, v2, ...]) → args: (IntVar, list[IntVar|BoolVar])
  model.add_at_most_one([b1, b2, ...])          → args: (list[BoolVar],)
  model.add_exactly_one([b1, b2, ...])          → args: (list[BoolVar],)
  model.add_abs_equality(target, var)           → args: (IntVar, IntVar)
  model.add_multiplication_equality(t, [a, b]) → args: (IntVar, list[IntVar])

  LinearExpr.WeightedSum([vars], [coeffs])      → NOT a constraint — returns a LinearExpr.
                                                   Use inside model.add(): 
                                                   model.add(var == LinearExpr.WeightedSum(...))
"""


def build_and_solve(roster: pl.DataFrame, queues: pl.DataFrame, intervals: pl.DataFrame) -> pl.DataFrame:
    

    assert set(roster.schema.keys())    == ROSTER_SCHEMA.keys(),        "Roster DataFrame schema mismatch."
    assert set(queues.schema.keys())    == QUEUE_PROFILE_SCHEMA.keys(), "QueueProfile DataFrame schema mismatch."
    assert set(intervals.schema.keys()) == INTERVAL_SCHEMA.keys(),      "Interval DataFrame schema mismatch."

    AGENT_UPPER_BOUND    = 25
    SCALED_UB = AGENT_UPPER_BOUND * 2

    model = cp_model.CpModel()

    df_schedule_activities = (_build_schedule_variants()
                                .select("schedule_id", "day", "slot", "activity", "block_index",
                                        "workweek_pattern_id", "start_time_slot_id", "shift_pattern_id"))

    df_schedules = (df_schedule_activities
                    .select("schedule_id", "workweek_pattern_id", "start_time_slot_id", "shift_pattern_id")
                    .unique()
    )
# model.add_decision_strategy( do this later
#     [workweek_vars],           # branch on workweek first
#     cp_model.CHOOSE_FIRST,
#     cp_model.SELECT_MIN_VALUE
# )
# model.add_decision_strategy(
#     [start_time_vars],         # then start time
#     cp_model.CHOOSE_FIRST,
#     cp_model.SELECT_MIN_VALUE
# )

    df_skillgroup_schedules = (roster
                               .select("primary_skill", "secondary_skill", "count")
                               .rename({"count": "skillgroup_agent_count"})
                               .with_columns(pl.int_ranges(0, pl.col("skillgroup_agent_count")).alias("_explode"))
                               .explode("_explode")
                               .rename({"_explode": "skillgroup_schedule_index"})
                               .join(df_schedules, how="cross")
                               #one row per skillgroup/schedule per count, to 
                               #accomodate up to n different schedules for each skillgroup
                               #-----------------------------------------------------------------------------------                               
                               .pipe(add_vars, model.new_int_var, lb=0, ub=AGENT_UPPER_BOUND, col_name="assigned_agents_var")
                               .pipe(add_constraints, model.add, lambda row: [row["assigned_agents_var"] <= row["skillgroup_agent_count"]])                               
                               .pipe(add_vars, model.new_int_var, lb=0, ub=6, col_name="workweek_pattern_id_var")
                               .pipe(add_vars, model.new_int_var, lb=0, ub=3, col_name="start_time_slot_id_var")
                               .pipe(add_vars, model.new_int_var, lb=0, ub=4, col_name="shift_pattern_id_var")
                               .pipe(add_vars, model.new_int_var, lb=0, ub=139, col_name="schedule_selected_int")
                               .pipe(add_constraints, model.add, lambda row: [row["schedule_selected_int"] == 
                                    row["workweek_pattern_id_var"] * 20 + 
                                    row["start_time_slot_id_var"] * 5 + 
                                    row["shift_pattern_id_var"],])
                               #combo of workweek/starttime/shift pattern computes schedule id
                               #----------------------------------------------------------------------------------- 
                               .select("primary_skill", "secondary_skill", "skillgroup_agent_count", "skillgroup_schedule_index",
                                       "assigned_agents_var", "workweek_pattern_id_var", "start_time_slot_id_var", 
                                       "shift_pattern_id_var", "schedule_selected_int", "schedule_id"))
    
    #serious formulation problems
    #cant be doing this cross join on schedules - we need to look up the schedule id based on pattern vars
    #then - somehow - map it so the blocks will correctly translate to the right slots
    #also need to ensure total assigned across all schedules = count for that skillgroup
    
    df_skillgroup_schedule_blocks = (df_skillgroup_schedules
                                        .with_columns(pl.when(pl.col("secondary_skill").is_null())
                                                        .then(1).otherwise(2).alias("skill_count"))
                                        .with_columns(pl.when(pl.col("skill_count") == 1)
                                                        .then(pl.concat_list("primary_skill"))
                                                        .otherwise(pl.concat_list("primary_skill", "secondary_skill"))
                                                        .alias("skill"))
                                        .explode("skill")
                                        .with_columns(pl.int_ranges(0, 20).alias("block_index"))
                                        .explode("block_index")
                                        .pipe(add_vars, model.new_int_var, lb=0, ub=AGENT_UPPER_BOUND, col_name="block_value")
                                        #for each skillgroup/skill/schedule, create a list of 20 'blocks' - 
                                            #each block ties to a working period (first shift start to first break = 0, last lunch end to last 
                                            #shift end = 19)
                                        #single skill skillgroups have 20 int blocks, each block = count
                                        #double skill skillgroups have 2 sets of 20 int blocks, where sum of each pair equals count
                                        .select("primary_skill", "secondary_skill", "skill", "schedule_id", "skillgroup_agent_count",
                                                "skillgroup_schedule_index", "assigned_agents_var", "workweek_pattern_id_var", 
                                                "start_time_slot_id_var", "shift_pattern_id_var", "schedule_selected_int", 
                                                "skill_count", "block_index", "block_value"))
    #single skill agents have 20 int blocks, each block = count
    (df_skillgroup_schedule_blocks
     .filter(pl.col("skill_count") == 1)
     .pipe(add_constraints, model.add, lambda row: [row["block_value"] == row["assigned_agents_var"]]))
    #double skill agents have 20 int blocks, where sum of each equals count
    (df_skillgroup_schedule_blocks
     .filter(pl.col("skill_count") == 2)
        .pipe(add_constraints, model.add, lambda row: [row["block_value"] <= row["assigned_agents_var"]])
        .group_by(["primary_skill", "secondary_skill", "schedule_id", "block_index"])
        .agg(pl.col("block_value").alias("block_value_list"),
             pl.col("assigned_agents_var").first().alias("assigned_agents_var"))
        .pipe(add_constraints, model.add, lambda row: [sum(row["block_value_list"]) == row["assigned_agents_var"]]))

    df_intervals = (intervals
                    .with_columns(pl.col("demand") * 2)  #multiply demand & productivity by 2, 
                    .filter(pl.col("demand") > 0)        #so break productivity can be 1 instead of 0.5
                    .select(pl.exclude("supply", "shortfall"))
                    .pipe(add_vars, model.new_int_var, lb=0, ub=SCALED_UB, col_name="supply")
                    .pipe(add_vars, model.new_int_var, lb=0, ub=SCALED_UB, col_name="shortfall")
                    .select("skill", "day", "slot", "demand", "supply", "shortfall"))

    #for each skill/day/slot, find all block vars for that skill where that slot is a working slot, sum them, and multiply by 2
    #for each skill/day/slot, find all block vars for that skill where that slot is a break slot, sum them, and multiply by 1
    #sum those two values to get supply for that skill/day/slot
    (df_skillgroup_schedule_blocks
        .join(df_schedule_activities, on=["schedule_id", "block_index"])
        .join(df_intervals, on=["skill", "day", "slot"])
        .filter(pl.col("activity") > 0) #only working or break slots contribute to supply
        .group_by(["skill", "day", "slot", "activity"])
        .agg(pl.col("block_value").alias("block_value_list"),
             pl.col("demand").first().alias("demand"),
             pl.col("supply").first().alias("supply"),
             pl.col("shortfall").first().alias("shortfall"),)
        .pipe(add_constraints, model.add, lambda row: [
            row["supply"] == (sum(row["block_value_list"]) * row["activity"])]) #multiply by 2 for working slots, 1 for break slots
        .pipe(add_constraints, model.add_max_equality, lambda row: [row["shortfall"], [row["demand"] - row["supply"], 0]]))
    
    #symmetry break- for each skillgroup in df_skillgroup_schedules,
    #cant use a skillgroup_schedule_index with a higher schedule_id if a lower schedule_id is not used
    (df_skillgroup_schedules
        .sort(["primary_skill", "secondary_skill", "skillgroup_schedule_index"])
        .with_columns(
            pl.col("assigned_agents_var").shift(1).over(["primary_skill", "secondary_skill"])
            .alias("prev_assigned_agents_var")
        )
        .filter(pl.col("prev_assigned_agents_var").is_not_null())
        .pipe(add_constraints, model.add, 
            lambda row: [row["assigned_agents_var"] <= row["prev_assigned_agents_var"]]))
    
    shortfall_sum = sum(df_intervals["shortfall"])
    model.Minimize(shortfall_sum)
    
    
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 120
    solver.parameters.num_search_workers = 8
    solver.parameters.log_search_progress = True
    solver.parameters.cp_model_presolve = True
    status = solver.Solve(model)

    df_interval_literals = df_intervals.select("day", "slot", "skill", "demand", "supply", "shortfall").with_columns(
        pl.Series("supply", [solver.Value(v) for v in df_intervals["supply"]], dtype=pl.Int64),
        pl.Series("shortfall", [solver.Value(v) for v in df_intervals["shortfall"]], dtype=pl.Int64)
    )

    df_skillgroup_schedule_block_literals = (
        df_skillgroup_schedule_blocks
        .with_columns(pl.Series("block_value", [solver.Value(v) for v in df_skillgroup_schedule_blocks["block_value"]], dtype=pl.Int64))
        .with_columns(pl.Series("assigned_agents", [solver.Value(v) for v in df_skillgroup_schedule_blocks["assigned_agents_var"]], dtype=pl.Int64))
        .with_columns(pl.Series("workweek_pattern_id", [solver.Value(v) for v in df_skillgroup_schedule_blocks["workweek_pattern_id_var"]], dtype=pl.Int64))
        .with_columns(pl.Series("start_time_slot_id", [solver.Value(v) for v in df_skillgroup_schedule_blocks["start_time_slot_id_var"]], dtype=pl.Int64))
        .with_columns(pl.Series("shift_pattern_id", [solver.Value(v) for v in df_skillgroup_schedule_blocks["shift_pattern_id_var"]], dtype=pl.Int64))
        .with_columns(pl.Series("schedule_selected_int", [solver.Value(v) for v in df_skillgroup_schedule_blocks["schedule_selected_int"]], dtype=pl.Int64))
        .select("primary_skill", "secondary_skill", "skillgroup_agent_count", "skillgroup_schedule_index", "skill", "schedule_id", "block_index", "block_value",
                "assigned_agents", "workweek_pattern_id", "start_time_slot_id", "shift_pattern_id", "schedule_selected_int")
    )

    df_block_literals = (
        df_skillgroup_schedule_blocks
        .with_columns(pl.Series("block_value", [solver.Value(v) for v in df_skillgroup_schedule_blocks["block_value"]], dtype=pl.Int64))
    )

    solve_run = SolveRun(intervals=df_interval_literals, roster=roster, run_id="x", label="x")
    print(f"Solver status: {solver.StatusName(status)}")

    #for now, everything to csv
    df_interval_literals.write_csv("intervals.csv")
    df_skillgroup_schedule_block_literals.write_csv("skillgroup_schedules.csv")
    df_block_literals.write_csv("blocks.csv")
    return solve_run


def _build_schedule_variants() -> pl.DataFrame:

    WORKWEEK_PATTERNS = [ #what days of the week are worked
        [2,3,4,5,6], [3,4,5,6,0], [4,5,6,0,1],
        [5,6,0,1,2], [6,0,1,2,3], [0,1,2,3,4], [1,2,3,4,5]
    ]

    SHIFT_PATTERNS = [ #what are the offsets from shift start for break1,lunch,break2
        [4,9,15], [5,10,16], [5,11,16], [3,7,14], [3,8,14]
    ]

    START_TIME_PATTERNS = [ #what slots are available as shift start times
        16, 18, 20, 22
    ]

    #create df crossproduct of patterns
    df_schedule_variants = (pl.DataFrame({"workweek_pattern": WORKWEEK_PATTERNS}
                               ).with_row_index("workweek_pattern_id")
                            .join(pl.DataFrame({"start_time_slot": START_TIME_PATTERNS}
                               ).with_row_index("start_time_slot_id"), how="cross")
                            .join(pl.DataFrame({"shift_pattern": SHIFT_PATTERNS}
                               ).with_row_index("shift_pattern_id"), how="cross")
                            .with_columns((pl.col("workweek_pattern_id") * 20 +
                                           pl.col("start_time_slot_id") * 5 + 
                                           pl.col("shift_pattern_id")).alias("schedule_id")) #calculated id
                            .select("schedule_id", "workweek_pattern", "start_time_slot", "shift_pattern", 
                                    "workweek_pattern_id", "start_time_slot_id", "shift_pattern_id"))

    df_slots = pl.DataFrame({"slot": list(range(0, 48))})
    #create one row per day/slot/activity/block,
    #where activity = 0 (off), 1 (break), 2 (work)
    #and the first block is the period between the first days shift start and the first break,
    #the second block is the period between the first break and lunch, etc.
    #should be 4 blocks per day x 5 workdays = 20 blocks per schedule variant
    df_schedule_activities = (df_schedule_variants.lazy()
        .with_columns(pl.col("shift_pattern").list.get(0).alias("first_break_offset"),
                      pl.col("shift_pattern").list.get(1).alias("lunch_offset"),
                      pl.col("shift_pattern").list.get(2).alias("second_break_offset"))                              
        .join(df_slots.lazy().rename({"slot": "slot"}), how="cross")
        .explode("workweek_pattern")
        .rename({"workweek_pattern": "day"})
        .select("schedule_id", "day", "slot", "start_time_slot", "first_break_offset", "lunch_offset", "second_break_offset",
                "workweek_pattern_id", "start_time_slot_id", "shift_pattern_id")
        .filter(pl.col("slot") >= pl.col("start_time_slot"),
                pl.col("slot") <= pl.col("start_time_slot") + 17)

        .with_columns(pl.when(pl.col("slot") == pl.col("start_time_slot") + pl.col("first_break_offset")).then(1)
                        .when(pl.col("slot") == pl.col("start_time_slot") + pl.col("lunch_offset")).then(0)
                        .when(pl.col("slot") == pl.col("start_time_slot") + pl.col("second_break_offset")).then(1)
                        .otherwise(2).alias("activity"))
        .with_columns(pl.col("day").rank("dense").over("schedule_id").alias("day_index"))
        .with_columns(pl.when(pl.col("slot") < pl.col("start_time_slot") + pl.col("first_break_offset"))
                        .then(0)
                        .when(pl.col("slot") < pl.col("start_time_slot") + pl.col("lunch_offset"))
                        .then(1)
                        .when(pl.col("slot") < pl.col("start_time_slot") + pl.col("second_break_offset"))
                        .then(2)
                        .otherwise(3)
                        .alias("within_day_block"))
        .with_columns(((pl.col("day_index") - 1) * 4 + pl.col("within_day_block")).alias("block_index"))
        .collect()        
        .select("schedule_id", "day", "slot", "activity", "block_index", 
                "workweek_pattern_id", "start_time_slot_id", "shift_pattern_id")

    )

    return df_schedule_activities