from datetime import UTC, date, datetime
from uuid import uuid4

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
from scripts.seed_demo import load_demo_block


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


# --- coordinate snapping ---


def test_snap_to_city_maps_by_nearest() -> None:
    assert snap_to_city(38.75, -9.2) == (38.72, -9.14)  # Lisbon suburb
    assert snap_to_city(40.7, -74.01) == (40.78, -73.97)  # lower Manhattan
    assert snap_to_city(41.9211, -87.634) == (41.88, -87.62)  # Chicago north side


# --- field stripping (privacy-critical) ---


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


# --- fail-loud validation ---


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


def test_build_fixture_sorts_by_date() -> None:
    runs = [
        _block_run(date=date(2025, 10, 12)),
        _block_run(date=date(2025, 9, 16)),
    ]
    rows = build_fixture(runs)
    assert [r["date"] for r in rows] == ["2025-09-16", "2025-10-12"]


# --- demo seed idempotence ---

_FIXTURE_ROWS = [
    {
        "date": "2025-10-12",
        "started_at": "2025-10-12T08:00:00+00:00",
        "distance_km": 42.2,
        "duration_seconds": 19500,
        "avg_pace_seconds_per_km": 462.1,
        "avg_hr": 158,
        "run_type": "race",
        "start_lat": 41.88,
        "start_lng": -87.62,
        "weather_temp_start_c": 11.0,
        "weather_temp_end_c": 14.0,
        "weather_temp_max_c": 16.0,
        "weather_temp_min_c": 9.0,
        "weather_apparent_temp_max_c": 15.0,
        "weather_humidity_avg": 60.0,
        "weather_wind_speed_avg_kmh": 12.0,
        "weather_precipitation_total_mm": 0.0,
    },
    {
        "date": "2025-10-14",
        "started_at": "2025-10-14T07:30:00+00:00",
        "distance_km": 5.0,
        "duration_seconds": 2100,
        "avg_pace_seconds_per_km": 420.0,
        "avg_hr": 130,
        "run_type": "recovery",
        "start_lat": 41.88,
        "start_lng": -87.62,
        "weather_temp_start_c": 12.0,
        "weather_temp_end_c": 13.0,
        "weather_temp_max_c": 15.0,
        "weather_temp_min_c": 8.0,
        "weather_apparent_temp_max_c": 14.0,
        "weather_humidity_avg": 55.0,
        "weather_wind_speed_avg_kmh": 10.0,
        "weather_precipitation_total_mm": 0.0,
    },
]


async def _counts(session: AsyncSession, user_id) -> dict[str, int]:
    runs = await session.execute(
        select(func.count()).select_from(Run).where(Run.user_id == user_id)
    )
    samples = await session.execute(
        select(func.count())
        .select_from(RunGlucoseSample)
        .join(Run, Run.id == RunGlucoseSample.run_id)
        .where(Run.user_id == user_id)
    )
    daily = await session.execute(
        select(func.count())
        .select_from(GlucoseDailyRecord)
        .where(GlucoseDailyRecord.user_id == user_id)
    )
    return {
        "runs": runs.scalar_one(),
        "samples": samples.scalar_one(),
        "daily": daily.scalar_one(),
    }


async def test_seed_demo_is_idempotent(session: AsyncSession, isolated_user) -> None:
    first = await load_demo_block(session, isolated_user.id, _FIXTURE_ROWS)
    counts_after_first = await _counts(session, isolated_user.id)

    second = await load_demo_block(session, isolated_user.id, _FIXTURE_ROWS)
    counts_after_second = await _counts(session, isolated_user.id)

    assert first["runs"] == second["runs"] == 2
    assert counts_after_first == counts_after_second
    # One daily record per calendar day across the block span (Oct 12-14)
    assert counts_after_first["daily"] == 3
    assert counts_after_first["samples"] > 0


async def test_seed_demo_tags_everything_manual_with_glucose_summaries(
    session: AsyncSession, isolated_user
) -> None:
    await load_demo_block(session, isolated_user.id, _FIXTURE_ROWS)

    runs = (
        (await session.execute(select(Run).where(Run.user_id == isolated_user.id)))
        .scalars()
        .all()
    )
    assert all(r.source == DataSource.MANUAL for r in runs)
    assert all(r.glucose_at_start_mg_dl is not None for r in runs)

    samples = (
        (
            await session.execute(
                select(RunGlucoseSample)
                .join(Run, Run.id == RunGlucoseSample.run_id)
                .where(Run.user_id == isolated_user.id)
            )
        )
        .scalars()
        .all()
    )
    assert samples and all(s.source == DataSource.MANUAL for s in samples)
