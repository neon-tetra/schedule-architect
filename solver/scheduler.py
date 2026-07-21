from ortools.sat.python import cp_model
import polars as pl
from core import solve_run
from core.frames import INTERVAL_SCHEMA, QUEUE_PROFILE_SCHEMA, ROSTER_SCHEMA
from core.solve_run import SolveRun

def make_name_from_cols(row, cols):
    if cols is None:
        return ""
    parts = [str(row[c]) if c in row else c for c in cols]
    return "_".join(parts)

def add_vars(df: pl.DataFrame, fn, col_name: str, var_name_cols: list[str] | None = None, **kwargs) -> pl.DataFrame:
    def make_var(row_idx, row):
        name = make_name_from_cols(row, var_name_cols)
        name = f"{name}_{row_idx}"
        return fn(name=name, **kwargs)
    
    vars_ = [make_var(i, row) for i, row in enumerate(df.iter_rows(named=True))]
    return df.with_columns(pl.Series(col_name, vars_, dtype=pl.Object))

def add_constraints(df: pl.DataFrame, fn, constraint_builder, cst_name: list[str] | None = None) -> pl.DataFrame:
    for row in df.iter_rows(named=True):
        name = make_name_from_cols(row, cst_name)
        fn(*constraint_builder(row)).with_name(name)
        
    return df

def add_conditional_constraints(df, model, fn, constraint_builder, condition_builder, cst_name_cols: list[str] | None = None) -> pl.DataFrame:
    for row in df.iter_rows(named=True):
        name = make_name_from_cols(row, cst_name_cols)
        
        condition_expr = condition_builder(row)
        condition_var = model.new_bool_var(f"condition_{name}")
        model.add(condition_expr).only_enforce_if(condition_var).with_name(f"condition_{name}")

        principal_expr = constraint_builder(row)
        fn(principal_expr).only_enforce_if(condition_var).with_name(f"constraint_{name}")
        
    return df

def add_reified_conditional_constraints(df, model, fn, constraint_builder, condition_builder, inverse_builder, cst_name_cols: list[str] | None = None) -> pl.DataFrame:
    add_conditional_constraints(df, model, fn, constraint_builder, condition_builder, cst_name_cols)
    add_conditional_constraints(df, model, fn, constraint_builder, inverse_builder, cst_name_cols)

    return df


    
