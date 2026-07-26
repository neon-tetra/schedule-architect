from ortools.sat.python import cp_model
import polars as pl
import os
import time
from datetime import datetime
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

TIMING_ENABLED = True  # flip to False to silence every _t(...) call below without deleting them

def _make_timer():
    """Unobtrusive profiling aid -- call _t("label") after a section to print
    time since the last mark and since the start. Single-line calls, no
    wrapping/indenting of existing code; delete the calls (or just flip
    TIMING_ENABLED) whenever this stops being useful."""
    start = time.perf_counter()
    last = [start]
    def mark(label):
        if not TIMING_ENABLED:
            return
        now = time.perf_counter()
        print(f"[timer] {label}: {now - last[0]:.3f}s (total {now - start:.3f}s)")
        last[0] = now
    return mark


def _log_benchmark(label, status, solver, frames, path="benchmark_log.csv"):
    """One row per run, appended -- a plain CSV log for eyeballing/plotting
    progress over time, not a real experiment-tracking system. `label` is
    a free-text field for you to fill in by hand per run."""
    has_solution = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    row = pl.DataFrame([{
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "label": label,
        "status": solver.status_name(status),
        "objective": solver.objective_value if has_solution else None,
        "best_bound": solver.best_objective_bound if has_solution else None,
        "gap": (solver.objective_value - solver.best_objective_bound) if has_solution else None,
        "walltime_s": solver.wall_time,
        "num_variables": frames["variables"].height,
        "num_constraints": frames["constraints"].height,
    }])
    if os.path.exists(path):
        # vertical_relaxed tolerates minor dtype drift across appends (e.g.
        # an all-null objective column from an earlier infeasible run) --
        # a plain concat would otherwise break on the first schema mismatch.
        row = pl.concat([pl.read_csv(path), row], how="vertical_relaxed")
    row.write_csv(path)


