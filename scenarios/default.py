"""
Default scenario: Retail customer service center.
Six skill queues modelled on a big-box retail contact centre.
Interval weights cover the operating window (8:00–20:00), 24 x 30-min slots (slots 16–39).
Day weights: 0=Monday … 6=Sunday.

Skill cost model:
  Primary skills  — account_services: $3,300/agent/month
                    online_orders:    $3,600/agent/month
  Secondary skills — photo, floral, bakery: +$500/agent/month
                     escalations:           +$800/agent/month
  Each agent may hold exactly one primary skill and at most one secondary skill.
  Roster cost is derived post-solve from the skill composition of each RosterEntry.
"""
from domain import QueueProfile, RosterEntry, Roster

# ── Skills ────────────────────────────────────────────────────────────────────

SKILL_ACCT_ID    = "account_services"
SKILL_ACCT_NAME  = "Account Services"
SKILL_ONLINE_ID  = "online_orders"
SKILL_ONLINE_NAME = "Online Orders"
SKILL_PHOTO_ID   = "photo"
SKILL_PHOTO_NAME = "Photo"
SKILL_FLORAL_ID  = "floral"
SKILL_FLORAL_NAME = "Floral"
SKILL_BAKERY_ID  = "bakery"
SKILL_BAKERY_NAME = "Bakery"
SKILL_ESC_ID     = "escalations"
SKILL_ESC_NAME   = "Escalations"

# ── Monthly costs per skill ───────────────────────────────────────────────────
# Primary skills: base monthly cost per agent certified on that skill.
# Secondary skills: incremental monthly cost added on top of the primary.

SKILL_ACCT_MONTHLY_COST   = 3300.0   # primary
SKILL_ONLINE_MONTHLY_COST = 3600.0   # primary
SKILL_PHOTO_MONTHLY_COST  =  500.0   # secondary (incremental)
SKILL_FLORAL_MONTHLY_COST =  500.0   # secondary (incremental)
SKILL_BAKERY_MONTHLY_COST =  500.0   # secondary (incremental)
SKILL_ESC_MONTHLY_COST    =  800.0   # secondary (incremental)

# ── Call Environment: Account Services ───────────────────────────────────────
# High volume, steady, Monday spike, moderate AHT

ENV_ACCT_WEEKLY_VOLUME   = 3000.0
ENV_ACCT_AHT_SECONDS     = 240.0
ENV_ACCT_AHT_STD_SECONDS = 60.0
ENV_ACCT_OPERATING_HOURS = (8, 20)
ENV_ACCT_DAY_WEIGHTS = [0.228571429, 0.171428571, 0.142857143, 0.142857143, 0.114285714, 0.114285714, 0.085714286]
ENV_ACCT_INTERVAL_WEIGHTS = [
    0.017341040, 0.023121387, 0.023121387, 0.028901734,  # 08:00 – 10:00
    0.034682081, 0.040462428, 0.046242775, 0.057803468,  # 10:00 – 12:00
    0.063583815, 0.052023121, 0.057803468, 0.063583815,  # 12:00 – 14:00
    0.075144509, 0.069364162, 0.057803468, 0.046242775,  # 14:00 – 16:00
    0.040462428, 0.034682081, 0.040462428, 0.034682081,  # 16:00 – 18:00
    0.023121387, 0.017341040, 0.028901734, 0.023121387,  # 18:00 – 20:00
]

# ── Call Environment: Online Orders ──────────────────────────────────────────
# High volume, longest AHT, midweek/Thursday peak

