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

import polars as pl

#Account Services
acct_services = {
    "id": "account_services",
    "name": "Account Services",
    "weekly_volume": 3000.0,
    "aht_seconds": 240.0,
    "aht_std_seconds": 60.0,
    "operating_hours": (8, 20),
    "day_weights": [0.228571429, 0.171428571, 0.142857143, 0.142857143, 0.114285714, 0.114285714, 0.085714286],
    "interval_weights": [
        0.017341040, 0.023121387, 0.023121387, 0.028901734,  # 08:00 – 10:00
        0.034682081, 0.040462428, 0.046242775, 0.057803468,  # 10:00 – 12:00
        0.063583815, 0.052023121, 0.057803468, 0.063583815,  # 12:00 – 14:00
        0.075144509, 0.069364162, 0.057803468, 0.046242775,  # 14:00 – 16:00
        0.040462428, 0.034682081, 0.040462428, 0.034682081,  # 16:00 – 18:00
        0.023121387, 0.017341040, 0.028901734, 0.023121387,  # 18:00 – 20:00
    ],
    "monthly_cost": 3300.0,
}

online_orders = {
    "id": "online_orders",
    "name": "Online Orders",
    "weekly_volume": 2500.0,
    "aht_seconds": 420.0,
    "aht_std_seconds": 90.0,
    "operating_hours": (8, 20),
    "day_weights": [0.171428571, 0.114285714, 0.200000000, 0.228571429, 0.142857143, 0.085714286, 0.057142857],
    "interval_weights": [
        0.045197740, 0.045197740, 0.050847458, 0.073446328,  # 08:00 – 10:00
        0.079096045, 0.067796610, 0.056497175, 0.056497175,  # 10:00 – 12:00
        0.056497175, 0.056497175, 0.039548023, 0.033898305,  # 12:00 – 14:00
        0.039548023, 0.022598870, 0.022598870, 0.016949153,  # 14:00 – 16:00
        0.016949153, 0.022598870, 0.028248588, 0.039548023,  # 16:00 – 18:00
        0.045197740, 0.033898305, 0.028248588, 0.022598870,  # 18:00 – 20:00
    ],
    "monthly_cost": 3600.0,
}

photo = {
    "id": "photo",
    "name": "Photo",
    "weekly_volume": 800.0,
    "aht_seconds": 180.0,
    "aht_std_seconds": 40.0,
    "operating_hours": (8, 20),
    "day_weights": [0.257142857, 0.228571429, 0.171428571, 0.114285714, 0.114285714, 0.057142857, 0.057142857],
    "interval_weights": [
        0.056603774, 0.056603774, 0.066037736, 0.075471698,  # 08:00 – 10:00
        0.084905660, 0.075471698, 0.056603774, 0.047169811,  # 10:00 – 12:00
        0.037735849, 0.037735849, 0.047169811, 0.037735849,  # 12:00 – 14:00
        0.028301887, 0.018867925, 0.037735849, 0.047169811,  # 14:00 – 16:00
        0.028301887, 0.037735849, 0.018867925, 0.018867925,  # 16:00 – 18:00
        0.028301887, 0.018867925, 0.018867925, 0.018867925,  # 18:00 – 20:00
    ],
    "monthly_cost": 500.0,
}

floral = {
    "id": "floral",
    "name": "Floral",
    "weekly_volume": 600.0,
    "aht_seconds": 200.0,
    "aht_std_seconds": 50.0,
    "operating_hours": (8, 20),
    "day_weights": [0.085714286, 0.057142857, 0.114285714, 0.142857143, 0.171428571, 0.228571429, 0.200000000],
    "interval_weights": [
        0.047619048, 0.066666667, 0.076190476, 0.076190476,  # 08:00 – 10:00
        0.085714286, 0.076190476, 0.047619048, 0.047619048,  # 10:00 – 12:00
        0.038095238, 0.038095238, 0.047619048, 0.038095238,  # 12:00 – 14:00
        0.019047619, 0.028571429, 0.028571429, 0.057142857,  # 14:00 – 16:00
        0.028571429, 0.028571429, 0.019047619, 0.028571429,  # 16:00 – 18:00
        0.019047619, 0.009523810, 0.009523810, 0.019047619,  # 18:00 – 20:00 (corrected)
    ],
    "monthly_cost": 500.0,
}

bakery = {
    "id": "bakery",
    "name": "Bakery",
    "weekly_volume": 400.0,
    "aht_seconds": 150.0,
    "aht_std_seconds": 30.0,
    "operating_hours": (8, 20),
    "day_weights": [0.171428571, 0.171428571, 0.142857143, 0.142857143, 0.142857143, 0.114285714, 0.114285714],
    "interval_weights": [
        0.038461538, 0.057692308, 0.067307692, 0.076923077,  # 08:00 – 10:00
        0.076923077, 0.086538462, 0.057692308, 0.057692308,  # 10:00 – 12:00
        0.028846154, 0.038461538, 0.038461538, 0.048076923,  # 12:00 – 14:00
        0.028846154, 0.028846154, 0.038461538, 0.067307692,  # 14:00 – 16:00
        0.028846154, 0.028846154, 0.009615385, 0.038461538,  # 16:00 – 18:00
        0.019230769, 0.000000000, 0.019230769, 0.019230769,  # 18:00 – 20:00
    ],
    "monthly_cost": 500.0,
}

escalations = {
    "id": "escalations",
    "name": "Escalations",
    "weekly_volume": 300.0,
    "aht_seconds": 720.0,
    "aht_std_seconds": 180.0,
    "operating_hours": (8, 20),
    "day_weights": [0.200000000, 0.114285714, 0.114285714, 0.085714286, 0.142857143, 0.171428571, 0.171428571],
    "interval_weights": [
        0.011235955, 0.028089888, 0.022471910, 0.022471910,  # 08:00 – 10:00
        0.039325843, 0.033707865, 0.050561798, 0.056179775,  # 10:00 – 12:00
        0.061797753, 0.044943820, 0.050561798, 0.067415730,  # 12:00 – 14:00
        0.067415730, 0.067415730, 0.056179775, 0.050561798,  # 14:00 – 16:00
        0.044943820, 0.033707865, 0.044943820, 0.039325843,  # 16:00 – 18:00
        0.022471910, 0.022471910, 0.033707865, 0.028089888,  # 18:00 – 20:00
    ],
    "monthly_cost": 800.0,
}

#stack series to make pl dataframe
DF_QUEUE_PROFILES = (pl.DataFrame([
    acct_services,
    online_orders,
    photo,
    floral,
    bakery,
    escalations,
]))


DF_STARTING_ROSTER = pl.DataFrame([
    {"primary_skill": "account_services", "secondary_skill": "floral",      "count": 3},
    {"primary_skill": "account_services", "secondary_skill": "bakery",      "count": 5},
    {"primary_skill": "account_services", "secondary_skill": "escalations", "count": 5},
    {"primary_skill": "account_services", "secondary_skill": None,          "count": 16},
    {"primary_skill": "online_orders",    "secondary_skill": "photo",       "count": 7},
    {"primary_skill": "online_orders",    "secondary_skill": "bakery",      "count": 1},
    {"primary_skill": "online_orders",    "secondary_skill": "escalations", "count": 2},
    {"primary_skill": "online_orders",    "secondary_skill": None,          "count": 13},
])