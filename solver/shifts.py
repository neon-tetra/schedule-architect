from pydantic import BaseModel, field_validator, model_validator

class ShiftVariant(BaseModel):
    slot_activity: list[int]
    slot_present: list[bool] | None = None

    @field_validator("slot_activity")
    @classmethod
    def validate_slots(cls, v):
        if len(v) != 48:
            raise ValueError("slot_activity must be a list of length 48")
        if any(s not in (0, 1, 2) for s in v):
            raise ValueError("slot_activity must only contain values 0, 1, or 2")
        return v

    @model_validator(mode="after")
    def set_slot_present(self):
        self.slot_present = [s > 0 for s in self.slot_activity]
        return self

    @property
    def variant_id(self) -> str:
        return "".join(str(s) for s in self.slot_activity)


def generate_variants(shift_starts: list[int], shift_duration_slots: int):
    """
    Generate all valid break/lunch combinations for each shift start.

    Offsets are in slots relative to shift start:
        First break  : shift_start + 3  to shift_start + 10
        Lunch        : shift_start + 6  to shift_start + 13
        Second break : shift_start + 9  to shift_start + 16

    Validity constraints:
        lunch  >= first_break + 3
        second >= lunch + 3
    """
    variants = []

    for shift_start in shift_starts:
        shift_start_slot = shift_start * 2  # hours -> slots

        for b1 in range(3, 11):
            for lunch in range(6, 14):
                for b2 in range(9, 17):

                    if lunch < b1 + 3:
                        continue
                    if b2 < lunch + 3:
                        continue

                    slots = [0] * 48
                    for s in range(shift_duration_slots):
                        slot_index = (shift_start_slot + s) % 48
                        slots[slot_index] = 2  # working
                    slots[(shift_start_slot + b1) % 48] = 1  # first break
                    slots[(shift_start_slot + lunch) % 48] = 0  # lunch
                    slots[(shift_start_slot + b2) % 48] = 1  # second break
                    variants.append(ShiftVariant(slot_activity=slots))

    return variants