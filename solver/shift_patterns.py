"""Hourly shift-shape geometry -- 4 core work-state families, 10 valid
(family, segment-extension) combos, tied together via add_allowed_assignments
instead of one flat 0-9 family int.

The underlying shift is still a 17-slot (30-min) pattern with a break, lunch,
and second break, each needing >=3 real work slots from the shift boundary
and from each other -- 10 raw (break1, lunch, break2) positions satisfy that.
Collapsing to hourly blocks only needs 4 distinct *work_state* shapes (it
never depends on exactly where the slack landed, only on whether each of the
four gaps has any at all) -- but two positions can share a work_state shape
while assigning one block to a different segment, so block_id still needs
the full 10-way resolution to stay correct (see the scheduler discussion:
(3,7,12) and (3,7,13) both read w4,w3,w4,w2,w4,w4,w3,w4,w4, but block 6
belongs to segment 4 in one and segment 3 in the other).

Rather than track that as one opaque 0-9 int, each real position is also
described by which of its 4 segments picked up extra length beyond the
3-slot minimum (there are only 2 "slack" slots total to distribute across
the 4 gaps, so at most 2 of the 4 seg*_extended bools are ever set). That
gives the solver 4 legible, independently-hintable bools instead of one
opaque family number. allowed_combos ties (family, 4 bools) to the resulting
combo_id via a single 10-row table constraint -- add_allowed_assignments
both blocks the 54 (of 4*16) bool combinations that aren't real positions,
and derives combo_id for free, since every listed row already pairs a unique
combo_id with its (family, bools). combo_id then drives block_id_array
exactly like the old flat family int did; shift_family_var (now just 0-3)
drives the now-4x-smaller work_state_array directly.

Every hour-block belongs to exactly one segment (never two) -- a block that
touches an event (break or lunch) only ever touches the ONE segment sitting
next to it, given the >=3-slot minimum gap. That's what keeps the 4-segment
skill-assignment scheme (one bool per segment, looked up by block_id) valid
at hourly resolution without any bespoke per-family logic.
"""
import polars as pl

EARLIEST_START_TIME_SLOT = 8  # hour-of-day, not a 30-min slot index
LATEST_START_TIME_SLOT = 11
SHIFT_LENGTH_SLOTS = 9  # 8 full hour-blocks + 1 half-hour tail block
MAX_START_OFFSET = LATEST_START_TIME_SLOT - EARLIEST_START_TIME_SLOT  # 3
PAD = MAX_START_OFFSET  # padding needed on EACH side of the real 9-block pattern
WORKDAY_LENGTH = PAD + SHIFT_LENGTH_SLOTS + PAD  # 15
NUM_BLOCKS = 4  # 4 skill-assignable segments -- unrelated to NUM_CORE_FAMILIES below

_RAW_SHIFT_LENGTH = 17  # the underlying 30-min-resolution shift length

# every valid (break1, lunch, break2) position: >=3 real work slots in each
# of the four gaps (start->b1, b1->l, l->b2, b2->end). 14 work slots split
# into 4 gaps of >=3 leaves 2 slack slots to distribute -- C(2+3, 3) = 10.
_VALID_POSITIONS = [
    (b1, l, b2)
    for b1 in range(_RAW_SHIFT_LENGTH)
    for l in range(_RAW_SHIFT_LENGTH)
    for b2 in range(_RAW_SHIFT_LENGTH)
    if (b1 > 2) and (l - b1 > 3) and (b2 - l > 3) and (_RAW_SHIFT_LENGTH - b2 > 3)
]

_SLOT_WEIGHT = {"work": 2, "break": 1, "lunch": 0}  # 30-min-slot contribution


