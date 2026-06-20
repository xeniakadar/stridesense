"""Find runs similar to a target run using weighted cosine similarity over
normalized features."""

import math
from dataclasses import dataclass
from statistics import mean, pstdev

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


def find_similar_runs(
    target: Run,
    candidates: list[Run],
    limit: int = 5,
) -> list[SimilarRun]:
    """Rank candidates by similarity to target. Excludes the target itself."""
    pool = [r for r in candidates if r.id != target.id]
    if not pool:
        return []

    target_f = extract_features(target)
    pool_f = [extract_features(r) for r in pool]
    norms = _normalizers([target_f, *pool_f])

    scored = [
        SimilarRun(run=r, score=_weighted_cosine(target_f, f, norms))
        for r, f in zip(pool, pool_f, strict=True)
    ]
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[:limit]
