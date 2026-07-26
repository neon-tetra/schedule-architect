"""Shift-shape geometry, split into two small skill-independent arrays
instead of one big skill-aware one.

Earlier version baked (skill_view, family, derivation) all into one flat
array's index, giving 2 x 6 x 16 x 29 = 5,568 entries -- and since
add_element rebuilds its whole array argument into a fresh constraint proto
on every single call (cost scales with array length, not with how many
times the same Python list gets reused), that array size was directly
driving real Python-side and presolve-side cost.

The fix: work/break/lunch state and "which of the 4 segments is this
position part of" never actually depended on skill at all -- only *segment
identity* is geometric (family + position), while *which skill a segment
serves* is a separate, per-schedule choice (4 bools, not baked into this
menu). Splitting them means both arrays here only need family x slot:

    work_state_array: 6 families x 29 slots = 174 entries -- 0/1/2, same
        meaning as before (2 = full work slot, 1 = half a work slot on a
        break, 0 = lunch or off).
    block_id_array: same 174-entry shape -- which segment (1-4) this
        position belongs to, 0 for lunch/padding (breaks inherit their
        preceding work segment's id, same rule as before: R1 -> segment 1,
        R2 -> segment 3).

Both indexed identically:
    flat_index = shift_family_var * WORKDAY_LENGTH
               + (slot - shift_start_offset - EARLIEST_START_TIME_SLOT + PAD)

Which skill a slot counts toward is resolved separately, in scheduler.py,
via a second tiny (5-entry) add_element against the schedule's own 4
segment-skill bools, keyed by whichever segment block_id_array reports --
never a 16-way lookup, since segment identity and segment-skill-assignment
are independent questions once separated like this.
"""
import polars as pl

EARLIEST_START_TIME_SLOT = 16
LATEST_START_TIME_SLOT = 22
SHIFT_LENGTH_SLOTS = 17
MAX_START_OFFSET = LATEST_START_TIME_SLOT - EARLIEST_START_TIME_SLOT  # 6
PAD = MAX_START_OFFSET  # padding needed on EACH side of the real 17-slot pattern
WORKDAY_LENGTH = PAD + SHIFT_LENGTH_SLOTS + PAD  # 29
NUM_BLOCKS = 4  # breaks + lunch split a shift into this many continuous work segments

# each triple is (work slots before break 1, before lunch, before break 2).
# the work slots remaining after break 2 always come out to 3: every triple
# sums to 11, and 17 - 11 - 3 (the two breaks + the one lunch slot) = 3.
SHIFT_FAMILIES = [(3, 3, 5), (3, 5, 3), (5, 3, 3), (4, 4, 3), (4, 3, 4), (3, 4, 4)]

# label -> (work_state, block_id). a break always takes the block id of the
# work segment it immediately follows -- R1 locks to segment 1, R2 to
# segment 3 -- so there are only 4 independently-choosable segments, not 6.
_LABEL_TO_STATE_BLOCK = {
    "W1": (2, 1), "R1": (1, 1),
    "W2": (2, 2),
    "W3": (2, 3), "R2": (1, 3),
    "W4": (2, 4),
    "L": (0, 0),
    "X": (0, 0),
}


def _real_pattern(a, b, c):
    # the unpadded 17-slot shape -- position 0 is always this schedule's
    # own first work slot, wherever that actually falls in absolute time.
    pattern = []
    for counter in range(1, SHIFT_LENGTH_SLOTS + 1):
        if counter <= a:
            label = "W1"
        elif counter == a + 1:
            label = "R1"
        elif counter <= a + b + 1:
            label = "W2"
        elif counter == a + b + 2:
            label = "L"
        elif counter <= a + b + c + 2:
            label = "W3"
        elif counter == a + b + c + 3:
            label = "R2"
        else:
            label = "W4"
        pattern.append(label)
    return pattern


real_patterns = [_real_pattern(a, b, c) for a, b, c in SHIFT_FAMILIES]


def _padded_labels(real_pattern):
    # pad both sides by PAD -- the same padded pattern is correct for
    # every offset value, since the offset subtraction in flat_index
    # re-centers real work onto positions PAD..PAD+16 regardless of which
    # offset a given schedule actually picked.
    return ["X"] * PAD + real_pattern + ["X"] * PAD


family_rows = []
for family_id, real_pattern in enumerate(real_patterns):
    labels = _padded_labels(real_pattern)
    for local_slot, label in enumerate(labels):
        work_state, block_id = _LABEL_TO_STATE_BLOCK[label]
        family_rows.append({
            "shift_family_id": family_id,
            "local_slot": local_slot,
            "label": label,
            "work_state": work_state,
            "block_id": block_id,
        })

family_geometry = pl.DataFrame(family_rows)

# flat_index = shift_family_var * WORKDAY_LENGTH +
#              (slot - shift_start_offset - EARLIEST_START_TIME_SLOT + PAD)
work_state_array = family_geometry.sort(["shift_family_id", "local_slot"])["work_state"].to_list()
block_id_array = family_geometry.sort(["shift_family_id", "local_slot"])["block_id"].to_list()


if __name__ == "__main__":
    pl.Config.set_ascii_tables(True)
    pl.Config.set_tbl_cols(-1)
    print(family_geometry)
    print(f"\n{len(work_state_array)} entries each (work_state_array, block_id_array)")