def build_and_solve(roster: pl.DataFrame, queues: pl.DataFrame, intervals: pl.DataFrame) -> pl.DataFrame:

    assert set(roster.schema.keys())    == ROSTER_SCHEMA.keys(),        "Roster DataFrame schema mismatch."
    assert set(queues.schema.keys())    == QUEUE_PROFILE_SCHEMA.keys(), "QueueProfile DataFrame schema mismatch."
    assert set(intervals.schema.keys()) == INTERVAL_SCHEMA.keys(),      "Interval DataFrame schema mismatch."

    AGENT_UPPER_BOUND    = 25
    SCALED_UB = AGENT_UPPER_BOUND * 2

    EARLIEST_START_TIME_SLOT = 16
    LATEST_START_TIME_SLOT   = 22

    model = cp_model.CpModel()
    
    skillgroup_schedules = (
        roster
        .select("primary_skill", "secondary_skill", "count")   
        .rename({"count": "skillgroup_agent_count"})
        .with_columns(pl.int_ranges(0, pl.col("skillgroup_agent_count"))
                        .alias("skillgroup_schedule_index"))
        .explode("skillgroup_schedule_index")
        .select("primary_skill", "secondary_skill", "skillgroup_agent_count", "skillgroup_schedule_index")
        #concat skills, secondary as "None" is null
        .with_columns(pl.concat_str([pl.col("primary_skill"), 
                                     pl.when(pl.col("secondary_skill").is_null())
                                       .then(pl.lit("single_skill")).otherwise(pl.col("secondary_skill"))]
                         , separator="_")
                        .alias("var_name"))
        .pipe(add_vars, model.new_int_var, col_name="assigned_agents_var",
              lb=0, ub=AGENT_UPPER_BOUND, var_name_cols=["var_name", "assigned_agents"])
        .pipe(add_vars, model.new_int_var, col_name="start_slot_idx_var",
              lb=EARLIEST_START_TIME_SLOT, ub=LATEST_START_TIME_SLOT, var_name_cols=["var_name", "start_slot_idx_var"])
        .pipe(add_vars, model.new_int_var, col_name="break_1_offset_var", lb=3, ub=5,  var_name_cols=["var_name", "break_1_offset"])
        .pipe(add_vars, model.new_int_var, col_name="lunch_offset_var",   lb=3, ub=5,  var_name_cols=["var_name", "lunch_offset"])
        .pipe(add_vars, model.new_int_var, col_name="break_2_offset_var", lb=3, ub=5,  var_name_cols=["var_name", "break_2_offset"])
        .pipe(add_vars, model.new_int_var, col_name="break_1_val",        lb=0, ub=47, var_name_cols=["var_name", "break_1"])
        .pipe(add_vars, model.new_int_var, col_name="lunch_val",          lb=0, ub=47, var_name_cols=["var_name", "lunch"])
        .pipe(add_vars, model.new_int_var, col_name="break_2_val",        lb=0, ub=47, var_name_cols=["var_name", "break_2"])
        .pipe(add_vars, model.new_int_var, col_name="end_slot_idx_val",   lb=0, ub=47, var_name_cols=["var_name", "end_slot_idx"])
        .pipe(add_constraints, model.add, lambda row: [
            row["break_1_val"] == row["start_slot_idx_var"] + row["break_1_offset_var"]],
            cst_name=["For all skillgroup x scheduleindex, break_1_val is the sum of start_slot_idx_var and break_1_offset_var"])
        .pipe(add_constraints, model.add, lambda row: [
            row["lunch_val"] == row["break_1_val"] + row["lunch_offset_var"]],
            cst_name=["For all skillgroup x scheduleindex, lunch_val is the sum of break_1_val and lunch_offset_var"])
        .pipe(add_constraints, model.add, lambda row: [
            row["break_2_val"] == row["lunch_val"] + row["break_2_offset_var"]],
            cst_name=["For all skillgroup x scheduleindex, break_2_val is the sum of lunch_val and break_2_offset_var"])
        .pipe(add_constraints, model.add, lambda row: [
            row["end_slot_idx_val"] == row["start_slot_idx_var"] + 17],
            cst_name=["For all skillgroup x scheduleindex, end_slot_idx_val is the sum of start_slot_idx_var and 17"])
        .pipe(add_constraints, model.add, lambda row: [
            row["break_2_val"] <= row["end_slot_idx_val"] - 3],
            cst_name=["For all skillgroup x scheduleindex, break_2_val is less than or equal to end_slot_idx_val minus 3"])
        .select("primary_skill",       "secondary_skill",    "skillgroup_schedule_index", "skillgroup_agent_count", 
                "assigned_agents_var", "start_slot_idx_var", "break_1_offset_var",        "break_1_val",
                "lunch_offset_var",    "lunch_val",          "break_2_offset_var",        "break_2_val",    "end_slot_idx_val"))

    agent_states    = pl.DataFrame({"agent_state":    ["scheduled", "work", "break"]})

    agent_substates = pl.DataFrame({"agent_state"   : ["scheduled", "work",   "work",   "break",   "break"],
                                    "agent_substate": ["scheduled", "work_a", "work_b", "break_a", "break_b"]})

    skillgroup_schedule_agent_states = (
        skillgroup_schedules
        .join(agent_states, how="cross")
        .join(pl.DataFrame({"slot_idx": list(range(0, 48))}),  how="cross")
        .pipe(add_vars, model.new_bool_var, col_name="agent_state_active_val",
              var_name_cols=["primary_skill", "secondary_skill", 
                             "skillgroup_schedule_index", "agent_state", "slot_idx", 
                             "agent_state_active"]))
    model.new_interval_var_serie
    (skillgroup_schedule_agent_states
        .filter(pl.col("agent_state") == "scheduled")
        .pipe(add_conditional_constraints, model, model.add,
                constraint_builder = lambda row: (row["agent_state_active_val"] == 1),
                condition_builder  = lambda row: (row["slot_idx"] >= row["start_slot_idx_var"]),
                cst_name_cols = ["""For all skillgroup x scheduleindex x agentstate x slot, where agentstate = 'scheduled',
                                 if slot_idx scalar >= start_slot_idx_var , then agent_state_active_val = 1"""])
        .pipe(add_conditional_constraints, model, model.add,
                constraint_builder = lambda row: (row["agent_state_active_val"] == 1),
                condition_builder  = lambda row: (row["slot_idx"] <= row["end_slot_idx_val"]),
                cst_name_cols = ["""For all skillgroup x scheduleindex x agentstate x slot, where agentstate = 'scheduled',
                                 if slot_idx scalar <= end_slot_idx_val , then agent_state_active_val = 1"""])
        .pipe(add_conditional_constraints, model, model.add,
                constraint_builder = lambda row: (row["agent_state_active_val"] == 1),
                condition_builder  = lambda row: (row["slot_idx"] != row["lunch_val"]),
                cst_name_cols = ["""For all skillgroup x scheduleindex x agentstate x slot, where agentstate = 'scheduled',
                                 if slot_idx scalar != lunch_val , then agent_state_active_val = 1"""]))
        
    
    (skillgroup_schedule_agent_states
        .pivot(index   =["primary_skill", "secondary_skill", "skillgroup_schedule_index", "slot_idx"],
               values  ="agent_state_active_val",
               columns ="agent_state")
        .pipe(add_constraints, model.add, lambda row: [
            row["work"] == row["scheduled"] - row["break"]],
            cst_name=["""For all skillgroup x scheduleindex x slot, the agent_state_active_val 
                      for work is equal to the agent_state_active_val for scheduled minus the agent_state_active_val for break"""]))
    
    (skillgroup_schedule_agent_states
     .filter(pl.col("agent_state") == "break")
     .sort("slot_idx")
     .group_by(["primary_skill", "secondary_skill", "skillgroup_schedule_index"])
     .agg(pl.col("agent_state_active_val").alias("break_active_list"),
          pl.col("break_1_val").first(),
          pl.col("break_2_val").first())
      .pipe(add_constraints, model.add_element, lambda row: [row["break_1_val"], row["break_active_list"], 1],
            cst_name=["""For all skillgroup x scheduleindex where agent_state = 'break', the agent_state_active_val 
                      at slot index break_1_val is equal to 1"""])
      .pipe(add_constraints, model.add_element, lambda row: [row["break_2_val"], row["break_active_list"], 1],
            cst_name=["""For all skillgroup x scheduleindex where agent_state = 'break', the agent_state_active_val 
                      at slot index break_2_val is equal to 1"""]))
          

    skillgroup_schedule_agent_substates = (
        skillgroup_schedule_agent_states
        .join(agent_substates, on="agent_state", how="inner")
        .join(pl.DataFrame({"day": list(range(0, 7))}), how="cross")
        .pipe(add_vars, model.new_bool_var, col_name="agent_substate_active_val",
              var_name_cols=["primary_skill", "secondary_skill", "skillgroup_schedule_index", 
                             "agent_state", "agent_substate", "day", "slot_idx", "agent_substate_active"]))

    (skillgroup_schedule_agent_substates
        .group_by(["primary_skill", "secondary_skill", "skillgroup_schedule_index", 
                   "slot_idx", "agent_state"])
        .agg(pl.col("agent_substate_active_val").alias("substate_active_list"),
             pl.col("agent_state_active_val").first())
        .pipe(add_constraints, model.add, lambda row: [
            sum(row["substate_active_list"]) == row["agent_state_active_val"]],
            cst_name=["""For all skillgroup x scheduleindex x slot x agentstate, the sum of agent_substate_active_val
                      for all agent_substates is equal to the agent_state_active_val for that slot and agentstate"""]))
    
    (skillgroup_schedule_agent_substates
        .filter(pl.col("agent_state") != "scheduled")
        .sort("slot_idx")
        .pivot(index=["primary_skill", "secondary_skill", "skillgroup_schedule_index", "day", "slot_idx"],
                values="agent_substate_active_val",
                columns="agent_substate")
        .with_columns(pl.col("work_a").shift(1).alias("prior_work_a"),
                      pl.col("work_b").shift(1).alias("prior_work_b"),
                      pl.col("work_a").shift(-1).alias("next_work_a"),
                      pl.col("work_b").shift(-1).alias("next_work_b"),)
        .filter(pl.col("prior_work_a").is_not_null() & pl.col("next_work_a").is_not_null())
        .pipe(add_constraints, model.add_at_most_one, lambda row: [row["prior_work_a"], row["work_b"]],
              cst_name=["""For all skillgroup x scheduleindex x slot x agentstate, at most one of prior_work_a and work_b can be active"""])
        .pipe(add_constraints, model.add_at_most_one, lambda row: [row["prior_work_b"], row["work_a"]],
              cst_name=["""For all skillgroup x scheduleindex x slot x agentstate, at most one of prior_work_b and work_a can be active"""])
        #break_a only if prior_work_a or next_work_a is true
        .pipe(add_conditional_constraints, model, model.add_bool_or,
                constraint_builder = lambda row: [row["prior_work_a"], row["next_work_a"]],
                condition_builder = lambda row: (row["break_a"]==1),
                cst_name_cols = ["""For all skillgroup x scheduleindex x slot x agentstate, where agent_substate = 'break_a',
                                 if break_a is active, then at least one of prior_work_a or next_work_a must be active"""])
        .pipe(add_conditional_constraints, model, model.add_bool_or,
                constraint_builder = lambda row: [row["prior_work_b"], row["next_work_b"]],
                condition_builder = lambda row: (row["break_b"]==1),
                cst_name_cols = ["""For all skillgroup x scheduleindex x slot x agentstate, where agent_substate = 'break_b',
                                 if break_b is active, then at least one of prior_work_b or next_work_b must be active"""]))

    schedule_substate_skills = (
        skillgroup_schedule_agent_substates
        .select("primary_skill", "secondary_skill", "skillgroup_schedule_index", "agent_state", 
                "agent_substate", "day", "slot_idx", "agent_substate_active_val")
        .with_columns(pl.when(pl.col("agent_substate").is_in(["work_a", "break_a"]))
                        .then(pl.col("primary_skill"))
                        .otherwise(pl.col("secondary_skill"))
                        .alias("skill")))

    (schedule_substate_skills
        .filter(pl.col("skill").is_null())
        .group_by("skill")
        .agg(pl.col("agent_substate_active_val").alias("substate_active_list"))
        .pipe(add_constraints, model.add, lambda row: [
            sum(row["substate_active_list"]) == 0],
            cst_name=["""For all skillgroup x scheduleindex x slot x agentstate, if skill is null, 
                      then the sum of agent_substate_active_val for all agent_substates is equal to 0"""]))

    intervals = (intervals
        .select("skill", "day", "slot", "demand")
        .rename({"slot": "slot_idx"})
        .pipe(add_vars, model.new_int_var, col_name="supply_val", lb=0, ub=SCALED_UB,
              var_name_cols=["skill", "day", "slot_idx", "supply"])
        .pipe(add_vars, model.new_int_var, col_name="shortfall_val", lb=0, ub=SCALED_UB,
              var_name_cols=["skill", "day", "slot_idx", "shortfall"])
        .join(schedule_substate_skills, on=["skill", "day", "slot_idx"], how="left")
        .group_by(["skill", "day", "slot_idx", "agent_state"])
        .agg(pl.col("agent_substate_active_val").alias("substate_active_list"),
             pl.col("demand").first(),
             pl.col("supply_val").first(),
             pl.col("shortfall_val").first())
        .pivot(index=["skill", "day", "slot_idx", "demand", "supply_val", "shortfall_val"],
               values="substate_active_list",
               columns="agent_state")
        .pipe(add_constraints, model.add, lambda row: [
            row["supply_val"] == sum(row["work"]) * 2 + sum(row["break"])],
            cst_name=["""For all skill x day x slot, the supply_val is equal to the sum of work 
                      and break agent_substate_active_val multiplied by 2"""])
        .pipe(add_constraints, model.add_max_equality, lambda row: [
            row["shortfall_val"], [row["demand"] - row["supply_val"], 0]],
            cst_name=["""For all skill x day x slot, the shortfall_val is equal to the maximum of 
                      (demand - supply_val) and 0"""]))
    
    model.Minimize(sum(intervals["shortfall_val"]))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60.0
    solver.parameters.num_search_workers = 8
    solver.parameters.log_search_progress = True
    solver.parameters.cp_model_presolve = True
    status = solver.Solve(model)
    proto = model.Proto()
    
    print("Solver status:", solver.StatusName(status))

    proto_vars = []
    proto_constraints = []
    for i, var in enumerate(proto.variables):
        proto_vars.append({"var_index": i, "var_name": var.name, "lb": var.domain[0], "ub": var.domain[1]})
    
    for i, constraint in enumerate(proto.constraints):
        #multiple varying fields possible, capture all present
        if constraint.linear:
            linear_expr = constraint.linear
            linear_vars = [linear_expr.vars[j] for j in range(len(linear_expr.vars))]
            linear_coeffs = [linear_expr.coeffs[j] for j in range(len(linear_expr.coeffs))]
            linear_domains = [linear_expr.domain[j] for j in range(len(linear_expr.domain))]
            proto_constraints.append({"constraint_index": i, "constraint_name": constraint.name, 
                                      "linear_vars": linear_vars, "linear_coeffs": linear_coeffs,
                                      "linear_domains": linear_domains})
    #pure json dump
    import json
    with open("model_dump.json", "w") as f:
        json.dump({"variables": proto_vars, "constraints": proto_constraints}, f, indent=4)
    return None