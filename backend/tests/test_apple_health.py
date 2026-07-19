from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GlucoseDailyRecord, ImportJob, Run, RunGlucoseSample, User
from app.models.enums import DataSource
from app.services.apple_health import parse_running_workouts

FIXTURE = Path(__file__).parent / "fixtures" / "apple_health_mini.zip"
TZ = timezone(timedelta(hours=2))

GARMIN_START = datetime(2026, 6, 10, 7, 0, tzinfo=TZ)
NIKE_START = datetime(2026, 6, 11, 7, 0, tzinfo=TZ)
WATCH_START = datetime(2026, 6, 12, 6, 0, tzinfo=TZ)


def test_parse_running_workouts_handles_both_distance_shapes() -> None:
    workouts = parse_running_workouts(FIXTURE)
    # the cycling workout must be filtered out
    assert len(workouts) == 4

    garmin, nike, watch, no_distance = workouts
    assert garmin["source_name"] == "Garmin Connect"
    assert garmin["distance_km"] == 8.0  # WorkoutStatistics variant
    assert garmin["energy_kcal"] == 450.0
    assert garmin["duration_seconds"] == 2400
    assert garmin["started_at"] == GARMIN_START
    # first GPX trkpt, rounded to 2 decimals — never full precision
    assert garmin["start_lat"] == 47.51
    assert garmin["start_lng"] == 19.05

    assert nike["distance_km"] == 5.2  # attribute variant
    assert nike["energy_kcal"] == 300.0
    assert nike["duration_seconds"] == 1800
    # its FileReference points at a file missing from the zip: clean skip
    assert nike["start_lat"] is None
    assert nike["start_lng"] is None

    # no WorkoutRoute at all
    assert watch["start_lat"] is None

    # the parser reports distance-less workouts; the import skips them
    assert no_distance["distance_km"] is None


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
    # 3 runs + 1 glucose sample + 1 daily record; the distance-less
    # workout is counted in the total but skipped (runs need distance > 0)
    assert job.items_imported == 5
    assert job.items_total == 6

    runs = await _fetch_runs(session, isolated_user)
    assert len(runs) == 3

    garmin_run = runs[GARMIN_START.isoformat()]
    assert garmin_run.source == DataSource.GARMIN
    assert garmin_run.distance_km == 8.0
    assert garmin_run.duration_seconds == 2400
    assert garmin_run.avg_pace_seconds_per_km == 300.0
    # windowed HR: 150 and 160 count, the 06:00 reading does not
    assert garmin_run.avg_hr == 155
    assert garmin_run.max_hr == 160
    # start coordinates from the linked GPX route, rounded
    assert garmin_run.start_lat == 47.51
    assert garmin_run.start_lng == 19.05

    nike_run = runs[NIKE_START.isoformat()]
    assert nike_run.source == DataSource.APPLE_HEALTH
    assert nike_run.distance_km == 5.2
    assert nike_run.avg_pace_seconds_per_km == 346.2
    assert nike_run.avg_hr is None
    # missing route file and no route: null coords, home-location fallback
    assert nike_run.start_lat is None
    assert runs[WATCH_START.isoformat()].start_lat is None

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
    garmin_run.start_lat = None
    garmin_run.start_lng = None
    await session.commit()

    job_id = await _upload(client)
    job = await session.get(ImportJob, job_id)
    assert job.status.value == "completed", job.error_message

    runs = await _fetch_runs(session, isolated_user)
    assert len(runs) == 3
    refreshed = runs[GARMIN_START.isoformat()]
    await session.refresh(refreshed)
    assert refreshed.start_lat == 47.51  # upsert restored the coordinates
    assert refreshed.start_lng == 19.05
    result = await session.execute(
        select(RunGlucoseSample).where(RunGlucoseSample.run_id == refreshed.id)
    )
    assert len(result.scalars().all()) == 1
    assert len(await _fetch_dailies(session, isolated_user)) == 1


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
            "Garmin Connect",
            "Nike Run Club",
            "Apple Watch",
        )
