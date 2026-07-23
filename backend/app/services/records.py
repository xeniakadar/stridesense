"""Personal records over a run history.

Distance records use tolerance bands (a "5K" is rarely 5.00 km on a
watch) and rank by pace, which is fair across the band; the row's value
rendering is the frontend's business. Biggest week is an ISO-week
distance sum and has no single run to link to.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

from app.models import Run

# kind -> (min_km, max_km)
DISTANCE_BANDS: dict[str, tuple[float, float]] = {
    "fastest_5k": (4.8, 5.5),
    "fastest_10k": (9.5, 11.0),
    "fastest_half": (20.6, 21.8),
}


@dataclass
class RecordItem:
    kind: str
    run_id: UUID | None  # None for biggest_week — it isn't one run
    date: date  # week start for biggest_week
    distance_km: float
    duration_seconds: int | None
    avg_pace_seconds_per_km: float | None


def compute_records(runs: list[Run]) -> list[RecordItem]:
    """Every record with data to back it; kinds without a match are absent."""
    records: list[RecordItem] = []

    for kind, (lo, hi) in DISTANCE_BANDS.items():
        candidates = [
            r
            for r in runs
            if lo <= r.distance_km <= hi and r.avg_pace_seconds_per_km
        ]
        if not candidates:
            continue
        best = min(candidates, key=lambda r: r.avg_pace_seconds_per_km)
        records.append(
            RecordItem(
                kind=kind,
                run_id=best.id,
                date=best.date,
                distance_km=best.distance_km,
                duration_seconds=best.duration_seconds,
                avg_pace_seconds_per_km=best.avg_pace_seconds_per_km,
            )
        )

    if runs:
        longest = max(runs, key=lambda r: r.distance_km)
        records.append(
            RecordItem(
                kind="longest_run",
                run_id=longest.id,
                date=longest.date,
                distance_km=longest.distance_km,
                duration_seconds=longest.duration_seconds,
                avg_pace_seconds_per_km=longest.avg_pace_seconds_per_km,
            )
        )

        by_week: dict[date, float] = defaultdict(float)
        for r in runs:
            monday = r.date - timedelta(days=r.date.weekday())
            by_week[monday] += r.distance_km
        best_week = max(by_week, key=lambda w: by_week[w])
        records.append(
            RecordItem(
                kind="biggest_week",
                run_id=None,
                date=best_week,
                distance_km=round(by_week[best_week], 2),
                duration_seconds=None,
                avg_pace_seconds_per_km=None,
            )
        )

    return records
