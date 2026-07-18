"""Glucose summary math — shared by the seed script and real imports.

The seed fakes realistic inputs and the Apple Health import supplies real
ones; both must produce the same eight run.glucose_* columns through the
same formulas.
"""

from datetime import datetime
from statistics import mean, stdev

GLUCOSE_RANGE_LOW_MG_DL = 70.0
GLUCOSE_RANGE_HIGH_MG_DL = 140.0


def compute_glucose_summary(
    during_values: list[float],
    pre_run_avg: float | None = None,
    post_run_avg: float | None = None,
) -> dict[str, float | None]:
    """The eight denormalized run.glucose_* columns.

    during_values are the readings during the run in time order; pre/post
    averages come from the adjacent 60-minute windows when available.
    """
    if not during_values:
        return {}
    in_range = sum(
        1
        for v in during_values
        if GLUCOSE_RANGE_LOW_MG_DL <= v <= GLUCOSE_RANGE_HIGH_MG_DL
    )
    tir = (in_range / len(during_values)) * 100
    return {
        "glucose_pre_run_60min_avg_mg_dl": (
            round(pre_run_avg, 1) if pre_run_avg is not None else None
        ),
        "glucose_at_start_mg_dl": round(during_values[0], 1),
        "glucose_at_end_mg_dl": round(during_values[-1], 1),
        "glucose_avg_during_run_mg_dl": round(mean(during_values), 1),
        "glucose_min_during_run_mg_dl": round(min(during_values), 1),
        "glucose_max_during_run_mg_dl": round(max(during_values), 1),
        "glucose_post_run_60min_avg_mg_dl": (
            round(post_run_avg, 1) if post_run_avg is not None else None
        ),
        "glucose_time_in_range_pct_during_run": round(tir, 1),
    }


def compute_daily_glucose(
    readings: list[tuple[datetime, float]],
) -> dict[str, float | None]:
    """Daily glucose_daily_records columns from (observed_at, mg/dL) readings.

    observed_at values keep their local offset (parsed with %z), so .hour is
    local time — the overnight window is local midnight to 6am.
    """
    values = [v for _, v in readings]
    avg = mean(values)
    std = stdev(values) if len(values) > 1 else None
    in_range = sum(
        1 for v in values if GLUCOSE_RANGE_LOW_MG_DL <= v <= GLUCOSE_RANGE_HIGH_MG_DL
    )
    overnight = [v for t, v in readings if t.hour < 6]

    return {
        "avg_glucose_mg_dl": round(avg, 1),
        "min_glucose_mg_dl": round(min(values), 1),
        "max_glucose_mg_dl": round(max(values), 1),
        "std_glucose_mg_dl": round(std, 1) if std is not None else None,
        "time_in_range_pct": round(in_range / len(values) * 100, 1),
        "glucose_variability_cv": (
            round(std / avg * 100, 1) if std is not None and avg else None
        ),
        # GMI = 3.31 + 0.02392 × mean glucose (standard CGM formula)
        "gmi": round(3.31 + 0.02392 * avg, 2),
        "overnight_avg_glucose_mg_dl": (
            round(mean(overnight), 1) if overnight else None
        ),
        "overnight_min_glucose_mg_dl": (
            round(min(overnight), 1) if overnight else None
        ),
    }
