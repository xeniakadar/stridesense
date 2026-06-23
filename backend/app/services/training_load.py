"""Compute per-run training load and the Acute:Chronic Workload Ratio (ACWR)."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from app.models import Run

ACUTE_WINDOW_DAYS = 7
CHRONIC_WINDOW_DAYS = 28

# ACWR interpretation thresholds (sports-science convention)
SWEET_SPOT_LOW = 0.8
SWEET_SPOT_HIGH = 1.3
DANGER_THRESHOLD = 1.5


@dataclass
class LoadPoint:
    date: date
    acute_load: float
    chronic_load: float
    acwr: float | None  # None when chronic baseline is not yet established
    zone: str  # "detraining" | "optimal" | "caution" | "danger" | "building"


def _session_load(run: Run) -> float:
    """Session-RPE style load: duration (min) x effort.

    Falls back gracefully when RPE is missing."""
    minutes = run.duration_seconds / 60
    if run.perceived_effort is not None:
        return minutes * run.perceived_effort
    # Fallback: approximate effort from HR if available, else assume moderate (5)
    if run.avg_hr is not None:
        # crude: map 100-190 bpm to effort ~3-9
        approx_effort = max(1, min(10, (run.avg_hr - 70) / 13))
        return minutes * approx_effort
    return minutes * 5


def _zone(acwr: float | None) -> str:
    if acwr is None:
        return "building"
    if acwr < SWEET_SPOT_LOW:
        return "detraining"
    if acwr <= SWEET_SPOT_HIGH:
        return "optimal"
    if acwr < DANGER_THRESHOLD:
        return "caution"
    return "danger"


def compute_load_series(runs: list[Run]) -> list[LoadPoint]:
    """Compute a daily ACWR series over the period covered by the runs."""
    if not runs:
        return []

    # Aggregate load per calendar day
    load_by_day: dict[date, float] = defaultdict(float)
    for r in runs:
        load_by_day[r.date] += _session_load(r)

    start = min(load_by_day)
    end = max(load_by_day)

    series: list[LoadPoint] = []
    day = start
    while day <= end:
        acute = sum(
            load_by_day.get(day - timedelta(days=i), 0.0)
            for i in range(ACUTE_WINDOW_DAYS)
        ) / ACUTE_WINDOW_DAYS
        chronic = sum(
            load_by_day.get(day - timedelta(days=i), 0.0)
            for i in range(CHRONIC_WINDOW_DAYS)
        ) / CHRONIC_WINDOW_DAYS

        # ACWR only meaningful once a chronic baseline exists
        acwr = (acute / chronic) if chronic > 0 else None
        series.append(
            LoadPoint(
                date=day,
                acute_load=round(acute, 1),
                chronic_load=round(chronic, 1),
                acwr=round(acwr, 2) if acwr is not None else None,
                zone=_zone(acwr),
            )
        )
        day += timedelta(days=1)

    return series


def acwr_for_run(run: Run, all_runs: list[Run]) -> LoadPoint | None:
    """The ACWR on the day of a specific run — what the runner was carrying
    into that session."""
    series = compute_load_series(all_runs)
    for point in series:
        if point.date == run.date:
            return point
    return None