ENV_ONLINE_WEEKLY_VOLUME   = 2500.0
ENV_ONLINE_AHT_SECONDS     = 420.0
ENV_ONLINE_AHT_STD_SECONDS = 90.0
ENV_ONLINE_OPERATING_HOURS = (8, 20)
ENV_ONLINE_DAY_WEIGHTS = [0.171428571, 0.114285714, 0.200000000, 0.228571429, 0.142857143, 0.085714286, 0.057142857]
ENV_ONLINE_INTERVAL_WEIGHTS = [
    0.045197740, 0.045197740, 0.050847458, 0.073446328,  # 08:00 – 10:00
    0.079096045, 0.067796610, 0.056497175, 0.056497175,  # 10:00 – 12:00
    0.056497175, 0.056497175, 0.039548023, 0.033898305,  # 12:00 – 14:00
    0.039548023, 0.022598870, 0.022598870, 0.016949153,  # 14:00 – 16:00
    0.016949153, 0.022598870, 0.028248588, 0.039548023,  # 16:00 – 18:00
    0.045197740, 0.033898305, 0.028248588, 0.022598870,  # 18:00 – 20:00
]

# ── Call Environment: Photo ───────────────────────────────────────────────────
# Low-moderate volume, peaks Mon/Tue, short AHT

ENV_PHOTO_WEEKLY_VOLUME   = 800.0
ENV_PHOTO_AHT_SECONDS     = 180.0
ENV_PHOTO_AHT_STD_SECONDS = 40.0
ENV_PHOTO_OPERATING_HOURS = (8, 20)
ENV_PHOTO_DAY_WEIGHTS = [0.257142857, 0.228571429, 0.171428571, 0.114285714, 0.114285714, 0.057142857, 0.057142857]
ENV_PHOTO_INTERVAL_WEIGHTS = [
    0.056603774, 0.056603774, 0.066037736, 0.075471698,  # 08:00 – 10:00
    0.084905660, 0.075471698, 0.056603774, 0.047169811,  # 10:00 – 12:00
    0.037735849, 0.037735849, 0.047169811, 0.037735849,  # 12:00 – 14:00
    0.028301887, 0.018867925, 0.037735849, 0.047169811,  # 14:00 – 16:00
    0.028301887, 0.037735849, 0.018867925, 0.018867925,  # 16:00 – 18:00
    0.028301887, 0.018867925, 0.018867925, 0.018867925,  # 18:00 – 20:00
]

# ── Call Environment: Floral ──────────────────────────────────────────────────
# Low volume, heavy Sat/Sun, near zero midweek, short AHT

ENV_FLORAL_WEEKLY_VOLUME   = 600.0
ENV_FLORAL_AHT_SECONDS     = 200.0
ENV_FLORAL_AHT_STD_SECONDS = 50.0
ENV_FLORAL_OPERATING_HOURS = (8, 20)
ENV_FLORAL_DAY_WEIGHTS = [0.085714286, 0.057142857, 0.114285714, 0.142857143, 0.171428571, 0.228571429, 0.200000000]
ENV_FLORAL_INTERVAL_WEIGHTS = [
    0.047619048, 0.066666667, 0.076190476, 0.076190476,  # 08:00 – 10:00
    0.085714286, 0.076190476, 0.047619048, 0.047619048,  # 10:00 – 12:00
    0.038095238, 0.038095238, 0.047619048, 0.038095238,  # 12:00 – 14:00
    0.019047619, 0.028571429, 0.028571429, 0.057142857,  # 14:00 – 16:00
    0.028571429, 0.028571429, 0.019047619, 0.028571429,  # 16:00 – 18:00
    0.019047619, 0.009523810, 0.009523810, 0.019047619,  # 18:00 – 20:00 (corrected)
]

# ── Call Environment: Bakery ──────────────────────────────────────────────────
# Lowest volume, flat curve, shortest AHT — filler queue

