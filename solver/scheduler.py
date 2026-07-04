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

def build_and_solve(roster: pl.DataFrame, queues: pl.DataFrame, intervals: pl.DataFrame) -> pl.DataFrame:
    

    assert set(roster.schema.keys())    == ROSTER_SCHEMA.keys(),        "Roster DataFrame schema mismatch."
    assert set(queues.schema.keys())    == QUEUE_PROFILE_SCHEMA.keys(), "QueueProfile DataFrame schema mismatch."
    assert set(intervals.schema.keys()) == INTERVAL_SCHEMA.keys(),      "Interval DataFrame schema mismatch."

    AGENT_UPPER_BOUND    = 25
    SCALED_UB = AGENT_UPPER_BOUND * 2

    model = cp_model.CpModel()
    
    

    df_skills = (
        queues
        .select("skill_id")
        .rename({"skill_id": "skill"})
        .unique())

    df_skillgroup_assignments = (
        roster
        .select("primary_skill", "secondary_skill", "count")
        .rename({"count": "skillgroup_agent_count"})
        .with_columns(pl.concat_str([pl.col("primary_skill"), pl.col("secondary_skill")
                                     ],separator="|")
                        .alias("skillgroup"))
        .with_columns(pl.int_ranges(0, pl.col("skillgroup_agent_count"))
                        .alias("skillgroup_schedule_index"))
        .explode("skillgroup_schedule_index")
        #one row per skillgroup/schedule per count, to 
        #accomodate up to n different schedules for each skillgroup
        #-----------------------------------------------------------------------------------                               
        .pipe(add_vars, model.new_int_var, lb=0, ub=AGENT_UPPER_BOUND, col_name="assigned_agents_var")
        .pipe(add_constraints, model.add, lambda row: [row["assigned_agents_var"] <= row["skillgroup_agent_count"]])                               
        .pipe(add_vars, model.new_int_var, lb=0, ub=6, col_name="workweek_pattern_id_var")
        .pipe(add_vars, model.new_int_var, lb=0, ub=3, col_name="start_time_slot_id_var")
        .pipe(add_vars, model.new_int_var, lb=0, ub=4, col_name="shift_pattern_id_var")
        .pipe(add_vars, model.new_int_var, lb=0, ub=139, col_name="schedule_selected_int")
        .select("skillgroup", "skillgroup_agent_count", "primary_skill", "secondary_skill", 
                "skillgroup_schedule_index", "assigned_agents_var", "workweek_pattern_id_var", 
                "start_time_slot_id_var", "shift_pattern_id_var", "schedule_selected_int"))
    
    (df_skillgroup_assignments
        .group_by(["skillgroup", "skillgroup_agent_count"])
        .agg(pl.col("assigned_agents_var").alias("assigned_agents_var_list"))
        .pipe(add_constraints, model.add, lambda row: [
            sum(row["assigned_agents_var_list"]) == row["skillgroup_agent_count"]]))


    df_schedule_activities = (_build_schedule_variants()
        .select("schedule_id", "day", "slot", "activity", "block_index",
                "workweek_pattern_id", "start_time_slot_id", "shift_pattern_id"))


    df_schedules = (
        df_schedule_activities
        .select("schedule_id", "workweek_pattern_id", "start_time_slot_id", "shift_pattern_id")
        .unique())
    

    df_schedule_id_allowed_assignments = (
        df_schedules
        .with_columns(pl.concat_list(["workweek_pattern_id", "start_time_slot_id", 
                                        "shift_pattern_id",  "schedule_id"])
                        .alias("allowed_assignment"))
        .select("allowed_assignment")
        .unique()
        .implode("allowed_assignment", "allowed_assignments_list")) #[[a,b,c,d]*n]                                                 
    allowed_assignments_list = df_schedule_id_allowed_assignments["allowed_assignments_list"][0]
    

    (df_skillgroup_assignments
        .pipe(add_constraints, model.AddAllowedAssignments, lambda row: [
        (row["workweek_pattern_id_var"], row["start_time_slot_id_var"],
         row["shift_pattern_id_var"],    row["schedule_selected_int"]), 
        (a for a in allowed_assignments_list)])) #first 3 vars now map to scheduleid
    

    df_schedule_skill_activities = (
        df_schedule_activities
        .select("schedule_id", "day", "slot", "activity", "block_index")
        .unique()
        .join(df_skills, how="cross")
        .pipe(add_vars, model.new_int_var, lb=0, ub=AGENT_UPPER_BOUND, col_name="agents_in_block_int"))
    

    df_skillgroup_index_schedule_active = (
        df_schedules
        .join(df_skillgroup_assignments, how="cross")
        .select("schedule_id", "skillgroup_schedule_index", "schedule_selected_int")
        .pipe(add_vars, model.new_bool_var, col_name="is_active")
        .pipe(add_constraints, model.add, lambda row: [
            row["is_active"] == (row["schedule_selected_int"] == row["schedule_id"])]))
    

    df_skillgroup_block_assignments = (
        df_skillgroup_assignments
        #if single skill, use primary_skill; if double skill, explode to both skills
        .with_columns(pl.when(pl.col("secondary_skill").is_null())
                        .then(pl.concat_list("primary_skill"))
                        .otherwise(pl.concat_list("primary_skill", "secondary_skill"))
                        .alias("skill"))
        .explode("skill")
        .with_columns(pl.int_ranges(0, 20).alias("block_index"))
        .explode("block_index")#one row per scheduleindex x skillcount x blockindex
                               #(scheduleindex = skillgroup x agent count)
        .pipe(add_vars, model.new_int_var, lb=0, ub=AGENT_UPPER_BOUND, col_name="block_value")
        .select("skillgroup", "skillgroup_agent_count", "skillgroup_schedule_index", 
                "assigned_agents_var", "skill", "block_index", "block_value"))
    
    #sum of block_values for each skillgroup/schedule = assigned_agents_var
    (df_skillgroup_block_assignments
        .group_by(["primary_skill", "secondary_skill", "skillgroup_schedule_index"])
        .agg(pl.col("block_value").alias("block_value_list"),
             pl.col("assigned_agents_var").first())
        .pipe(add_constraints, model.add, lambda row: [
            sum(row["block_value_list"]) == row["assigned_agents_var"]]))
                                       
    #df_schedule_skill_activities agents_in_block_int = sum
    #   of block values for all skillgrouproster entries
    #   with that skill and block index, gated on bool in df_skillgroup_index_schedule_active
    (df_schedule_skill_activities #schedule_id, day, slot, activity, block_index, skill, agents_in_block_int
     .join(df_skillgroup_block_assignments, #skillgroup_index, assigned_agents_var, block_value
           on=["skill", "block_index"], how="left") 
     .join(df_skillgroup_index_schedule_active, #is_active
           on=["schedule_id", "skillgroup_schedule_index"], how="left")
     .select("skillgroup", "skill", "day", "slot", "activity", 
             "skillgroup_schedule_index",  "schedule_id", "is_active", "assigned_agents_var",
             "block_index", "block_value", "agents_in_block_int")
     #agents_in_block_int is the sum of all block values at index, gated on is_active
     .pipe(add_vars, model.new_int_var, lb=0, ub=AGENT_UPPER_BOUND, col_name="block_value_contribution")
     .pipe(add_constraints, model.add, lambda row: [
         row["block_value_contribution"] == row["block_value"] * row["is_active"]])
     #go up a layer of aggregation to get the assigned agents
    
     
     return None


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
        #assign a unique block index across all schedule variants
        #index partitioned by schedule_id, day_index, within_day_block
        .with_columns(pl.col("within_day_block").rank("dense")
                                                .over(["schedule_id", "day_index"])
                                                .alias("block_index"))
        .collect()        
        .select("schedule_id", "day", "slot", "activity", "block_index", 
                "workweek_pattern_id", "start_time_slot_id", "shift_pattern_id")

    )

    return df_schedule_activities