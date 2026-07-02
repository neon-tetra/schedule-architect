import math
import polars as pl
from core.frames import QUEUE_PROFILE_SCHEMA, INTERVAL_SCHEMA

class ErlangC:

    @classmethod
    def wait_probability(cls, arrival_rate: float, aht_seconds: float, agents: int) -> float:

        if arrival_rate <= 0:
            return 0.0

        a = arrival_rate * aht_seconds   # offered load in Erlangs
        c = agents

        if a / c >= 1.0:
            return 1.0  # queue is unstable — every call will wait

        log_a = math.log(a)
        log_numerator = c * log_a - math.lgamma(c + 1) + math.log(c) - math.log(c - a)
        log_poisson_terms = [k * log_a - math.lgamma(k + 1) for k in range(c)]

        # Normalise in log space to avoid overflow
        max_log = max(log_poisson_terms + [log_numerator])
        poisson_sum = sum(math.exp(t - max_log) for t in log_poisson_terms)
        numerator = math.exp(log_numerator - max_log)

        return numerator / (poisson_sum + numerator)

    @classmethod
    def service_level(
        cls,
        arrival_rate: float,
        aht_seconds: float,
        agents: int,
        answer_within_seconds: float,
    ) -> float:

        if arrival_rate <= 0:
            return 1.0

        offered_load = arrival_rate * aht_seconds
        p_wait = cls.wait_probability(arrival_rate, aht_seconds, agents)
        service_rate = 1.0 / aht_seconds

        return 1.0 - p_wait * math.exp(
            -(agents - offered_load) * service_rate * answer_within_seconds
        )

    @classmethod
    def minimum_agents(
        cls,
        arrival_rate: float,
        aht_seconds: float,
        target_service_level: float,
        answer_within_seconds: float,
        max_agents: int = 500,
    ) -> int:

        if arrival_rate <= 0:
            return 0

        offered_load = arrival_rate * aht_seconds
        agents = max(1, math.ceil(offered_load) + 1)

        while agents <= max_agents:
            if cls.service_level(arrival_rate, aht_seconds, agents, answer_within_seconds) >= target_service_level:
                return agents
            agents += 1

        return max_agents

    @classmethod
    def requirements_curve(cls, env: dict) -> pl.DataFrame:
        TARGET_SL = 0.8
        SHRINKAGE = 0.2
        ANSWER_WITHIN_SECONDS = 20.0

        assert env.keys() == QUEUE_PROFILE_SCHEMA.keys(), "QueueProfile schema mismatch."

        intervals_per_hour = 2  # 30-minute slots
        start_hour, end_hour = env["operating_hours"]
        slots_in_window = (end_hour - start_hour) * intervals_per_hour
        
        rows = []

        for day in range(7):
            for slot_index in range(slots_in_window):
                interval_calls = (
                    env["weekly_volume"]
                    * env["day_weights"][day]
                    * env["interval_weights"][slot_index]
                )
                arrival_rate = interval_calls / 1800.0  # calls per second

                erlang_minimum = cls.minimum_agents(
                    arrival_rate          = arrival_rate,
                    aht_seconds           = env["aht_seconds"],
                    target_service_level  = TARGET_SL,
                    answer_within_seconds = ANSWER_WITHIN_SECONDS,
                )

                scheduled = (
                    math.ceil(erlang_minimum / (1 - SHRINKAGE))
                    if SHRINKAGE > 0
                    else erlang_minimum
                )

                absolute_slot = (start_hour * intervals_per_hour) + slot_index
                
                rows.append({
                    "day": day,
                    "slot": absolute_slot,
                    "skill": env["id"],
                    "demand": scheduled,
                })
                
        df_interval = pl.DataFrame(rows, schema=INTERVAL_SCHEMA)

        return df_interval