def build_and_solve(roster: pl.DataFrame, queues: pl.DataFrame, intervals: pl.DataFrame) -> pl.DataFrame:
    model = cp_model.CpModel()
    problem = Problem(model)
    SCALED_UB = 50
    AGENT_UPPER_BOUND = 25  # generous per-template cap; the per-skillgroup sum constraint enforces the real total
    PATTERN_HALF_LEN = len(flattened_pattern_values) // 2  # skill_view is the outermost/most-significant dimension

    problem.diagnostic_mode = False
    _t = _make_timer()

    intervals = (intervals
            .select(["skill", "day", "slot", "demand"])
            # 16..38 inclusive is the true window: latest start (22) + shift
            # length (17) - 1 = 38 is the last slot any schedule could ever
            # occupy. 39 was never a real slot -- including it both wasted a
            # row and, worse, could compute an index one past the end of the
            # (now-sliced) pattern array for the highest family/derivation
            # combination at the earliest offset.
            .filter((pl.col("slot") >= 16) & (pl.col("slot") <= 38)))
    _t("intervals filtered")


    # ==================== 1. schedules: one row per potential agent ====================
    shift_start_domain = cp_model.Domain.FromValues([0, 2, 4, 6])
    schedules = (roster
        .select("primary_skill", "secondary_skill", "count")
        .rename({"count": "skillgroup_agent_count"})
        .with_columns(schedule_template_count = 2)
        .with_columns(pl.int_ranges(0, pl.col("schedule_template_count")).alias("skillgroup_schedule_index"))
        .explode("skillgroup_schedule_index")
        .sort("primary_skill", "secondary_skill")
        .with_row_index(name="schedule_id")
        .select("primary_skill", "secondary_skill", "skillgroup_agent_count", "schedule_id")
        .pipe(problem.new_bool_var, "schedule_active")
        .pipe(problem.new_int_var, "schedule_agent_count_var", lb=0, ub=AGENT_UPPER_BOUND)
        .pipe(problem.new_int_var, "shift_family_var", lb=0, ub=5)
        .pipe(problem.new_int_var, "shift_derivation_var", lb=0, ub=15)
        .pipe(problem.new_int_var_from_domain, "shift_start_offset_var", domain=shift_start_domain))
    _t("schedules vars created")


    # .over(...) scopes the shift to each skillgroup -- without it, the last
    # template of one skillgroup gets compared against the first template of
    # the next, which could wrongly force an unrelated skillgroup's template
    # inactive just because the previous skillgroup's last one was.
    (schedules
        .with_columns(pl.col("schedule_active").shift(1).over(["primary_skill", "secondary_skill"])
                        .alias("schedule_active_prev"))
        .filter(pl.col("schedule_active_prev").is_not_null())
        .pipe(problem.add, lambda row: (row["schedule_active_prev"] >= row["schedule_active"],)))

    # lexicographic ordering on the (family, derivation, offset) triple, same
    # skillgroup scoping as above -- otherwise interchangeable templates
    # within a skillgroup are free to permute which one picked which shape,
    # multiplying the search space for no reason. same radix-encoding trick
    # as the array index, built fresh here since the index formula treats
    # offset as a subtraction, not a digit: family is the most-significant
    # digit (base 16*7=112), derivation next (base 7, covering offset's raw
    # range 0-6), offset least significant.
    (schedules
        .with_columns(pl.col("shift_family_var").shift(1).over(["primary_skill", "secondary_skill"])
                        .alias("shift_family_var_prev"),
                      pl.col("shift_derivation_var").shift(1).over(["primary_skill", "secondary_skill"])
                        .alias("shift_derivation_var_prev"),
                      pl.col("shift_start_offset_var").shift(1).over(["primary_skill", "secondary_skill"])
                        .alias("shift_start_offset_var_prev"))
        .filter(pl.col("shift_family_var_prev").is_not_null())
        .pipe(problem.add, lambda row: (
            (row["shift_family_var_prev"] * 112 + row["shift_derivation_var_prev"] * 7 +
             row["shift_start_offset_var_prev"]) <=
            (row["shift_family_var"] * 112 + row["shift_derivation_var"] * 7 +
             row["shift_start_offset_var"]),)))

    # each template's agent count sums to its skillgroup's real headcount --
    # pooling made this necessary: skillgroup_agent_count is the group total,
    # not a per-template value, so something has to divide it back up.
    (schedules
        .group_by(["primary_skill", "secondary_skill"])
        .agg(pl.col("schedule_agent_count_var").alias("agent_count_list"),
             pl.col("skillgroup_agent_count").first())
        .pipe(problem.add, lambda row: (sum(row["agent_count_list"]) == row["skillgroup_agent_count"],)))

    # bidirectional: 0 agents means inactive, inactive means 0 agents.
    (schedules
        .pipe(problem.add_conditional, "add",
              lambda row: (row["schedule_agent_count_var"] == 0,),
              lambda row: row["schedule_active"].Not())
        .pipe(problem.add_conditional, "add",
              lambda row: (row["schedule_agent_count_var"] >= 1,),
              lambda row: row["schedule_active"]))
    _t("schedule-level constraints applied")

    schedules_x_days = (schedules
        .join(pl.DataFrame({"day": list(range(7))}), how="cross")
        .pipe(problem.new_bool_var, "schedule_day_active_var"))
    
    valid_workweek_patterns = [[1,1,1,1,1,0,0],
                               [0,1,1,1,1,1,0],
                               [0,0,1,1,1,1,1],
                               [1,0,0,1,1,1,1],
                               [1,1,0,0,1,1,1],
                               [1,1,1,0,0,1,1],
                               [1,1,1,1,0,0,1]]
    
    (schedules_x_days
        .group_by("schedule_id")
        .agg(pl.col("schedule_day_active_var").alias("schedule_day_active_list"))
        .pipe(problem.add_allowed_assignments, lambda row:
                                                     (row["schedule_day_active_list"],
                                                      valid_workweek_patterns)))
    _t("workweek patterns applied")

    intervals_x_schedules = (intervals.lazy()
        .join(schedules_x_days.lazy(), on="day")
        .filter((pl.col("skill") == pl.col("primary_skill")) | (pl.col("skill") == pl.col("secondary_skill")))
        .with_columns(pl.when(pl.col("skill") == pl.col("primary_skill"))
                        .then(0)
                        .otherwise(1).alias("skill_offset_flag"))        
        .collect()
        .pipe(problem.new_int_var, "schedule_interval_contribution_raw_val", lb=0, ub=SCALED_UB)
        .pipe(problem.new_int_var, "schedule_interval_contribution_weighted_val", lb=0, ub=SCALED_UB))
    _t("intervals_x_schedules built (join + vars)")
    (intervals_x_schedules
        .pipe(problem.add_conditional, "add", 
              lambda row: (row["schedule_interval_contribution_raw_val"] == 0,),
              lambda row: (row["schedule_day_active_var"].Not(),))

        #if skill = online_orders or account_services then = else 1

        .pipe(problem.add_conditional, "add_element",
                # add_element rebuilds its array argument into a fresh
                # constraint proto on every single call -- cost scales with
                # array length, regardless of it being the same Python list
                # object each time (measured: ~1.5ms/call at this array's
                # size vs ~0.004ms/call for a 3-entry array). skill_offset_flag
                # is already a plain constant per row (resolved in polars
                # before this lambda ever runs, not a CP-SAT variable), so we
                # already know which half of the array is relevant -- slice
                # to just that half instead of handing over the whole thing.
                # pattern_id = family*16 + derivation (skill_view no longer
                # part of the index -- it's which half we sliced instead),
                # flat_index = pattern_id*29 + (slot - offset - EARLIEST_START_TIME_SLOT + PAD).
                lambda row: (((row["shift_family_var"] * 16 +
                           row["shift_derivation_var"]) * 29 +
                           row["slot"] - row["shift_start_offset_var"] -
                           EARLIEST_START_TIME_SLOT + PAD),
                           flattened_pattern_values[row["skill_offset_flag"] * PATTERN_HALF_LEN:
                                                     (row["skill_offset_flag"] + 1) * PATTERN_HALF_LEN],
                           row["schedule_interval_contribution_raw_val"],),
                lambda row: row["schedule_day_active_var"])
        .pipe(problem.add_multiplication_equality,
              lambda row: (row["schedule_interval_contribution_weighted_val"],
                           row["schedule_interval_contribution_raw_val"],
                           row["schedule_agent_count_var"],)))
    _t("contribution constraints applied (add_conditional/add_element/multiplication)")

    intervals_supply = (intervals_x_schedules
        .group_by(["skill", "day", "slot", "demand"])
        .agg(pl.col("schedule_interval_contribution_weighted_val")
               .alias("schedule_interval_contribution_list"))
        .pipe(problem.new_int_var, "supply_val", lb=0, ub=SCALED_UB)
        .pipe(problem.add, lambda row: (row["supply_val"] == 
                                    sum(row["schedule_interval_contribution_list"]),),)
        .pipe(problem.new_int_var, "shortfall_val", lb=0, ub=SCALED_UB)
        .pipe(problem.add_max_equality, lambda row: (row["shortfall_val"],
                                                     row["demand"] - row["supply_val"],
                                                     0),))
    _t("supply/shortfall constraints applied")

    shortfall_vars = [problem.store.get(v) for v in intervals_supply["shortfall_val"]]
    problem.minimize(sum(shortfall_vars))

    import model_view
    frames = problem.to_frames()
    _t("frames captured (problem.to_frames)")
    model_view.to_tree_html(frames, "model_view.html")
    model_view.to_tree_json(frames, "model_view.json")
    _t("model_view built (html + json)")

    _t("PYTHON TOTAL before solver.solve()")
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60.0
    solver.parameters.num_search_workers = 4  # lighter load while iterating; raise for a real run
    solver.parameters.log_search_progress = True
    status = problem.solve(solver)
    print(f"Solver status: {solver.status_name(status)}")
    _log_benchmark("Whole roster initial benchmark", status, solver, frames)

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
