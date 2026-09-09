
import polars as pl

EARLIEST_START_TIME_SLOT = 8
LATEST_START_TIME_SLOT = 11
SHIFT_LENGTH_SLOTS = 9  # 8 full hour-blocks + 1 half-hour tail block
#MAX_START_OFFSET = LATEST_START_TIME_SLOT - EARLIEST_START_TIME_SLOT  # 3

#distinct schedule elements -
#the break pattern
#the start time
#the work week
#the intra-day skill switching -- channel this.  calculate only the raw state, include zone as
#metadata, downstream logic will appply skill switching to relevant zones


_RAW_SHIFT_LENGTH = 17  # the underlying 30-min-resolution shift length

_VALID_BREAK_PATTERNS = [
    (b1, l, b2)
    for b1 in range(_RAW_SHIFT_LENGTH)
    for l in range(_RAW_SHIFT_LENGTH)
    for b2 in range(_RAW_SHIFT_LENGTH)
    if (b1 > 3) and (l - b1 > 3) and (b2 - l > 3) and (_RAW_SHIFT_LENGTH - b2 > 3)
]

break_patterns = (
    pl.DataFrame(_VALID_BREAK_PATTERNS, schema=["break1_slot", "lunch_slot", "break2_slot"], orient="row")
    .with_row_index("break_pattern_id"))

#shift_intervals dataframe
#shift_interval_id 0 to 16
shift_intervals = pl.DataFrame(
    {"shift_interval_id": list(range(_RAW_SHIFT_LENGTH))})

zone_patterns = (
    break_patterns
    .join(shift_intervals, how="cross")
    .with_columns(
        pl.when(pl.col("shift_interval_id") == pl.col("break1_slot")).then(pl.lit("break 1"))
        .when(pl.col("shift_interval_id") == pl.col("lunch_slot")).then(pl.lit("lunch"))
        .when(pl.col("shift_interval_id") == pl.col("break2_slot")).then(pl.lit("break 2"))
        .otherwise(
            pl.when(pl.col("shift_interval_id") < pl.col("break1_slot")).then(pl.lit("zone 1"))
            .when(pl.col("shift_interval_id") < pl.col("lunch_slot")).then(pl.lit("zone 2"))
            .when(pl.col("shift_interval_id") < pl.col("break2_slot")).then(pl.lit("zone 3"))
            .otherwise(pl.lit("zone 4"))
        )
        .alias("zone")))

shift_start_intervals = pl.DataFrame(
    {"shift_start_interval": [16, 18, 20, 22], "shift_start_offset_id": [0, 1, 2, 3]})

shift_patterns = (
    break_patterns
    .join(shift_start_intervals, how="cross")
    .with_row_index("shift_pattern_id"))

local_zone_by_day_interval = (
    shift_patterns
    .join(zone_patterns.select(["break_pattern_id", "shift_interval_id", "zone"]), on="break_pattern_id")
    .with_columns((pl.col("shift_interval_id") + pl.col("shift_start_interval")).alias("day_interval_id"))
    .select(["shift_pattern_id", "day_interval_id", "zone"]))

day_intervals = pl.DataFrame(
    {"day_interval_id": list(range(48))})  # 48 half-hour slots in a day

DAY_PATTERNS = (
    shift_patterns
    .join(day_intervals, how="cross")
    .join(local_zone_by_day_interval, on=["shift_pattern_id", "day_interval_id"], how="left")
    .with_columns(pl.col("zone").fill_null("off"))
    .select(["shift_pattern_id", "break_pattern_id", "shift_start_offset_id", "day_interval_id", "zone",
             "break1_slot", "lunch_slot", "break2_slot"]))


if __name__ == "__main__":
    pl.Config.set_ascii_tables(True)
    pl.Config.set_tbl_cols(-1)
    pl.Config.set_tbl_rows(-1)
    print(f"break_patterns: {break_patterns.height} rows")
    print(f"shift_patterns (combinations): {shift_patterns.height} rows")
    print(f"day_patterns: {day_patterns.height} rows "
          f"(expect {break_patterns.height} x 4 x 48 = {break_patterns.height * 4 * 48})")
    print(day_patterns.filter(pl.col("shift_pattern_id") == 0))