ENV_BAKERY_WEEKLY_VOLUME   = 400.0
ENV_BAKERY_AHT_SECONDS     = 150.0
ENV_BAKERY_AHT_STD_SECONDS = 30.0
ENV_BAKERY_OPERATING_HOURS = (8, 20)
ENV_BAKERY_DAY_WEIGHTS = [0.171428571, 0.171428571, 0.142857143, 0.142857143, 0.142857143, 0.114285714, 0.114285714]
ENV_BAKERY_INTERVAL_WEIGHTS = [
    0.038461538, 0.057692308, 0.067307692, 0.076923077,  # 08:00 – 10:00
    0.076923077, 0.086538462, 0.057692308, 0.057692308,  # 10:00 – 12:00
    0.028846154, 0.038461538, 0.038461538, 0.048076923,  # 12:00 – 14:00
    0.028846154, 0.028846154, 0.038461538, 0.067307692,  # 14:00 – 16:00
    0.028846154, 0.028846154, 0.009615385, 0.038461538,  # 16:00 – 18:00
    0.019230769, 0.000000000, 0.019230769, 0.019230769,  # 18:00 – 20:00
]

# ── Call Environment: Escalations ────────────────────────────────────────────
# Low volume, highest AHT, held by senior agents only

ENV_ESC_WEEKLY_VOLUME   = 300.0
ENV_ESC_AHT_SECONDS     = 720.0
ENV_ESC_AHT_STD_SECONDS = 180.0
ENV_ESC_OPERATING_HOURS = (8, 20)
ENV_ESC_DAY_WEIGHTS = [0.200000000, 0.114285714, 0.114285714, 0.085714286, 0.142857143, 0.171428571, 0.171428571]
ENV_ESC_INTERVAL_WEIGHTS = [
    0.011235955, 0.028089888, 0.022471910, 0.022471910,  # 08:00 – 10:00
    0.039325843, 0.033707865, 0.050561798, 0.056179775,  # 10:00 – 12:00
    0.061797753, 0.044943820, 0.050561798, 0.067415730,  # 12:00 – 14:00
    0.067415730, 0.067415730, 0.056179775, 0.050561798,  # 14:00 – 16:00
    0.044943820, 0.033707865, 0.044943820, 0.039325843,  # 16:00 – 18:00
    0.022471910, 0.022471910, 0.033707865, 0.028089888,  # 18:00 – 20:00
]

# ── Erlang defaults ───────────────────────────────────────────────────────────

DEFAULT_TARGET_SL             = 0.80
DEFAULT_ANSWER_WITHIN_SECONDS = 30.0
DEFAULT_SHRINKAGE             = 0.30

# ── Profiles ──────────────────────────────────────────────────────────────────

