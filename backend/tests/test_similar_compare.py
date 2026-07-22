from datetime import date, timedelta
from uuid import uuid4

from httpx import AsyncClient

from app.models import Run
from app.models.enums import RunType
from app.services.similarity import (
    SimilarRun,
    compare_to_similar,
    find_similar_runs_detailed,
)


def _run(**overrides) -> Run:
    defaults = dict(
        id=uuid4(),
        date=date(2026, 7, 1),
        run_type=RunType.EASY,
        distance_km=8.0,
        duration_seconds=2700,
        avg_pace_seconds_per_km=420.0,
    )
    return Run(**defaults | overrides)


def _similar(*runs: Run) -> list[SimilarRun]:
    return [SimilarRun(run=r, score=0.9) for r in runs]


# --- comparison math (pure) ---


def test_comparison_uses_median_not_mean() -> None:
    target = _run(avg_pace_seconds_per_km=408.0)
    # One outlier (500) drags the mean to 440; the median stays 420
    comparables = _similar(
        _run(avg_pace_seconds_per_km=400.0),
        _run(avg_pace_seconds_per_km=420.0),
        _run(avg_pace_seconds_per_km=500.0),
    )
    comparison = compare_to_similar(target, comparables)
    assert comparison is not None
    assert comparison.pace_delta_seconds_per_km == -12.0  # 408 - 420, not 408 - 440


def test_comparison_skips_metrics_missing_on_either_side() -> None:
    target = _run(avg_hr=150, weather_temp_start_c=None)
    comparables = _similar(
        _run(avg_hr=None, weather_temp_start_c=20.0),
        _run(avg_hr=None, weather_temp_start_c=22.0),
    )
    comparison = compare_to_similar(target, comparables)
    assert comparison is not None
    assert comparison.avg_hr_delta is None  # no comparable has HR
    assert comparison.weather_temp_delta_c is None  # target has no temp
    assert comparison.pace_delta_seconds_per_km == 0.0  # both sides present


def test_comparison_glucose_requires_both_sides() -> None:
    target_with = _run(glucose_avg_during_run_mg_dl=110.0)
    target_without = _run()
    comp_with = _similar(
        _run(glucose_avg_during_run_mg_dl=100.0),
        _run(glucose_avg_during_run_mg_dl=104.0),
    )
    comp_without = _similar(_run(), _run())

    assert (
        compare_to_similar(target_with, comp_with).glucose_delta_mg_dl == 8.0
    )  # 110 - median(100, 104)
    assert compare_to_similar(target_with, comp_without).glucose_delta_mg_dl is None
    assert compare_to_similar(target_without, comp_with).glucose_delta_mg_dl is None


def test_comparison_empty_pool_returns_none() -> None:
    assert compare_to_similar(_run(), []) is None


# --- pool metadata ---


def test_detailed_reports_type_fallback_on_thin_pool() -> None:
    target = _run(run_type=RunType.RACE)
    candidates = [_run(run_type=RunType.RACE) for _ in range(3)] + [
        _run(run_type=RunType.EASY) for _ in range(5)
    ]
    pool = find_similar_runs_detailed(target, candidates, min_pool=8)
    assert pool.type_fallback is True
    assert pool.pool_size == 8  # all candidates, target excluded implicitly


def test_detailed_no_fallback_with_enough_same_type() -> None:
    target = _run()
    candidates = [_run() for _ in range(8)] + [_run(run_type=RunType.TEMPO)]
    pool = find_similar_runs_detailed(target, candidates, min_pool=8)
    assert pool.type_fallback is False
    assert pool.pool_size == 8  # same-type only


def test_detailed_empty_candidates() -> None:
    pool = find_similar_runs_detailed(_run(), [])
    assert pool.runs == []
    assert pool.pool_size == 0


# --- endpoint shape ---


async def test_similar_endpoint_envelope_shape(
    client: AsyncClient, isolated_user
) -> None:
    today = date(2026, 6, 10)

    def payload(d: date, minutes: int, hr: int) -> dict:
        return {
            "date": d.isoformat(),
            "run_type": "easy",
            "distance_km": 8.0,
            "duration_seconds": minutes * 60,
            "avg_hr": hr,
        }

    target = (await client.post("/runs", json=payload(today, 48, 148))).json()
    await client.post("/runs", json=payload(today - timedelta(days=3), 50, 150))
    await client.post("/runs", json=payload(today - timedelta(days=6), 52, 154))

    res = await client.get(f"/runs/{target['id']}/similar")
    assert res.status_code == 200
    body = res.json()

    assert set(body) == {"runs", "pool_size", "type_fallback", "comparison"}
    assert body["pool_size"] == 2
    assert body["type_fallback"] is True  # 2 same-type < min_pool of 8
    assert len(body["runs"]) == 2
    for item in body["runs"]:
        assert "weather_temp_start_c" in item
        assert 0.0 <= item["score"] <= 1.0

    comparison = body["comparison"]
    # pace: 48min/8km = 360 s/km vs median(375, 390) = 382.5 → -22.5
    assert comparison["pace_delta_seconds_per_km"] == -22.5
    assert comparison["avg_hr_delta"] == 148 - 152  # median(150, 154)
    assert comparison["weather_temp_delta_c"] is None
    assert comparison["glucose_delta_mg_dl"] is None
