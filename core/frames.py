import polars as pl

INTERVAL_SCHEMA = {
    "day":       pl.Int64,
    "slot":      pl.Int64,
    "skill":     pl.Utf8,
    "demand":    pl.Int64,
    "supply":    pl.Int64,   # nullable until solved
    "shortfall": pl.Int64,   # nullable until solved
}

QUEUE_PROFILE_SCHEMA = {
    "id":              pl.Utf8,
    "name":            pl.Utf8,
    "weekly_volume":   pl.Int64,
    "aht_seconds":     pl.Int64,
    "aht_std_seconds": pl.Int64,
    "operating_hours": pl.List(pl.Int64),
    "day_weights":     pl.List(pl.Float64),
    "interval_weights": pl.List(pl.Float64),
    "monthly_cost":    pl.Float64,
}

ROSTER_SCHEMA = {
    "primary_skill": pl.Utf8,
    "secondary_skill": pl.Utf8,  # nullable
    "count": pl.Int64,
}

