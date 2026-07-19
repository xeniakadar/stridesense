from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GlucoseDailyRecord, ImportJob, Run, RunGlucoseSample, User
from app.models.enums import DataSource
from app.services.apple_health import _workout_source, parse_running_workouts

FIXTURE = Path(__file__).parent / "fixtures" / "apple_health_mini.zip"
TZ = timezone(timedelta(hours=2))

GARMIN_START = datetime(2026, 6, 10, 7, 0, tzinfo=TZ)
OURA_DUP_START = datetime(2026, 6, 10, 7, 45, tzinfo=TZ)
NIKE_START = datetime(2026, 6, 11, 7, 0, tzinfo=TZ)
WATCH_START = datetime(2026, 6, 12, 6, 0, tzinfo=TZ)
OURA_START = datetime(2026, 6, 15, 6, 0, tzinfo=TZ)


def test_workout_source_maps_real_export_names() -> None:
    assert _workout_source("Connect") == DataSource.GARMIN
    assert _workout_source("Strava") == DataSource.STRAVA
    assert _workout_source("Oura") == DataSource.OURA
    assert _workout_source("Nike Run Club") == DataSource.APPLE_HEALTH
    assert _workout_source("5K Runner") == DataSource.APPLE_HEALTH
    assert _workout_source("Xenia’s Apple Watch") == DataSource.APPLE_HEALTH


def test_parse_running_workouts_handles_both_distance_shapes() -> None:
    workouts = parse_running_workouts(FIXTURE)
    # the cycling workout must be filtered out
    assert len(workouts) == 7

    garmin, oura_dup, nike, watch, no_distance, zero_distance, oura = workouts
    assert garmin["source_name"] == "Connect"
    assert garmin["distance_km"] == 8.0  # WorkoutStatistics variant
    assert garmin["energy_kcal"] == 450.0
    assert garmin["duration_seconds"] == 2400
    assert garmin["started_at"] == GARMIN_START
    # real Garmin workouts carry no WorkoutRoute
    assert garmin["start_lat"] is None

    assert nike["distance_km"] == 5.2  # attribute variant
    assert nike["energy_kcal"] == 300.0
    assert nike["duration_seconds"] == 1800
    # its FileReference points at a file missing from the zip: clean skip
    assert nike["start_lat"] is None
    assert nike["start_lng"] is None

    # first GPX trkpt, rounded to 2 decimals — never full precision
    assert watch["start_lat"] == 47.51
    assert watch["start_lng"] == 19.05

    # the parser reports these faithfully; the import skips both
    assert no_distance["distance_km"] is None
    assert zero_distance["distance_km"] == 0.0

    # the parser reports Oura workouts faithfully; the import dedupes
    assert oura_dup["started_at"] == OURA_DUP_START
    assert oura["started_at"] == OURA_START


async def _upload(client: AsyncClient) -> str:
    response = await client.post(
        "/integrations/apple-health/upload",
        files={"file": ("export.zip", FIXTURE.read_bytes(), "application/zip")},
    )
    assert response.status_code == 202
    return response.json()["job_id"]


async def _fetch_runs(session: AsyncSession, user: User) -> dict[str, Run]:
    result = await session.execute(select(Run).where(Run.user_id == user.id))
    return {r.external_id: r for r in result.scalars().all()}


async def _fetch_dailies(
    session: AsyncSession, user: User
) -> list[GlucoseDailyRecord]:
    result = await session.execute(
        select(GlucoseDailyRecord).where(GlucoseDailyRecord.user_id == user.id)
    )
    return list(result.scalars().all())