def _real_pattern(b1, l, b2):
    """One (work_state, block_id) pair per real hour-block (9 of them).

    work_state sums each slot's own weight over the pair -- work=2, break=1
    (a break is only 15 min, so the agent's still half-present), lunch=0
    (the full 30 min). block_id is read off whichever slot in the pair is
    real "work" -- never assumed fixed for a given break, since whether a
    break pairs with the segment before or after it depends on b1/b2's
    parity.
    """
    def zone(idx):
        if idx == l:
            return ("lunch", None)
        if idx in (b1, b2):
            return ("break", None)
        if idx < b1:
            return ("work", 1)
        if idx < l:
            return ("work", 2)
        if idx < b2:
            return ("work", 3)
        return ("work", 4)

    zones = [zone(i) for i in range(_RAW_SHIFT_LENGTH)]
    blocks = []
    for i in range(0, _RAW_SHIFT_LENGTH, 2):
        pair = [zones[i]] if i == _RAW_SHIFT_LENGTH - 1 else [zones[i], zones[i + 1]]
        work_state = sum(_SLOT_WEIGHT[kind] for kind, _ in pair)
        segment_ids = {seg for kind, seg in pair if kind == "work"}
        assert len(segment_ids) == 1, f"block has zero or more than one segment: {pair}"
        blocks.append((work_state, segment_ids.pop()))
    return blocks


def _gaps(b1, l, b2):
    # the 4 segment lengths, each guaranteed >=3 by _VALID_POSITIONS.
    return (b1, l - b1 - 1, b2 - l - 1, (_RAW_SHIFT_LENGTH - 1) - b2)


# group the 10 valid positions by their work_state-only shape -- this is the
# 4-way split, since work_state never depends on exactly which segment
# absorbed the slack, only on whether each gap has any.
_by_work_state = {}
for _pos in _VALID_POSITIONS:
    _shape = tuple(ws for ws, _ in _real_pattern(*_pos))
    _by_work_state.setdefault(_shape, []).append(_pos)

NUM_CORE_FAMILIES = len(_by_work_state)  # 4
NUM_COMBOS = len(_VALID_POSITIONS)  # 10

# allowed_combos: (family_id, seg1_extended, seg2_extended, seg3_extended,
# seg4_extended, combo_id) -- one row per real position. seg*_extended
# marks whether that segment picked up any slack beyond its 3-slot minimum.
allowed_combos = []
_work_state_shapes = [None] * NUM_CORE_FAMILIES
_block_id_shapes = [None] * NUM_COMBOS
_combo_id = 0
for _family_id, (_shape, _positions) in enumerate(_by_work_state.items()):
    _work_state_shapes[_family_id] = _shape
    for _pos in _positions:
        _extra = tuple(g - 3 for g in _gaps(*_pos))
        _seg_extended = tuple(1 if e > 0 else 0 for e in _extra)
        allowed_combos.append((_family_id, *_seg_extended, _combo_id))
        _block_id_shapes[_combo_id] = tuple(bid for _, bid in _real_pattern(*_pos))
        _combo_id += 1


def _padded(values, pad_value):
    # pad both sides by PAD -- same padded pattern is correct for every
    # offset value, since the offset subtraction in flat_index re-centers
    # real work onto positions PAD..PAD+8 regardless of which offset a given
    # schedule actually picked.
    pad = [pad_value] * PAD
    return pad + list(values) + pad


# flat_index = shift_family_var * WORKDAY_LENGTH +
#              (hour_slot - shift_start_offset - EARLIEST_START_TIME_SLOT + PAD)
work_state_array = [v for shape in _work_state_shapes for v in _padded(shape, 0)]

# flat_index = combo_id_var * WORKDAY_LENGTH + (same slot/offset arithmetic)
block_id_array = [v for shape in _block_id_shapes for v in _padded(shape, 0)]


if __name__ == "__main__":
    pl.Config.set_ascii_tables(True)
    pl.Config.set_tbl_cols(-1)
    pl.Config.set_tbl_rows(-1)
    print(f"{NUM_CORE_FAMILIES} core families, {NUM_COMBOS} valid combos")
    print("allowed_combos (family, seg1_ext, seg2_ext, seg3_ext, seg4_ext, combo_id):")
    for row in allowed_combos:
        print(" ", row)
    print(f"\nwork_state_array: {len(work_state_array)} entries")
    print(f"block_id_array: {len(block_id_array)} entries")
