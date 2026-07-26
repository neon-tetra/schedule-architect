from ortools.sat.python import cp_model
import polars as pl
pl.Config.set_ascii_tables(True)  # Windows console (cp1252) can't render polars' default Unicode table borders
#from core.frames import INTERVAL_SCHEMA, QUEUE_PROFILE_SCHEMA, ROSTER_SCHEMA


try:
    from problem import Problem       # dfor -- importable in place via the venv .pth file, see CLAUDE.md
    from report import solved as dfor_solved
except ImportError:

    import sys
    sys.path.insert(0, r"C:\neon_tetra\active\dfor")
    from problem import Problem
    from report import solved as dfor_solved

from solver.shift_patterns import flattened_pattern_values, EARLIEST_START_TIME_SLOT, PAD


def build_and_solve(roster: pl.DataFrame, queues: pl.DataFrame, intervals: pl.DataFrame) -> pl.DataFrame:
    model = cp_model.CpModel()
    problem = Problem(model)
    SCALED_UB = 50

    problem.diagnostic_mode = False

    intervals = (intervals
            .select(["skill", "day", "slot", "demand"])
            .filter((pl.col("slot") >= 16) & (pl.col("slot") <= 39)))


    # ==================== 1. schedules: one row per potential agent ====================
    shift_start_domain = cp_model.Domain.FromValues([0, 2, 4, 6])
    schedules = (roster
        .select("primary_skill", "secondary_skill", "count")
        .rename({"count": "skillgroup_agent_count"})
        .with_columns(schedule_template_count = 3)
        .with_columns(pl.int_ranges(0, pl.col("schedule_template_count")).alias("skillgroup_schedule_index"))
        .explode("skillgroup_schedule_index")
        .sort("primary_skill", "secondary_skill")
        .with_row_index(name="schedule_id")
        .select("primary_skill", "secondary_skill", "skillgroup_agent_count", "schedule_id")
        .pipe(problem.new_bool_var, "schedule_active")
        .pipe(problem.new_int_var, "shift_family_var", lb=0, ub=5)
        .pipe(problem.new_int_var, "shift_derivation_var", lb=0, ub=15)
        .pipe(problem.new_int_var_from_domain, "shift_start_offset_var", domain=shift_start_domain))


    (schedules
        .with_columns(pl.col("schedule_active").shift(1).alias("schedule_active_prev"))
        .filter(pl.col("schedule_active_prev").is_not_null())
        .pipe(problem.add, lambda row: (row["schedule_active_prev"] >= row["schedule_active"],)))
    
    schedules_x_days = (schedules
        .join(pl.DataFrame({"day": list(range(7))}), how="cross")
        .pipe(problem.new_bool_var, "schedule_day_active_var"))
    
    (schedules_x_days
        .group_by("schedule_id")
        .agg(pl.col("schedule_day_active_var").alias("active_day_active_list"))
        .pipe(problem.add, lambda row: (sum(row["active_day_active_list"]) == 5,))) #for now
    
    intervals_x_schedules = (intervals.lazy()
        .join(schedules_x_days.lazy(), on="day")
        .filter((pl.col("skill") == pl.col("primary_skill")) | (pl.col("skill") == pl.col("secondary_skill")))
        .collect()
        .pipe(problem.new_int_var, "schedule_interval_contribution_val", lb=0, ub=SCALED_UB))
    
    (intervals_x_schedules
        .pipe(problem.add_conditional, "add", 
              lambda row: (row["schedule_interval_contribution_val"] == 0,),
              lambda row: (row["schedule_day_active_var"].Not(),))
        #if skill = online_orders or account_services then = else 1
        .with_columns(pl.when(pl.col("skill") == pl.col("primary_skill"))
                        .then(0)
                        .otherwise(1).alias("skill_offset_flag"))
        .pipe(problem.add_conditional, "add_element",
                # pattern_id = skill*96 + family*16 + derivation,
                # flat_index = pattern_id*29 + (slot - offset - EARLIEST_START_TIME_SLOT + PAD).
                # offset is a plain subtraction now, not its own array
                # dimension -- one both-sides-padded 29-slot pattern per
                # (skill,family,derivation) is correct for every offset,
                # since `slot - offset` re-centers real work onto the same
                # local positions regardless of which offset was picked.
                lambda row: (((row["skill_offset_flag"] * 96 +
                           row["shift_family_var"] * 16 +
                           row["shift_derivation_var"]) * 29 +
                           row["slot"] - row["shift_start_offset_var"] -
                           EARLIEST_START_TIME_SLOT + PAD),
                           flattened_pattern_values,
                           row["schedule_interval_contribution_val"],),
                lambda row: row["schedule_day_active_var"]))

    intervals_supply = (intervals_x_schedules
        .group_by(["skill", "day", "slot", "demand"])
        .agg(pl.col("schedule_interval_contribution_val")
               .alias("schedule_interval_contribution_list"))
        .pipe(problem.new_int_var, "supply_val", lb=0, ub=SCALED_UB)
        .pipe(problem.add, 
              lambda row: (row["supply_val"] == 
                           sum(row["schedule_interval_contribution_list"]),),)
        .pipe(problem.new_int_var, "shortfall_val", lb=0, ub=SCALED_UB)
        .pipe(problem.add_max_equality, lambda row: (row["shortfall_val"], 
                                                    row["demand"] - row["supply_val"], 
                                                     0),))
    
    shortfall_vars = [problem.store.get(v) for v in intervals_supply["shortfall_val"]]
    problem.minimize(sum(shortfall_vars))
    
    import model_view
    frames = problem.to_frames()
    model_view.to_tree_html(frames, "model_view.html")
    model_view.to_tree_json(frames, "model_view.json")

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0
    solver.parameters.num_search_workers = 4  # lighter load while iterating; raise for a real run
    solver.parameters.log_search_progress = True
    status = problem.solve(solver)
    print(f"Solver status: {solver.status_name(status)}")

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        # ---- happy path: pull real values out of the var-holding frames ----
        # dfor_solved(df, problem, solver) is the conversion -- returns a
        # copy of df with every satvar column (currently var-id strings)
        # replaced by the solver's actual resolved integer values.
        resolved_schedules = dfor_solved(schedules, problem, solver)
        resolved_supply = dfor_solved(intervals_supply, problem, solver)
        print(resolved_schedules)
        print(resolved_supply)
        resolved_schedules.write_csv("resolved_schedules.csv")
        # CSV can't hold the nested per-contributor list -- that's debug
        # detail anyway, drop it for the export.
        resolved_supply.drop("schedule_interval_contribution_list").write_csv("resolved_supply.csv")
        result = resolved_supply
    else:
        # ---- unhappy path: infeasibility analysis ----
        # only produces anything if problem.diagnostic_mode was True before
        # the constraints were built above -- flip it and re-run to debug.
        problem.explain(solver)
        # TODO: quickxplain.minimize(...) + reduce_to_core(...) to shrink
        # this down to a genuinely minimal core, then build a report/tree
        # view off just that reduced sub-model instead of the full reified
        # one -- not wired up yet.
        result = intervals_supply


    return result
