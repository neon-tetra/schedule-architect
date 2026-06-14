import math
from core.domain import QueueProfile
from core.slot_matrix import SlotMatrix


class ErlangC:
    """
    Erlang C queuing model for call centre staffing.
    All methods are stateless class methods.

    The Erlang C formula models an M/M/c queue:
        - Calls arrive randomly (Poisson process)
        - Service times are exponentially distributed
        - Callers wait indefinitely until answered

    Core notation used in wait_probability() matches the standard formula:
        a   = offered load in Erlangs (arrival_rate * aht_seconds)
        c   = number of agents
        rho = utilisation per agent (a/c), must be < 1 for a stable queue
    """

    @classmethod
    def wait_probability(cls, arrival_rate: float, aht_seconds: float, agents: int) -> float:
        """Probability that an arriving call has to wait (the Erlang C formula).

        Computed in log space to avoid overflow at high agent counts.
        Returns 1.0 for an unstable queue (utilisation >= 1).
        """
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
        """Fraction of calls answered within answer_within_seconds.

        Returns 1.0 when there are no arrivals.
        """
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
        """Minimum agents needed to meet the service level target for a single interval.

        Starts just above the offered load (minimum for queue stability)
        and increments until the target is reached.
        Returns 0 when there are no arrivals.
        """
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
    def requirements_curve(cls, env: QueueProfile) -> SlotMatrix:
        """Derive per-interval staffing requirements across a full week.

        Reads target_sl, answer_within_seconds, and shrinkage directly from
        the QueueProfile so each queue carries its own service level parameters.

        interval_weights must have one value per interval slot in the operating
        window — e.g. 24 values for an 8am–8pm window at 30-min intervals.

        Shrinkage inflates the Erlang minimum to account for non-productive time:
            scheduled = ceil(erlang_minimum / (1 - shrinkage))

        Returns a SlotMatrix keyed by (day, slot, skill_id) -> agents_required.
        """
        intervals_per_hour = 2  # 30-minute slots
        start_hour, end_hour = env.operating_hours
        slots_in_window = (end_hour - start_hour) * intervals_per_hour

        values: dict[tuple[int, int, str], int] = {}

        for day in range(7):
            for slot_index in range(slots_in_window):
                interval_calls = (
                    env.weekly_volume
                    * env.day_weights[day]
                    * env.interval_weights[slot_index]
                )
                arrival_rate = interval_calls / 1800.0  # calls per second

                erlang_minimum = cls.minimum_agents(
                    arrival_rate=arrival_rate,
                    aht_seconds=env.aht_seconds,
                    target_service_level=env.target_sl,
                    answer_within_seconds=env.answer_within_seconds,
                )

                scheduled = (
                    math.ceil(erlang_minimum / (1 - env.shrinkage))
                    if env.shrinkage > 0
                    else erlang_minimum
                )

                absolute_slot = (start_hour * intervals_per_hour) + slot_index
                values[(day, absolute_slot, env.skill_id)] = scheduled

        return SlotMatrix(label=f"demand_{env.skill_id}", values=values)
