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
            .agg(pl.col("demand").sum()))
    _t("intervals filtered")


    # ==================== 1. schedules: one row per potential agent ====================
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
        .pipe(problem.new_int_var, "schedule_agent_count_var", lb=0, ub=AGENT_UPPER_BOUND)
        .pipe(problem.new_int_var, "shift_family_var", lb=0, ub=NUM_CORE_FAMILIES - 1)

        .pipe(problem.new_bool_var, "seg1_extended_var")
        .pipe(problem.new_bool_var, "seg2_extended_var")
        .pipe(problem.new_bool_var, "seg3_extended_var")
        .pipe(problem.new_bool_var, "seg4_extended_var")
        .pipe(problem.new_int_var, "combo_id_var", lb=0, ub=NUM_COMBOS - 1)

        .pipe(problem.new_bool_var, "seg1_is_secondary_var")
        .pipe(problem.new_bool_var, "seg2_is_secondary_var")
        .pipe(problem.new_bool_var, "seg3_is_secondary_var")
        .pipe(problem.new_bool_var, "seg4_is_secondary_var")
        .pipe(problem.new_int_var, "shift_start_offset_var", lb=0, ub=MAX_START_OFFSET))
    _t("schedules vars created")


    (schedules
        .pipe(problem.add_allowed_assignments, lambda row: (
            [row["shift_family_var"], row["seg1_extended_var"], row["seg2_extended_var"],
             row["seg3_extended_var"], row["seg4_extended_var"], row["combo_id_var"]],
            allowed_combos,
        )))

    (schedules
        .with_columns(pl.col("schedule_active").shift(1).over(["primary_skill", "secondary_skill"])
                        .alias("schedule_active_prev"))
        .filter(pl.col("schedule_active_prev").is_not_null())
        .pipe(problem.add, lambda row: (row["schedule_active_prev"] >= row["schedule_active"],)))

    (schedules
        .with_columns(pl.col("combo_id_var").shift(1).over(["primary_skill", "secondary_skill"])
                        .alias("combo_id_var_prev"),
                      pl.col("seg1_is_secondary_var").shift(1).over(["primary_skill", "secondary_skill"])
                        .alias("seg1_is_secondary_var_prev"),
                      pl.col("seg2_is_secondary_var").shift(1).over(["primary_skill", "secondary_skill"])
                        .alias("seg2_is_secondary_var_prev"),
                      pl.col("seg3_is_secondary_var").shift(1).over(["primary_skill", "secondary_skill"])
                        .alias("seg3_is_secondary_var_prev"),
                      pl.col("seg4_is_secondary_var").shift(1).over(["primary_skill", "secondary_skill"])
                        .alias("seg4_is_secondary_var_prev"),
                      pl.col("shift_start_offset_var").shift(1).over(["primary_skill", "secondary_skill"])
                        .alias("shift_start_offset_var_prev"))
        .filter(pl.col("combo_id_var_prev").is_not_null())
        .pipe(problem.add, lambda row: (
            (row["combo_id_var_prev"] * 64 +
             (row["seg1_is_secondary_var_prev"] * 8 + row["seg2_is_secondary_var_prev"] * 4 +
              row["seg3_is_secondary_var_prev"] * 2 + row["seg4_is_secondary_var_prev"]) * 4 +
             row["shift_start_offset_var_prev"]) <=
            (row["combo_id_var"] * 64 +
             (row["seg1_is_secondary_var"] * 8 + row["seg2_is_secondary_var"] * 4 +
              row["seg3_is_secondary_var"] * 2 + row["seg4_is_secondary_var"]) * 4 +
             row["shift_start_offset_var"]),)))

    (schedules
        .filter(pl.col("secondary_skill").is_null() | (pl.col("secondary_skill") == ""))
        .pipe(problem.add, lambda row: (row["seg1_is_secondary_var"] == 0,))
        .pipe(problem.add, lambda row: (row["seg2_is_secondary_var"] == 0,))
        .pipe(problem.add, lambda row: (row["seg3_is_secondary_var"] == 0,))
        .pipe(problem.add, lambda row: (row["seg4_is_secondary_var"] == 0,)))


    (schedules
        .group_by(["primary_skill", "secondary_skill"])
        .agg(pl.col("schedule_agent_count_var").alias("agent_count_list"),
             pl.col("skillgroup_agent_count").first())
        .pipe(problem.add, lambda row: (sum(row["agent_count_list"]) == row["skillgroup_agent_count"],)))


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

    schedule_day_slot = (schedules_x_days
        .join(pl.DataFrame({"slot": slots_in_scope}), how="cross")
        .pipe(problem.new_int_var, "raw_state_var", lb=0, ub=4)
        .pipe(problem.new_int_var, "block_id_var", lb=0, ub=NUM_BLOCKS)
        .pipe(problem.new_bool_var, "is_secondary_var"))
    _t("schedule_day_slot vars created")

    (schedule_day_slot
        .pipe(problem.add_conditional, "add",
              lambda row: (row["raw_state_var"] == 0,),
              lambda row: row["schedule_day_active_var"].Not())

        .pipe(problem.add_conditional, "add_element",
              lambda row: ((row["shift_family_var"] * WORKDAY_LENGTH +
                           row["slot"] - row["shift_start_offset_var"] -
                           EARLIEST_START_TIME_SLOT + PAD),
                           work_state_array,
                           row["raw_state_var"],),
              lambda row: row["schedule_day_active_var"])

        .pipe(problem.add_conditional, "add_element",
              lambda row: ((row["combo_id_var"] * WORKDAY_LENGTH +
                           row["slot"] - row["shift_start_offset_var"] -
                           EARLIEST_START_TIME_SLOT + PAD),
                           block_id_array,
                           row["block_id_var"],),
              lambda row: row["schedule_day_active_var"])

        .pipe(problem.add_element, lambda row: (
              row["block_id_var"],
              [0, row["seg1_is_secondary_var"], row["seg2_is_secondary_var"],
               row["seg3_is_secondary_var"], row["seg4_is_secondary_var"]],
              row["is_secondary_var"],)))
    _t("schedule_day_slot constraints applied")

    intervals_x_schedules = (intervals.lazy()
        .join(schedules_x_days.lazy(), on="day")
        .filter((pl.col("skill") == pl.col("primary_skill")) | (pl.col("skill") == pl.col("secondary_skill")))
        .with_columns(pl.when(pl.col("skill") == pl.col("primary_skill"))
                        .then(0)
                        .otherwise(1).alias("skill_offset_flag"))
        .collect()
        .join(schedule_day_slot.select(["schedule_id", "day", "slot", "raw_state_var", "is_secondary_var"]),
              on=["schedule_id", "day", "slot"])
        .pipe(problem.new_int_var, "schedule_interval_contribution_raw_val", lb=0, ub=SCALED_UB)
        .pipe(problem.new_int_var, "schedule_interval_contribution_weighted_val", lb=0, ub=SCALED_UB))
    _t("intervals_x_schedules built (join + vars)")

    (intervals_x_schedules

        .pipe(problem.add_conditional, "add",
              lambda row: (row["schedule_interval_contribution_raw_val"] == row["raw_state_var"],),
              lambda row: row["is_secondary_var"] if row["skill_offset_flag"] else row["is_secondary_var"].Not())
        .pipe(problem.add_conditional, "add",
              lambda row: (row["schedule_interval_contribution_raw_val"] == 0,),
              lambda row: row["is_secondary_var"].Not() if row["skill_offset_flag"] else row["is_secondary_var"])
        .pipe(problem.add_multiplication_equality,
              lambda row: (row["schedule_interval_contribution_weighted_val"],
                           row["schedule_interval_contribution_raw_val"],
                           row["schedule_agent_count_var"],)))
    _t("contribution constraints applied (skill-split add + multiplication)")

    intervals_supply = (intervals_x_schedules
        .group_by(["skill", "day", "slot", "demand"])
        .agg(pl.col("schedule_interval_contribution_weighted_val")
               .alias("schedule_interval_contribution_list"))
        .pipe(problem.new_int_var, "supply_val", lb=0, ub=SCALED_UB)  # 4 = max # of segments per schedule
        .pipe(problem.add, lambda row: (row["supply_val"] == 
                                    sum(row["schedule_interval_contribution_list"]),),)
        .pipe(problem.new_int_var, "shortfall_val", lb=0, ub=lambda row: row["demand"])
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

        resolved_supply.drop("schedule_interval_contribution_list").write_csv("resolved_supply.csv")
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
