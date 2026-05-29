"""
Hardcoded default scenario configuration for MVP development and testing.

Two-skill scenario: Inbound English and Inbound Spanish.
Interval weights cover the operating window (8am–8pm) only, 24 x 30-min slots.
"""

# ── Skills ────────────────────────────────────────────────────────────────────

SKILL_EN_ID   = "inbound_en"
SKILL_EN_NAME = "Inbound English"

SKILL_ES_ID   = "inbound_es"
SKILL_ES_NAME = "Inbound Spanish"

# ── Call Environment: Inbound English ─────────────────────────────────────────

ENV_EN_WEEKLY_VOLUME    = 2000.0
ENV_EN_AHT_SECONDS      = 300.0
ENV_EN_AHT_STD_SECONDS  = 60.0
ENV_EN_OPERATING_HOURS  = (8, 20)
ENV_EN_DAY_WEIGHTS      = [0.22, 0.19, 0.18, 0.19, 0.22, 0.0, 0.0]  # Mon–Sun, sums to 1.0
ENV_EN_INTERVAL_WEIGHTS = [
    0.020833333, 0.020833333, 0.020833333, 0.020833333,  # 08:00 – 10:00
    0.041666667, 0.041666667, 0.041666667, 0.041666667,  # 10:00 – 12:00
    0.062500000, 0.062500000, 0.062500000, 0.062500000,  # 12:00 – 14:00
    0.031250000, 0.031250000, 0.031250000, 0.031250000,  # 14:00 – 16:00
    0.062500000, 0.062500000, 0.062500000, 0.062500000,  # 16:00 – 18:00
    0.031250000, 0.031250000, 0.031250000, 0.031250000,  # 18:00 – 20:00
]  # 24 slots, sums to 1.0

# ── Call Environment: Inbound Spanish ─────────────────────────────────────────

ENV_ES_WEEKLY_VOLUME    = 1000.0
ENV_ES_AHT_SECONDS      = 400.0
ENV_ES_AHT_STD_SECONDS  = 80.0
ENV_ES_OPERATING_HOURS  = (8, 20)
ENV_ES_DAY_WEIGHTS      = [0.20, 0.18, 0.20, 0.22, 0.20, 0.0, 0.0]  # Mon–Sun, sums to 1.0
ENV_ES_INTERVAL_WEIGHTS = [
    0.041666667, 0.041666667, 0.041666667, 0.041666667,  # 08:00 – 10:00
    0.062500000, 0.062500000, 0.062500000, 0.062500000,  # 10:00 – 12:00
    0.062500000, 0.062500000, 0.062500000, 0.062500000,  # 12:00 – 14:00
    0.041666667, 0.041666667, 0.041666667, 0.041666667,  # 14:00 – 16:00
    0.020833333, 0.020833333, 0.020833333, 0.020833333,  # 16:00 – 18:00
    0.020833333, 0.020833333, 0.020833333, 0.020833333,  # 18:00 – 20:00
]  # 24 slots, sums to 1.0

# ── Erlang derivation defaults (shared) ───────────────────────────────────────

DEFAULT_TARGET_SL              = 0.80
DEFAULT_ANSWER_WITHIN_SECONDS  = 30.0
DEFAULT_SHRINKAGE               = 0.30

# ── Roster derivation defaults ────────────────────────────────────────────────

DEFAULT_HEADCOUNT_BUFFER = 1.5