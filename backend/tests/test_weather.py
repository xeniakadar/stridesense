from datetime import UTC, date, datetime

import respx
from httpx import AsyncClient, Response
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import ImportJob, Run, RunWeatherSample
from app.models.enums import DataSource, RunType, RunTypeSource
from app.services.weather import ARCHIVE_URL

# Local time = UTC + 2h; temperature_2m[hour] == hour makes indexing checkable.
OPEN_METEO_PAYLOAD = {
    "utc_offset_seconds": 7200,
    "hourly": {
        "temperature_2m": [float(h) for h in range(24)],
        "apparent_temperature": [float(h) - 1.0 for h in range(24)],
        "relative_humidity_2m": [50.0] * 24,
        "wind_speed_10m": [10.0] * 24,
        "precipitation": [0.1] * 24,
    },
}


def _make_run(**overrides) -> Run:
    values = {
        "user_id": get_settings().dev_user_id,
        "source": DataSource.MANUAL,
        "date": date(2026, 6, 15),
        # 07:00 UTC = 09:00 local; 60 min -> samples at local hours 9, 9, 10
        "started_at": datetime(2026, 6, 15, 7, 0, tzinfo=UTC),
        "distance_km": 10.0,
        "duration_seconds": 3600,
        "run_type": RunType.EASY,
        "run_type_source": RunTypeSource.USER,
        "start_lat": 47.50,
        "start_lng": 19.05,
    }
    return Run(**(values | overrides))


async def _cleanup(session: AsyncSession, run: Run, job_ids: list[str]) -> None:
    await session.execute(delete(Run).where(Run.id == run.id))
    await session.execute(delete(ImportJob).where(ImportJob.id.in_(job_ids)))
    await session.commit()


async def _sample_count(session: AsyncSession, run: Run) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(RunWeatherSample)
        .where(RunWeatherSample.run_id == run.id)
    )
    return result.scalar_one()


@respx.mock
async def test_weather_backfill_enriches_and_is_idempotent(
    client: AsyncClient, session: AsyncSession
) -> None:
    respx.get(ARCHIVE_URL).mock(return_value=Response(200, json=OPEN_METEO_PAYLOAD))

    run = _make_run()
    session.add(run)
    await session.commit()

    job_ids = []
    try:
        response = await client.post("/integrations/weather/backfill")
        assert response.status_code == 202
        job_ids.append(response.json()["job_id"])

        # ASGITransport awaits background tasks before returning
        await session.refresh(run)
        assert run.weather_temp_start_c == 9.0
        assert run.weather_temp_end_c == 10.0
        assert run.weather_temp_max_c == 10.0
        assert run.weather_temp_min_c == 9.0
        assert run.weather_apparent_temp_max_c == 9.0
        assert run.weather_humidity_avg == 50.0
        assert run.weather_wind_speed_avg_kmh == 10.0
        assert run.weather_precipitation_total_mm == 0.3
        assert await _sample_count(session, run) == 3

        # Re-run: samples upsert, no duplicates
        response = await client.post("/integrations/weather/backfill")
        assert response.status_code == 202
        job_ids.append(response.json()["job_id"])
        assert await _sample_count(session, run) == 3

        job = await session.get(ImportJob, job_ids[0])
        assert job.source == DataSource.OPEN_METEO
        assert job.finished_at is not None
    finally:
        await _cleanup(session, run, job_ids)


@respx.mock
async def test_weather_backfill_skips_runs_archive_cannot_serve(
    client: AsyncClient, session: AsyncSession
) -> None:
    # The archive 400s for too-recent dates — the run must be skipped,
    # left unenriched, and the job must not fail.
    respx.get(ARCHIVE_URL).mock(return_value=Response(400, json={"error": True}))

    run = _make_run()
    session.add(run)
    await session.commit()

    job_ids = []
    try:
        response = await client.post("/integrations/weather/backfill")
        assert response.status_code == 202
        job_ids.append(response.json()["job_id"])

        await session.refresh(run)
        assert run.weather_temp_start_c is None
        assert await _sample_count(session, run) == 0

        job = await session.get(ImportJob, job_ids[0])
        assert job.status.value == "partial"
        assert job.error_message is None
    finally:
        await _cleanup(session, run, job_ids)