DEFAULT_PROFILES = [
    QueueProfile(skill_id=SKILL_ACCT_ID,   skill_name=SKILL_ACCT_NAME,   weekly_volume=ENV_ACCT_WEEKLY_VOLUME,   aht_seconds=ENV_ACCT_AHT_SECONDS,   aht_std_seconds=ENV_ACCT_AHT_STD_SECONDS,   operating_hours=ENV_ACCT_OPERATING_HOURS,   day_weights=ENV_ACCT_DAY_WEIGHTS,   interval_weights=ENV_ACCT_INTERVAL_WEIGHTS,   monthly_cost=SKILL_ACCT_MONTHLY_COST,   target_sl=DEFAULT_TARGET_SL, answer_within_seconds=DEFAULT_ANSWER_WITHIN_SECONDS, shrinkage=DEFAULT_SHRINKAGE),
    QueueProfile(skill_id=SKILL_ONLINE_ID,  skill_name=SKILL_ONLINE_NAME, weekly_volume=ENV_ONLINE_WEEKLY_VOLUME, aht_seconds=ENV_ONLINE_AHT_SECONDS, aht_std_seconds=ENV_ONLINE_AHT_STD_SECONDS, operating_hours=ENV_ONLINE_OPERATING_HOURS, day_weights=ENV_ONLINE_DAY_WEIGHTS, interval_weights=ENV_ONLINE_INTERVAL_WEIGHTS, monthly_cost=SKILL_ONLINE_MONTHLY_COST, target_sl=DEFAULT_TARGET_SL, answer_within_seconds=DEFAULT_ANSWER_WITHIN_SECONDS, shrinkage=DEFAULT_SHRINKAGE),
    QueueProfile(skill_id=SKILL_PHOTO_ID,   skill_name=SKILL_PHOTO_NAME,  weekly_volume=ENV_PHOTO_WEEKLY_VOLUME,  aht_seconds=ENV_PHOTO_AHT_SECONDS,  aht_std_seconds=ENV_PHOTO_AHT_STD_SECONDS,  operating_hours=ENV_PHOTO_OPERATING_HOURS,  day_weights=ENV_PHOTO_DAY_WEIGHTS,  interval_weights=ENV_PHOTO_INTERVAL_WEIGHTS,  monthly_cost=SKILL_PHOTO_MONTHLY_COST,  target_sl=DEFAULT_TARGET_SL, answer_within_seconds=DEFAULT_ANSWER_WITHIN_SECONDS, shrinkage=DEFAULT_SHRINKAGE),
    QueueProfile(skill_id=SKILL_FLORAL_ID,  skill_name=SKILL_FLORAL_NAME, weekly_volume=ENV_FLORAL_WEEKLY_VOLUME, aht_seconds=ENV_FLORAL_AHT_SECONDS, aht_std_seconds=ENV_FLORAL_AHT_STD_SECONDS, operating_hours=ENV_FLORAL_OPERATING_HOURS, day_weights=ENV_FLORAL_DAY_WEIGHTS, interval_weights=ENV_FLORAL_INTERVAL_WEIGHTS, monthly_cost=SKILL_FLORAL_MONTHLY_COST, target_sl=DEFAULT_TARGET_SL, answer_within_seconds=DEFAULT_ANSWER_WITHIN_SECONDS, shrinkage=DEFAULT_SHRINKAGE),
    QueueProfile(skill_id=SKILL_BAKERY_ID,  skill_name=SKILL_BAKERY_NAME, weekly_volume=ENV_BAKERY_WEEKLY_VOLUME, aht_seconds=ENV_BAKERY_AHT_SECONDS, aht_std_seconds=ENV_BAKERY_AHT_STD_SECONDS, operating_hours=ENV_BAKERY_OPERATING_HOURS, day_weights=ENV_BAKERY_DAY_WEIGHTS, interval_weights=ENV_BAKERY_INTERVAL_WEIGHTS, monthly_cost=SKILL_BAKERY_MONTHLY_COST, target_sl=DEFAULT_TARGET_SL, answer_within_seconds=DEFAULT_ANSWER_WITHIN_SECONDS, shrinkage=DEFAULT_SHRINKAGE),
    QueueProfile(skill_id=SKILL_ESC_ID,     skill_name=SKILL_ESC_NAME,    weekly_volume=ENV_ESC_WEEKLY_VOLUME,   aht_seconds=ENV_ESC_AHT_SECONDS,   aht_std_seconds=ENV_ESC_AHT_STD_SECONDS,   operating_hours=ENV_ESC_OPERATING_HOURS,   day_weights=ENV_ESC_DAY_WEIGHTS,   interval_weights=ENV_ESC_INTERVAL_WEIGHTS,   monthly_cost=SKILL_ESC_MONTHLY_COST, target_sl=DEFAULT_TARGET_SL, answer_within_seconds=DEFAULT_ANSWER_WITHIN_SECONDS, shrinkage=DEFAULT_SHRINKAGE),
]

# ── Starting Roster ───────────────────────────────────────────────────────────

DEFAULT_ROSTER = Roster(entries=[
    RosterEntry(skills=["account_services", "floral"],      count=3),
    RosterEntry(skills=["account_services", "bakery"],      count=5),
    RosterEntry(skills=["account_services", "escalations"], count=5),
    RosterEntry(skills=["account_services"],                count=16),
    RosterEntry(skills=["online_orders", "photo"],          count=7),
    RosterEntry(skills=["online_orders", "bakery"],         count=1),
    RosterEntry(skills=["online_orders", "escalations"],    count=2),
    RosterEntry(skills=["online_orders"],                   count=13),
])