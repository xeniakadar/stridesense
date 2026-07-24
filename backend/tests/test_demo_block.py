import json
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GlucoseDailyRecord, Run, RunGlucoseSample
from app.models.enums import DataSource, RunType, RunTypeSource
from scripts.export_demo_block import (
    FIXTURE_FIELDS,
    build_fixture,
    snap_to_city,
    to_fixture_row,
    validate_block,
)
from scripts.seed_demo import CITIES, RACES, city_on, generate_dataset, load_demo_data


def _block_run(**overrides) -> Run:
    defaults = dict(
        id=uuid4(),
        date=date(2025, 10, 12),
        started_at=datetime(2025, 10, 12, 8, 0, tzinfo=UTC),
        run_type=RunType.RACE,
        run_type_source=RunTypeSource.USER,
        source=DataSource.GARMIN,
        distance_km=42.2,
        duration_seconds=19500,
        avg_pace_seconds_per_km=462.1,
        avg_hr=158,
        start_lat=41.9211,
        start_lng=-87.6340,
        # Privacy-sensitive fields the export must never leak
        raw_payload={"gps_track": [[41.92113, -87.63401]]},
        notes="met Anna at the corner of my street before the start",
        external_id="garmin-123456",
        external_url="https://connect.garmin.com/activity/123456",
        weather_temp_start_c=11.0,
        weather_temp_end_c=14.0,
        weather_temp_max_c=16.0,
        weather_temp_min_c=9.0,
        weather_apparent_temp_max_c=15.0,
        weather_humidity_avg=60.0,
        weather_wind_speed_avg_kmh=12.0,
        weather_precipitation_total_mm=0.0,
    )
    return Run(**defaults | overrides)


# --- exporter: coordinate snapping ---


def test_snap_to_city_maps_by_nearest() -> None:
    assert snap_to_city(38.75, -9.2) == (38.72, -9.14)  # Lisbon suburb
    assert snap_to_city(40.7, -74.01) == (40.78, -73.97)  # lower Manhattan
    assert snap_to_city(41.9211, -87.634) == (41.88, -87.62)  # Chicago north side


# --- exporter: field stripping (privacy-critical) ---


def test_fixture_row_is_whitelist_only() -> None:
    row = to_fixture_row(_block_run())
    # The row's keys are EXACTLY the public surface — nothing extra can leak
    assert set(row) == set(FIXTURE_FIELDS)
    for forbidden in ("raw_payload", "notes", "external_id", "external_url",
                      "id", "user_id", "perceived_effort"):
        assert forbidden not in row


def test_fixture_row_has_no_full_precision_coords() -> None:
    row = to_fixture_row(_block_run(start_lat=41.9211387, start_lng=-87.6340125))
    assert row["start_lat"] == 41.88
    assert row["start_lng"] == -87.62
    serialized = str(row)
    assert "41.9211" not in serialized
    assert "87.6340" not in serialized


def test_fixture_row_content_is_leak_free() -> None:
    run = _block_run()
    serialized = str(to_fixture_row(run))
    assert "Anna" not in serialized  # notes
    assert "garmin-123456" not in serialized  # external id
    assert "gps_track" not in serialized  # raw payload


# --- exporter: fail-loud validation ---


def test_validate_block_flags_unlocated_and_unclassified() -> None:
    runs = [
        _block_run(),
        _block_run(date=date(2025, 9, 20), start_lat=None, start_lng=None),
        _block_run(date=date(2025, 9, 22), run_type_source=RunTypeSource.DEFAULT),
    ]
    errors = validate_block(runs)
    assert len(errors) == 2
    assert any("2025-09-20" in e and "start_lat" in e for e in errors)
    assert any("2025-09-22" in e and "DEFAULT" in e for e in errors)


def test_build_fixture_raises_with_no_output_when_invalid() -> None:
    runs = [_block_run(), _block_run(start_lat=None, start_lng=None)]
    with pytest.raises(ValueError, match="not export-ready"):
        build_fixture(runs)


# --- demo generator ---

_GEN_USER = UUID("00000000-0000-0000-0000-00000000d340")
_GEN_END = date(2026, 7, 23)


