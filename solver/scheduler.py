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
        # vertical_relaxed tolerates minor dtype drift across appends (e.g.
        # an all-null objective column from an earlier infeasible run) --
        # a plain concat would otherwise break on the first schema mismatch.
        row = pl.concat([pl.read_csv(path), row], how="vertical_relaxed")
    row.write_csv(path)


def build_and_solve(roster: pl.DataFrame, queues: pl.DataFrame, intervals: pl.DataFrame) -> pl.DataFrame:
    model = cp_model.CpModel()
    problem = Problem(model)
    # raw_state_var now maxes at 4 (was 2 at 30-min resolution), so a single
    # fully-staffed contribution can reach 4 * AGENT_UPPER_BOUND -- bumped
    # from 50 to keep the same headroom multiple this had before rather than
    # silently clipping a legitimate high-demand interval.
    AGENT_UPPER_BOUND = 25  # generous per-template cap; the per-skillgroup sum constraint enforces the real total
    SCALED_UB = 4 * AGENT_UPPER_BOUND  # 100

    problem.diagnostic_mode = False
    _t = _make_timer()

    # slots_in_scope is in HOUR units now (8..19 inclusive by default) --
    # everything downstream (schedule_day_slot's cross join, the interval
    # aggregation below) shares this one derivation instead of each
    # recomputing their own window.
    slots_in_scope = list(range(EARLIEST_START_TIME_SLOT, EARLIEST_START_TIME_SLOT + WORKDAY_LENGTH - PAD))

    # raw interval data still arrives on the old 30-min grid -- condense
    # pairs of slots into hour blocks here rather than upstream, since
    # Erlang C itself is still computed at 30-min resolution (coarsening
    # arrival-rate curves before the erlang math would lose real accuracy).
    # min/max here in 30-min units bracket exactly the hour window above:
    # min_slot_30 = first hour's first half; max_slot_30 = last in-scope
    # hour's first half. That last hour's SECOND half (max_slot_30 + 1) is
    # deliberately excluded -- no (family, offset) combination ever reaches
    # it, since the latest-starting shift's own pattern ends exactly there
    # (the trailing half-hour tail block covered by max_slot_30 alone).
    # Including it would silently inflate that one hour's demand relative to
    # what any schedule could ever actually cover.
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
        # seg*_extended_var: does this segment carry any of the 2 "slack"
        # work-slots beyond its 3-slot minimum -- a geometric fact about
        # break/lunch placement, independent of skill. Paired with
        # shift_family_var via allowed_combos below, these 4 bools + family
        # uniquely determine combo_id, which is what actually drives
        # block_id_array (see the schedule_day_slot section). Legible,
        # individually-hintable bools instead of one opaque 0-9 int.
        .pipe(problem.new_bool_var, "seg1_extended_var")
        .pipe(problem.new_bool_var, "seg2_extended_var")
        .pipe(problem.new_bool_var, "seg3_extended_var")
        .pipe(problem.new_bool_var, "seg4_extended_var")
        .pipe(problem.new_int_var, "combo_id_var", lb=0, ub=NUM_COMBOS - 1)
        # replaces the old single 0-15 "derivation" int -- one bool per
        # segment (is this segment working the secondary skill), same
        # "only 4 independently-choosable segments" fact as before, just
        # kept as 4 separate bools instead of packed into one int, since the
        # skill-assignment lookup now only ever needs one segment's own bool
        # at a time (see the schedule_day_slot section below).
        .pipe(problem.new_bool_var, "seg1_is_secondary_var")
        .pipe(problem.new_bool_var, "seg2_is_secondary_var")
        .pipe(problem.new_bool_var, "seg3_is_secondary_var")
        .pipe(problem.new_bool_var, "seg4_is_secondary_var")
        .pipe(problem.new_int_var, "shift_start_offset_var", lb=0, ub=MAX_START_OFFSET))
    _t("schedules vars created")

    # ties (family, 4 extended bools) to combo_id -- a single 10-row table
    # constraint that both blocks the 54 (of 4*16) bool combinations that
    # aren't real positions, and derives combo_id for free, since every
    # listed row already pairs a unique combo_id with its (family, bools).
    (schedules
        .pipe(problem.add_allowed_assignments, lambda row: (
            [row["shift_family_var"], row["seg1_extended_var"], row["seg2_extended_var"],
             row["seg3_extended_var"], row["seg4_extended_var"], row["combo_id_var"]],
            allowed_combos,
        )))


    # .over(...) scopes the shift to each skillgroup -- without it, the last
    # template of one skillgroup gets compared against the first template of
    # the next, which could wrongly force an unrelated skillgroup's template
    # inactive just because the previous skillgroup's last one was.
    (schedules
        .with_columns(pl.col("schedule_active").shift(1).over(["primary_skill", "secondary_skill"])
                        .alias("schedule_active_prev"))
        .filter(pl.col("schedule_active_prev").is_not_null())
        .pipe(problem.add, lambda row: (row["schedule_active_prev"] >= row["schedule_active"],)))

    # lexicographic ordering on the (combo_id, 4 skill-segment bools, offset)
    # tuple, same skillgroup scoping as above -- otherwise interchangeable
    # templates within a skillgroup are free to permute which one picked
    # which shape, multiplying the search space for no reason. combo_id
    # alone stands in for (shift_family_var, seg*_extended_var) here --
    # allowed_combos already ties them together bijectively for the 10 real
    # positions, so ordering combo_id orders the underlying geometry too,
    # without needing to build a wider radix over the geometry bools
    # directly. Same radix-encoding trick as before for the rest: combo_id
    # is the most-significant digit (base 16*4=64), the 4-bit skill-segment
    # value next (base 4, covering offset's range 0-3), offset least
    # significant.
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

    # single-skill schedules have no secondary to switch to -- a segment
    # marked "is_secondary" there doesn't count toward anything at all
    # (intervals_x_schedules can never match skill == a null secondary), so
    # that work just vanishes from the objective with nothing pulling the
    # solver away from it. pin all 4 segment bools to 0 to remove that dead
    # degree of freedom rather than leave it as free, purposeless slack.
    (schedules
        .filter(pl.col("secondary_skill").is_null() | (pl.col("secondary_skill") == ""))
        .pipe(problem.add, lambda row: (row["seg1_is_secondary_var"] == 0,))
        .pipe(problem.add, lambda row: (row["seg2_is_secondary_var"] == 0,))
        .pipe(problem.add, lambda row: (row["seg3_is_secondary_var"] == 0,))
        .pipe(problem.add, lambda row: (row["seg4_is_secondary_var"] == 0,)))

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

    # ==================== schedule_day_slot: skill-independent geometry ====================
    # raw_state_var (0/1/2/3/4, work/break amount) and is_secondary_var
    # (which skill this slot's segment serves) never depend on which skill
    # an interval is asking about -- only on family/combo/offset/segment-
    # assignment, all schedule-level facts. Computing them here, once per
    # (schedule, day, slot), instead of once per (schedule, day, slot, skill)
    # halves the expensive lookups for every dual-skill schedule, on top of
    # work_state_array now only being 60 entries (4 core families), with
    # block_id_array's 150-entry lookup (10 real combos) unchanged from the
    # flat-family version -- see shift_patterns.py and allowed_combos above.
    # slots_in_scope (hour units) computed above, shared with the intervals
    # aggregation.
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
              # flat_index = family*WORKDAY_LENGTH + (slot - offset - EARLIEST_START_TIME_SLOT + PAD)
              # -- shift_family_var (0-3) against the 60-entry work_state_array;
              # combo_id_var drives the separate 150-entry block_id_array below.
              lambda row: ((row["shift_family_var"] * WORKDAY_LENGTH +
                           row["slot"] - row["shift_start_offset_var"] -
                           EARLIEST_START_TIME_SLOT + PAD),
                           work_state_array,
                           row["raw_state_var"],),
              lambda row: row["schedule_day_active_var"])
        .pipe(problem.add_conditional, "add_element",
              # combo_id_var, not shift_family_var -- block_id_array is keyed
              # by the full 10-combo resolution (see shift_patterns.py),
              # while shift_family_var only carries the 4-way work_state
              # shape above.
              lambda row: ((row["combo_id_var"] * WORKDAY_LENGTH +
                           row["slot"] - row["shift_start_offset_var"] -
                           EARLIEST_START_TIME_SLOT + PAD),
                           block_id_array,
                           row["block_id_var"],),
              lambda row: row["schedule_day_active_var"])
        # tiny 5-entry lookup: which of the 4 segments' own bool applies.
        # index 0 (lunch/padding, block_id_var's sentinel) reads a harmless
        # constant 0 -- doesn't matter what is_secondary_var ends up being
        # there, raw_state_var is already 0 for those positions.
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
        # this row's skill_offset_flag is already a known constant (0 =
        # primary, 1 = secondary) -- so "does this slot's segment serve MY
        # skill" is just is_secondary_var itself, or its negation, a literal
        # we already have. no new bool, no multiplication, both branches
        # plain linear equalities.
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
