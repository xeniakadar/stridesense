"""Find runs similar to a target run using weighted cosine similarity over
normalized features."""

import math
from dataclasses import dataclass
from statistics import mean, median, pstdev

from app.models import Run
from app.services.features import RunFeatures, extract_features

# Relative importance of each dimension when judging "comparable run".
# Pace and distance define a run; weather is context, not identity.
FEATURE_WEIGHTS: dict[str, float] = {
    "distance_km": 1.0,
    "pace_seconds_per_km": 1.0,
    "avg_hr": 0.8,
    "elevation_gain_m": 0.5,
    "perceived_effort": 0.4,
    "weather_temp_avg_c": 0.3,
    "weather_humidity_avg": 0.2,
    "glucose_avg_during_run": 0.3,
    "glucose_time_in_range_pct": 0.2,
}


@dataclass
class SimilarRun:
    run: Run
    score: float  # 0..1, higher = more similar


def _collect(features: list[RunFeatures], attr: str) -> list[float]:
    return [
        getattr(f, attr)
        for f in features
        if getattr(f, attr) is not None
    ]


def _normalizers(all_features: list[RunFeatures]) -> dict[str, tuple[float, float]]:
    """Return (mean, stddev) per dimension for z-scoring. Stddev floored to
    avoid divide-by-zero on constant dimensions."""
    norms: dict[str, tuple[float, float]] = {}
    for attr in FEATURE_WEIGHTS:
        values = _collect(all_features, attr)
        if len(values) >= 2:
            m = mean(values)
            sd = pstdev(values) or 1.0
        else:
            m, sd = 0.0, 1.0
        norms[attr] = (m, sd)
    return norms


def _z(value: float, mean_sd: tuple[float, float]) -> float:
    m, sd = mean_sd
    return (value - m) / sd


def _weighted_cosine(
    a: RunFeatures,
    b: RunFeatures,
    norms: dict[str, tuple[float, float]],
) -> float:
    """Weighted cosine similarity over dimensions BOTH runs have."""
    dot = 0.0
    mag_a = 0.0
    mag_b = 0.0
    for attr, weight in FEATURE_WEIGHTS.items():
        va = getattr(a, attr)
        vb = getattr(b, attr)
        if va is None or vb is None:
            continue  # only compare shared dimensions
        za = _z(va, norms[attr]) * weight
        zb = _z(vb, norms[attr]) * weight
        dot += za * zb
        mag_a += za * za
        mag_b += zb * zb
    if mag_a == 0 or mag_b == 0:
        return 0.0
    cosine = dot / (math.sqrt(mag_a) * math.sqrt(mag_b))
    # cosine is in [-1, 1]; map to [0, 1] so 1.0 = identical direction
    return (cosine + 1) / 2


@dataclass
class SimilarRunsPool:
    runs: list[SimilarRun]
    pool_size: int  # candidates actually ranked (after type filter/fallback)
    type_fallback: bool  # True when too few same-type runs forced an all-types pool


@dataclass
class ComparisonDeltas:
    """This run minus the MEDIAN of its comparables, per metric.

    Median, not mean: one outlier comparable (a bonked run, a heat wave)
    shouldn't drag the baseline. A delta is None whenever either side
    lacks the metric. Negative pace/HR deltas mean faster/lower.
    """

    pace_delta_seconds_per_km: float | None
    avg_hr_delta: float | None
    weather_temp_delta_c: float | None
    glucose_delta_mg_dl: float | None


def find_similar_runs_detailed(
    target: Run,
    candidates: list[Run],
    limit: int = 5,
    min_pool: int = 8,
) -> SimilarRunsPool:
    """Rank candidates by similarity to target.

    Prefers runs of the same type; falls back to all runs when fewer than
    `min_pool` same-type candidates exist (rare run types like races).
    Excludes the target itself."""
    same_type = [
        r for r in candidates if r.run_type == target.run_type and r.id != target.id
    ]
    if len(same_type) >= min_pool:
        pool = same_type
        type_fallback = False
    else:
        pool = [r for r in candidates if r.id != target.id]
        type_fallback = True

    if not pool:
        return SimilarRunsPool(runs=[], pool_size=0, type_fallback=type_fallback)

    target_f = extract_features(target)
    pool_f = [extract_features(r) for r in pool]
    norms = _normalizers([target_f, *pool_f])

    scored = [
        SimilarRun(run=r, score=_weighted_cosine(target_f, f, norms))
        for r, f in zip(pool, pool_f, strict=True)
    ]
    scored.sort(key=lambda s: s.score, reverse=True)
    return SimilarRunsPool(
        runs=scored[:limit], pool_size=len(pool), type_fallback=type_fallback
    )


def find_similar_runs(
    target: Run,
    candidates: list[Run],
    limit: int = 5,
    min_pool: int = 8,
) -> list[SimilarRun]:
    return find_similar_runs_detailed(target, candidates, limit, min_pool).runs


def _median_delta(
    target_value: float | None, comparable_values: list[float]
) -> float | None:
    if target_value is None or not comparable_values:
        return None
    return round(target_value - median(comparable_values), 1)


def compare_to_similar(
    target: Run, similar: list[SimilarRun]
) -> ComparisonDeltas | None:
    """Deltas of this run vs the median of its comparables (see dataclass)."""
    if not similar:
        return None
    runs = [s.run for s in similar]
    # Start temp: the temperature number the rest of the UI shows for a run
    return ComparisonDeltas(
        pace_delta_seconds_per_km=_median_delta(
            target.avg_pace_seconds_per_km,
            [r.avg_pace_seconds_per_km for r in runs if r.avg_pace_seconds_per_km],
        ),
        avg_hr_delta=_median_delta(
            target.avg_hr, [r.avg_hr for r in runs if r.avg_hr is not None]
        ),
        weather_temp_delta_c=_median_delta(
            target.weather_temp_start_c,
            [r.weather_temp_start_c for r in runs if r.weather_temp_start_c is not None],
        ),
        glucose_delta_mg_dl=_median_delta(
            target.glucose_avg_during_run_mg_dl,
            [
                r.glucose_avg_during_run_mg_dl
                for r in runs
                if r.glucose_avg_during_run_mg_dl is not None
            ],
        ),
    )