async def test_apple_health_import_end_to_end(
    client: AsyncClient, session: AsyncSession, isolated_user
) -> None:
    job_id = await _upload(client)

    job = await session.get(ImportJob, job_id)
    assert job.status.value == "completed", job.error_message
    # 4 runs + 1 glucose sample + 1 daily record; two distance-less
    # workouts skipped and one Oura auto-detect deduped
    assert job.items_imported == 6
    assert job.items_total == 9
    assert job.items_skipped_duplicates == 1

    runs = await _fetch_runs(session, isolated_user)
    assert len(runs) == 4

    garmin_run = runs[GARMIN_START.isoformat()]
    assert garmin_run.source == DataSource.GARMIN
    assert garmin_run.distance_km == 8.0
    assert garmin_run.duration_seconds == 2400
    assert garmin_run.avg_pace_seconds_per_km == 300.0
    # same-source HR only: Connect's 150/160 count; the Oura ring's
    # 120/130 in the same window and the 06:00 reading do not
    assert garmin_run.avg_hr == 155
    assert garmin_run.max_hr == 160
    assert garmin_run.start_lat is None  # Garmin workouts carry no route

    nike_run = runs[NIKE_START.isoformat()]
    assert nike_run.source == DataSource.APPLE_HEALTH
    assert nike_run.distance_km == 5.2
    assert nike_run.avg_pace_seconds_per_km == 346.2
    assert nike_run.avg_hr is None
    # missing route file: null coords, home-location fallback
    assert nike_run.start_lat is None

    # start coordinates from the linked GPX route, rounded
    watch_run = runs[WATCH_START.isoformat()]
    assert watch_run.start_lat == 47.51
    assert watch_run.start_lng == 19.05

    # The Oura auto-detect overlapping the Garmin run was NOT imported…
    assert OURA_DUP_START.isoformat() not in runs
    # …but the standalone Oura workout was, with OURA provenance
    oura_run = runs[OURA_START.isoformat()]
    assert oura_run.source == DataSource.OURA
    assert oura_run.distance_km == 6.0

    # Glucose: one Linx mmol/L reading in the Garmin window
    result = await session.execute(
        select(RunGlucoseSample).where(RunGlucoseSample.run_id == garmin_run.id)
    )
    samples = result.scalars().all()
    assert len(samples) == 1
    sample = samples[0]
    assert sample.glucose_mg_dl == 95.5  # 5.3 mmol/L converted
    assert sample.source == DataSource.LINX_CGM
    assert sample.elapsed_seconds == 873  # 07:14:33 - 07:00:00

    assert garmin_run.glucose_at_start_mg_dl == 95.5
    assert garmin_run.glucose_time_in_range_pct_during_run == 100.0
    assert garmin_run.glucose_pre_run_60min_avg_mg_dl is None

    # A glucose-free workout imports cleanly with no summary
    assert nike_run.glucose_at_start_mg_dl is None

    # Daily record covers in- and out-of-window readings (95.5, 108.1)
    dailies = await _fetch_dailies(session, isolated_user)
    assert len(dailies) == 1
    daily = dailies[0]
    assert daily.source == DataSource.LINX_CGM
    assert daily.date == date(2026, 6, 10)
    assert daily.avg_glucose_mg_dl == 101.8
    assert daily.min_glucose_mg_dl == 95.5
    assert daily.max_glucose_mg_dl == 108.1
    assert daily.glucose_variability_cv == 8.8
    assert daily.gmi == 5.75
    assert daily.time_in_range_pct == 100.0
    assert daily.overnight_avg_glucose_mg_dl is None

    # Re-import must UPDATE existing rows: blank the coords, then re-upload
    watch_run.start_lat = None
    watch_run.start_lng = None
    await session.commit()

    job_id = await _upload(client)
    job = await session.get(ImportJob, job_id)
    assert job.status.value == "completed", job.error_message

    runs = await _fetch_runs(session, isolated_user)
    assert len(runs) == 4
    refreshed = runs[WATCH_START.isoformat()]
    await session.refresh(refreshed)
    assert refreshed.start_lat == 47.51  # upsert restored the coordinates
    assert refreshed.start_lng == 19.05
    result = await session.execute(
        select(RunGlucoseSample).where(
            RunGlucoseSample.run_id == runs[GARMIN_START.isoformat()].id
        )
    )
    assert len(result.scalars().all()) == 1
    assert len(await _fetch_dailies(session, isolated_user)) == 1


async def test_reupload_heals_existing_zero_distance_runs(
    client: AsyncClient, session: AsyncSession, isolated_user
) -> None:
    # A database already poisoned by a pre-fix import must come clean
    bad_run = Run(
        user_id=isolated_user.id,
        date=date(2025, 9, 23),
        external_id="bad-zero-distance",
        distance_km=0.0,
        duration_seconds=1920,
    )
    session.add(bad_run)
    await session.commit()

    job_id = await _upload(client)
    job = await session.get(ImportJob, job_id)
    assert job.status.value == "completed", job.error_message

    result = await session.execute(
        select(Run).where(
            Run.user_id == isolated_user.id, Run.distance_km <= 0
        )
    )
    assert result.scalars().all() == []


async def test_upload_job_records_source_and_type(
    client: AsyncClient, session: AsyncSession, isolated_user
) -> None:
    job_id = await _upload(client)
    job = await session.get(ImportJob, job_id)
    assert job.source == DataSource.APPLE_HEALTH
    assert job.job_type.value == "file_upload"
    assert job.started_at is not None
    assert job.finished_at is not None


# imported_at must be set on imported runs (used by UI source badges later)
async def test_imported_runs_carry_import_metadata(
    client: AsyncClient, session: AsyncSession, isolated_user
) -> None:
    await _upload(client)
    runs = await _fetch_runs(session, isolated_user)
    for run in runs.values():
        assert run.imported_at is not None
        assert run.imported_at <= datetime.now(UTC)
        assert run.run_type.value == "other"
        assert run.run_type_source.value == "default"
        assert run.raw_payload["sourceName"] in (
            "Connect",
            "Nike Run Club",
            "Xenia’s Apple Watch",
            "Oura",
        )
