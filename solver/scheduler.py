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

from solver.shift_patterns import (work_state_array, block_id_array, allowed_combos, NUM_BLOCKS,
                                    NUM_CORE_FAMILIES, NUM_COMBOS,
                                    EARLIEST_START_TIME_SLOT, MAX_START_OFFSET, PAD, WORKDAY_LENGTH)

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

        row = pl.concat([pl.read_csv(path), row], how="vertical_relaxed")
    row.write_csv(path)


def build_and_solve(roster: pl.DataFrame, queues: pl.DataFrame, intervals: pl.DataFrame) -> pl.DataFrame:
    model = cp_model.CpModel()
    problem = Problem(model)
    
    AGENT_UPPER_BOUND = 25
    SCALED_UB = 4 * AGENT_UPPER_BOUND  # 100

    problem.diagnostic_mode = False
    _t = _make_timer()

    slots_in_scope = list(range(EARLIEST_START_TIME_SLOT, EARLIEST_START_TIME_SLOT + WORKDAY_LENGTH - PAD))

    min_slot_30 = min(slots_in_scope) * 2
    max_slot_30 = max(slots_in_scope) * 2
    intervals = (intervals
            .select(["skill", "day", "slot", "demand"])
            .with_columns(demand=pl.col("demand") * 2)
            .filter((pl.col("slot") >= min_slot_30) & (pl.col("slot") <= max_slot_30))
            .with_columns(slot=pl.col("slot") // 2)
            .group_by(["skill", "day", "slot"])
            .agg(pl.col("demand").sum())
            .select(["skill", "day", "slot", "demand"]))
    _t("intervals filtered")


    # ==================== 1. schedules: one row per potential agent ====================

    from shift_patterns import DAY_PATTERNS
    day_patterns = DAY_PATTERNS
    
    num_shift_patterns = day_patterns.select("shift_pattern_id").unique().height
    num_break_patterns = day_patterns.select("break_pattern_id").unique().height
    num_shift_start_offsets = day_patterns.select("shift_start_offset_id").unique().height

    schedules = (roster
        .select("primary_skill", "secondary_skill", "count")
        .rename({"count": "skillgroup_agent_count"})
        .with_columns(schedule_template_count = 3)
        .with_columns(pl.int_ranges(0, pl.col("schedule_template_count")).alias("skillgroup_schedule_index"))
        .explode("skillgroup_schedule_index")
        .sort("primary_skill", "secondary_skill")
        .with_row_index(name="schedule_id")
        .select("primary_skill", "secondary_skill", "skillgroup_agent_count", "schedule_id")
        .pipe(problem.new_bool_var, "var_schedule_active")
        .pipe(problem.new_int_var, "var_schedule_agent_count", lb=0, ub=AGENT_UPPER_BOUND)
        .pipe(problem.new_int_var, "var_shift_pattern", lb=0, ub=num_shift_patterns - 1)
        .pipe(problem.new_int_var, "var_break_pattern", lb=0, ub=num_break_patterns - 1)
        .pipe(problem.new_int_var, "var_shift_start_offset", lb=0, ub=num_shift_start_offsets - 1)
        .select([
            "schedule_id",
            "primary_skill",
            "secondary_skill",
            "skillgroup_agent_count",
            "var_schedule_active",
            "var_schedule_agent_count",
            "var_shift_pattern",
            "var_break_pattern",
            "var_shift_start_offset"]))
    _t("schedules vars created")

    (schedules
        .with_columns(pl.col("schedule_active").shift(1).over(["primary_skill", "secondary_skill"])
                        .alias("schedule_active_prev"))
        .filter(pl.col("schedule_active_prev").is_not_null())
        .pipe(problem.add, lambda row: (row["schedule_active_prev"] >= row["schedule_active"],))) #lexicographic

    distinct_shift_patterns = (day_patterns
        .select(["shift_pattern_id", "break_pattern_id", "shift_start_offset_id"])
        .unique()
        .to_list())
    (schedules
        .pipe(problem.add_allowed_assignments, lambda row: (
            [row["var_shift_pattern"], row["var_break_pattern"], row["var_shift_start_offset"]],
            distinct_shift_patterns)))
    _t("schedules allowed assignments applied")





    (schedules
        .group_by(["primary_skill", "secondary_skill"])
        .agg(pl.col("var_schedule_agent_count").alias("list_agent_count"),
             pl.col("skillgroup_agent_count").first())
        .pipe(problem.add, lambda row: (sum(row["list_agent_count"]) == row["skillgroup_agent_count"],)))

    (schedules
        .pipe(problem.add_conditional, "add",
              lambda row: (row["var_schedule_agent_count"] == 0,),
              lambda row: row["var_schedule_active"].Not())
        .pipe(problem.add_conditional, "add",
              lambda row: (row["var_schedule_agent_count"] >= 1,),
              lambda row: row["var_schedule_active"]))
    _t("schedule-level constraints applied")

    schedules_x_days = (schedules
        .join(pl.DataFrame({"day": list(range(7))}), how="cross")
        .pipe(problem.new_bool_var, "var_schedule_day_active")
        .select([
            "schedule_id"           ,
            "day"                   ,
            "primary_skill"         ,
            "secondary_skill"       ,
            "skillgroup_agent_count",

            "var_schedule_active"         ,
            "var_schedule_day_active" ,
            "var_schedule_agent_count",
            "var_shift_pattern"       ,
            "var_break_pattern"       ,
            "var_shift_start_offset"
        ]))

    valid_workweek_patterns = [[1,1,1,1,1,0,0],
                               [0,1,1,1,1,1,0],
                               [0,0,1,1,1,1,1],
                               [1,0,0,1,1,1,1],
                               [1,1,0,0,1,1,1],
                               [1,1,1,0,0,1,1],
                               [1,1,1,1,0,0,1]]
    
    (schedules_x_days
        .group_by("schedule_id")
        .agg(pl.col("var_schedule_day_active").alias("list_schedule_day_active"))
        .pipe(problem.add_allowed_assignments, lambda row:
                                                     (row["list_schedule_day_active"],
                                                      valid_workweek_patterns)))
    _t("workweek patterns applied")

    schedule_day_slot = (schedules_x_days
        .join(pl.DataFrame({"slot": slots_in_scope}), how="cross")
        .pipe(problem.new_int_var, "var_raw_state", lb=0, ub=4)
        .pipe(problem.new_int_var, "var_block_id", lb=0, ub=NUM_BLOCKS)
        .pipe(problem.new_bool_var, "var_is_secondary")
        .select([
            "schedule_id"           ,
            "day"                   ,
            "slot"                  ,
            "primary_skill"         ,
            "secondary_skill"       ,
            "skillgroup_agent_count",

            "var_schedule_active"         ,
            "var_schedule_day_active" ,
            "var_schedule_agent_count",
            "var_shift_pattern"       ,
            "var_break_pattern"       ,
            "var_shift_start_offset"  ,
            "var_raw_state"           ,
            "var_block_id"            ,
            "var_is_secondary"
        ]))
    _t("schedule_day_slot vars created")

    (schedule_day_slot
        .pipe(problem.add_conditional, "add",
              lambda row: (row["var_raw_state"] == 0,),
              lambda row: row["var_schedule_day_active"].Not())

        .pipe(problem.add_conditional, "add_element",
              lambda row: ((row["var_shift_family"] * WORKDAY_LENGTH +
                           row["slot"] - row["var_shift_start_offset"] -
                           EARLIEST_START_TIME_SLOT + PAD),
                           work_state_array,
                           row["var_raw_state"],),
              lambda row: row["var_schedule_day_active"])

        .pipe(problem.add_conditional, "add_element",
              lambda row: ((row["var_combo_id"] * WORKDAY_LENGTH +
                           row["slot"] - row["var_shift_start_offset"] -
                           EARLIEST_START_TIME_SLOT + PAD),
                           block_id_array,
                           row["var_block_id"],),
              lambda row: row["var_schedule_day_active"])

        .pipe(problem.add_element, lambda row: (
              row["var_block_id"],
              [0, row["var_seg1_is_secondary"], row["var_seg2_is_secondary"],
               row["var_seg3_is_secondary"], row["var_seg4_is_secondary"]],
              row["var_is_secondary"],)))
    _t("schedule_day_slot constraints applied")

    intervals_x_schedules = (intervals.lazy()
        .join(schedules_x_days.lazy(), on="day")
        .filter((pl.col("skill") == pl.col("primary_skill")) | (pl.col("skill") == pl.col("secondary_skill")))
        .with_columns(pl.when(pl.col("skill") == pl.col("primary_skill"))
                        .then(0)
                        .otherwise(1).alias("skill_offset_flag"))
        .collect()
        .join(schedule_day_slot.select(["schedule_id", "day", "slot", "var_raw_state", "var_is_secondary"]),
              on=["schedule_id", "day", "slot"])
        .pipe(problem.new_int_var, "val_schedule_interval_contribution_raw", lb=0, ub=SCALED_UB)
        .pipe(problem.new_int_var, "val_schedule_interval_contribution_weighted", lb=0, ub=SCALED_UB)
        .select([
            "schedule_id"           ,
            "day"                   ,
            "slot"                  ,
            "skill"                 ,
            "demand"                ,
            "primary_skill"         ,
            "secondary_skill"       ,
            "skillgroup_agent_count",
            "skill_offset_flag"     ,

            "var_schedule_active"         ,
            "var_schedule_day_active" ,
            "var_schedule_agent_count",
            "var_shift_pattern"       ,
            "var_break_pattern"       ,
            "var_shift_start_offset"  ,
            "var_raw_state"           ,
            "var_is_secondary"        ,

            "val_schedule_interval_contribution_raw"     ,
            "val_schedule_interval_contribution_weighted"
        ]))
    _t("intervals_x_schedules built (join + vars)")

    (intervals_x_schedules

        .pipe(problem.add_conditional, "add",
              lambda row: (row["val_schedule_interval_contribution_raw"] == row["var_raw_state"],),
              lambda row: row["var_is_secondary"] if row["skill_offset_flag"] else row["var_is_secondary"].Not())
        .pipe(problem.add_conditional, "add",
              lambda row: (row["val_schedule_interval_contribution_raw"] == 0,),
              lambda row: row["var_is_secondary"].Not() if row["skill_offset_flag"] else row["var_is_secondary"])
        .pipe(problem.add_multiplication_equality,
              lambda row: (row["val_schedule_interval_contribution_weighted"],
                           row["val_schedule_interval_contribution_raw"],
                           row["var_schedule_agent_count"],)))
    _t("contribution constraints applied (skill-split add + multiplication)")

    intervals_supply = (intervals_x_schedules
        .group_by(["skill", "day", "slot", "demand"])
        .agg(pl.col("val_schedule_interval_contribution_weighted")
               .alias("list_schedule_interval_contribution"))
        .pipe(problem.new_int_var, "val_supply", lb=0, ub=SCALED_UB)  # 4 = max # of segments per schedule
        .pipe(problem.add, lambda row: (row["val_supply"] ==
                                    sum(row["list_schedule_interval_contribution"]),),)
        .pipe(problem.new_int_var, "val_shortfall", lb=0, ub=lambda row: row["demand"])
        .pipe(problem.add_max_equality, lambda row: (row["val_shortfall"],
                                                     row["demand"] - row["val_supply"],
                                                     0),)
        .select([
            "skill" ,
            "day"   ,
            "slot"  ,
            "demand",

            "val_supply"   ,
            "val_shortfall",

            "list_schedule_interval_contribution"
        ]))
    _t("supply/shortfall constraints applied")

    shortfall_vars = [problem.store.get(v) for v in intervals_supply["val_shortfall"]]
    problem.minimize(sum(shortfall_vars))

    import model_view
    frames = problem.to_frames()
    _t("frames captured (problem.to_frames)")
    model_view.to_tree_html(frames, "model_view.html")
    model_view.to_tree_json(frames, "model_view.json")
    _t("model_view built (html + json)")


    _t("PYTHON TOTAL before solver.solve()")
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 600.0
    solver.parameters.num_search_workers = 8
    solver.parameters.log_search_progress = True
    status = problem.solve(solver)
    print(f"Solver status: {solver.status_name(status)}")
    _log_benchmark("Whole roster initial benchmark", status, solver, frames)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):

        resolved_schedules = dfor_solved(schedules, problem, solver)
        resolved_supply = dfor_solved(intervals_supply, problem, solver)
        print(resolved_schedules)
        print(resolved_supply)
        resolved_schedules.write_csv("resolved_schedules.csv")

        resolved_supply.drop("list_schedule_interval_contribution").write_csv("resolved_supply.csv")
        result = resolved_supply
    else:
        # ---- unhappy path: infeasibility analysis ----
        # only produces anything if problem.diagnostic_mode was True before
        # the constraints were built above.
        problem.explain(solver)  # quick, non-minimal sufficient-assumption dump

        if problem.diagnostic_mode:
            import quickxplain

            def oracle_solver_factory():
                # quickxplain's first "sanity" probe re-solves ALL assumptions
                # (the whole original model) -- as hard as the infeasibility
                # proof above, observed ~10-42s run to run. Cap must clear
                # that or a slow-but-correct probe reads as "not infeasible".
                s = cp_model.CpSolver()
                s.parameters.cp_model_presolve = False
                s.parameters.num_search_workers = 1
                s.parameters.max_time_in_seconds = 90.0
                return s

            _t("explain() printed, starting quickxplain")
            core_solver, core_status = quickxplain.reduce_to_core(problem, model, oracle_solver_factory)
            print(f"QuickXplain core status: {core_solver.status_name(core_status)}")
            _t("quickxplain reduce_to_core complete")

            core_frames = problem.to_frames()
            model_view.to_tree_html(core_frames, "model_view.html")
            model_view.to_tree_json(core_frames, "model_view.json")
            _t("model_view rebuilt from minimal core")

        result = intervals_supply


    return result
