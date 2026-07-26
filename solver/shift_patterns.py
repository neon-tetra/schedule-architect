"""Shift-shape menu, as a single DataFrame: one row per (skill_view,
shift_family, per-segment skill assignment) combination -- 2 x 6 x 16 = 192
rows, each carrying its own flat pattern_id alongside the ids that produce
it, plus the resulting 29-slot numeric lookup pattern.

Generated from a small, code-derived spec (SHIFT_FAMILIES) rather than
hand-typed, so there's nothing to transcribe wrong the way a fully
enumerated table would risk.

pattern_id is a straight linear combination of three independent choices --
skill_view (0-1), family_id (0-5), derivation (0-15, the 4-bit segment
assignment):

    pattern_id = skill_view*96 + family_id*16 + derivation
    flat_index = pattern_id*29 + (slot - shift_start_offset - EARLIEST_START_TIME_SLOT + PAD)

shift_start_offset is a plain subtraction term here, not its own array
dimension (an earlier version multiplied the array by 7 to sidestep the
padding question -- this is smaller and turns out not to need that).
The reason a single shared, both-sides-padded pattern works for every
offset: real work sits at local positions PAD..PAD+16 for *any* offset,
because `slot - offset` cancels the fact that a later start shifts the
absolute slots by exactly the same amount. Only the padding needs to be
wide enough to cover queries that fall outside a given offset's own
working window in either direction -- PAD slots on each side (6, the max
offset) is exactly enough, verified against the actual min/max of
`slot - offset` across the full range.
"""
import itertools
import polars as pl

EARLIEST_START_TIME_SLOT = 16
LATEST_START_TIME_SLOT = 22
SHIFT_LENGTH_SLOTS = 17
MAX_START_OFFSET = LATEST_START_TIME_SLOT - EARLIEST_START_TIME_SLOT  # 6
PAD = MAX_START_OFFSET  # padding needed on EACH side of the real 17-slot pattern
WORKDAY_LENGTH = PAD + SHIFT_LENGTH_SLOTS + PAD  # 29

# each triple is (work slots before break 1, before lunch, before break 2).
# the work slots remaining after break 2 always come out to 3: every triple
# sums to 11, and 17 - 11 - 3 (the two breaks + the one lunch slot) = 3.
SHIFT_FAMILIES = [(3, 3, 5), (3, 5, 3), (5, 3, 3), (4, 4, 3), (4, 3, 4), (3, 4, 4)]


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


def _to_numeric(labels, skill):
    # a work slot in this skill's own blocks contributes 2, a break in this
    # skill's own blocks contributes 1 (half a work slot -- you still work
    # 15 of the 30 minutes on break), everything else (the other skill's
    # blocks, lunch, padding) contributes 0.
    numeric = []
    for label in labels:
        if label.startswith("W") and label.endswith(skill):
            numeric.append(2)
        elif label.startswith("R") and label.endswith(skill):
            numeric.append(1)
        else:
            numeric.append(0)
    return numeric


rows = []
pattern_id = 0
# skill outermost, then family, then derivation -- one flat array laid out
# skill/family/derivation/slot, strides 96/16/1 (each further multiplied by
# 29 for the slot dimension). a schedule's real choices (family, the 4
# segment bits) drive both its primary-skill index and its secondary-skill
# index; they differ only by the skill_view term. shift_start_offset is
# handled at read time, not baked into the menu.
for skill_view, skill in enumerate(("A", "B")):
    for family_id, real_pattern in enumerate(real_patterns):
        # a break always takes the skill of the work block it immediately
        # follows -- R1 locks to W1's skill, R2 locks to W3's skill -- so
        # there are only 4 independently-choosable segments, not 6.
        for derivation, (w1_sec, w2_sec, w3_sec, w4_sec) in enumerate(
                itertools.product((0, 1), repeat=4)):
            bucket_skill = {
                "W1": "B" if w1_sec else "A", "R1": "B" if w1_sec else "A",
                "W2": "B" if w2_sec else "A",
                "W3": "B" if w3_sec else "A", "R2": "B" if w3_sec else "A",
                "W4": "B" if w4_sec else "A",
            }
            base_labels = [label + bucket_skill[label] if label in bucket_skill else label
                           for label in real_pattern]
            labels = _padded_labels(base_labels)
            rows.append({
                "pattern_id": pattern_id,
                "skill_view": skill_view,
                "shift_family_id": family_id,
                "derivation": derivation,
                "w1_secondary": w1_sec, "w2_secondary": w2_sec,
                "w3_secondary": w3_sec, "w4_secondary": w4_sec,
                "labels": labels,
                "numeric_pattern": _to_numeric(labels, skill),
            })
            pattern_id += 1

pattern_menu = pl.DataFrame(rows)
NUM_PATTERNS = len(pattern_menu)

# ready-to-use flat array for a single add_element call: index with
# pattern_id * WORKDAY_LENGTH + (slot - shift_start_offset - EARLIEST_START_TIME_SLOT + PAD),
# where pattern_id = skill_view*96 + shift_family_id*16 + derivation.
flattened_pattern_values = [v for pattern in pattern_menu["numeric_pattern"] for v in pattern]


if __name__ == "__main__":
    pl.Config.set_ascii_tables(True)
    pl.Config.set_tbl_cols(-1)
    print(pattern_menu.drop("labels"))
    print(f"\n{NUM_PATTERNS} total patterns, {len(flattened_pattern_values)} flattened values")