def _serialize(dataset) -> str:
    """Canonical byte representation of a generated dataset."""
    runs, samples, daily = dataset
    return json.dumps(
        {
            "runs": [
                [
                    str(r.id), r.date.isoformat(), r.started_at.isoformat(),
                    r.distance_km, r.duration_seconds, r.avg_pace_seconds_per_km,
                    r.avg_hr, r.perceived_effort, r.run_type.value,
                    r.start_lat, r.start_lng,
                    r.weather_temp_start_c, r.weather_humidity_avg,
                    r.glucose_at_start_mg_dl, r.glucose_at_end_mg_dl,
                ]
                for r in runs
            ],
            "samples": [
                [str(s.run_id), s.elapsed_seconds, s.glucose_mg_dl] for s in samples
            ],
            "daily": [[d.date.isoformat(), d.avg_glucose_mg_dl] for d in daily],
        }
    )


def test_generation_is_deterministic() -> None:
    first = _serialize(generate_dataset(_GEN_USER, end=_GEN_END))
    second = _serialize(generate_dataset(_GEN_USER, end=_GEN_END))
    assert first == second  # byte-identical across runs and deploys


def test_every_run_is_located_and_user_classified() -> None:
    runs, _, _ = generate_dataset(_GEN_USER, end=_GEN_END)
    assert 300 <= len(runs) <= 420  # ~350: 4-5 runs/week over ~19 months
    assert all(r.start_lat is not None and r.start_lng is not None for r in runs)
    assert all(r.run_type_source == RunTypeSource.USER for r in runs)
    assert all(r.source == DataSource.MANUAL for r in runs)


def test_fitness_arc_easy_pace_improves_year_over_year() -> None:
    runs, _, _ = generate_dataset(_GEN_USER, end=_GEN_END)

    def avg_easy_pace(year: int, month: int) -> float:
        paces = [
            r.avg_pace_seconds_per_km
            for r in runs
            if r.run_type == RunType.EASY
            and r.date.year == year
            and r.date.month == month
        ]
        assert paces, f"no easy runs in {year}-{month:02d}"
        return sum(paces) / len(paces)

    # Clearly faster, not just noise-faster
    assert avg_easy_pace(2026, 6) < avg_easy_pace(2025, 6) - 5


def test_races_match_the_calendar() -> None:
    runs, _, _ = generate_dataset(_GEN_USER, end=_GEN_END)
    races = [r for r in runs if r.run_type == RunType.RACE]
    assert len(races) == 4
    by_date = {r.date: r for r in races}
    assert set(by_date) == {rd for rd, _, _ in RACES}
    marathon = by_date[date(2025, 10, 12)]
    assert marathon.distance_km == 42.2
    assert (marathon.start_lat, marathon.start_lng) == (
        CITIES["chicago"].lat,
        CITIES["chicago"].lng,
    )


def test_city_assignment_follows_the_residence_timeline() -> None:
    # Spot-check the timeline function itself
    assert city_on(date(2025, 1, 3)) is CITIES["phuket"]
    assert city_on(date(2025, 1, 10)) is CITIES["hanoi"]
    assert city_on(date(2025, 1, 20)) is CITIES["budapest"]
    assert city_on(date(2025, 6, 1)) is CITIES["lisbon"]
    assert city_on(date(2025, 10, 5)) is CITIES["nyc"]
    assert city_on(date(2025, 10, 12)) is CITIES["chicago"]
    assert city_on(date(2025, 11, 20)) is CITIES["sf"]
    assert city_on(date(2026, 2, 1)) is CITIES["lisbon"]
    assert city_on(date(2026, 6, 14)) is CITIES["nyc"]

    # And that every generated run wears its date's city coordinates
    runs, _, _ = generate_dataset(_GEN_USER, end=_GEN_END)
    for r in runs:
        city = city_on(r.date)
        assert (r.start_lat, r.start_lng) == (city.lat, city.lng)


async def test_load_demo_data_is_idempotent(
    session: AsyncSession, isolated_user
) -> None:
    first = await load_demo_data(session, isolated_user.id)
    second = await load_demo_data(session, isolated_user.id)
    assert first == second

    runs = await session.execute(
        select(func.count()).select_from(Run).where(Run.user_id == isolated_user.id)
    )
    assert runs.scalar_one() == first["runs"]
    samples = await session.execute(
        select(func.count())
        .select_from(RunGlucoseSample)
        .join(Run, Run.id == RunGlucoseSample.run_id)
        .where(Run.user_id == isolated_user.id)
    )
    assert samples.scalar_one() == first["glucose_samples"]
    daily = await session.execute(
        select(func.count())
        .select_from(GlucoseDailyRecord)
        .where(GlucoseDailyRecord.user_id == isolated_user.id)
    )
    assert daily.scalar_one() == first["daily_records"]
