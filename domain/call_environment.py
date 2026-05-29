from pydantic import BaseModel


class CallEnvironment(BaseModel):
    """Defines the call volume and distribution characteristics for a single skill."""

    skill_id: str
    weekly_volume: float
    aht_seconds: float
    aht_std_seconds: float
    operating_hours: tuple[int, int] = (8, 20)
    day_weights: list[float]       # 7 values, one per day of week
    interval_weights: list[float]  # one per interval within operating hours

    # Deferred
    # operating_days: list[int]