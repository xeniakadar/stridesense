"""Open-Meteo historical weather client and run enrichment."""

from datetime import timedelta
from statistics import mean
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models import ImportJob, Run, RunWeatherSample, User
from app.models.enums import ImportJobStatus
from app.services.ingest import finish_job
from app.services.insights import invalidate_insights

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HOURLY_VARS = (
    "temperature_2m,relative_humidity_2m,apparent_temperature,"
    "precipitation,wind_speed_10m"
)
SAMPLE_INTERVAL_SECONDS = 30 * 60

# Cache of fetched day-payloads within one backfill, keyed by
# (~1km-rounded lat, lng, ISO date). None means "archive had nothing".
FetchCache = dict[tuple[float, float, str], dict | None]


async def fetch_day(lat: float, lng: float, day: str) -> dict:
    """Fetch one day of hourly archive weather.

    Returns the full payload — `hourly` arrays plus `utc_offset_seconds`,
    which enrichment needs to convert UTC run times to local hours
    (`timezone: auto` makes the arrays local to the coordinates).
    """
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            ARCHIVE_URL,
            params={
                "latitude": lat,
                "longitude": lng,
                "start_date": day,
                "end_date": day,
                "hourly": HOURLY_VARS,
                "timezone": "auto",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def _payload_for(
    lat: float, lng: float, day: str, cache: FetchCache
) -> dict | None:
    key = (round(lat, 2), round(lng, 2), day)
    if key not in cache:
        try:
            cache[key] = await fetch_day(lat, lng, day)
        except httpx.HTTPError:
            # Archive lag (recent days 400 or come back empty) or a flaky
            # fetch: treat as unavailable, a later backfill catches it.
            cache[key] = None
    return cache[key]


def compute_weather_summary(samples: list[dict[str, Any]]) -> dict[str, float | None]:
    """The eight denormalized weather_* columns, same shape the seed fakes."""
    temps = [s["temperature_c"] for s in samples if s["temperature_c"] is not None]
    apparents = [
        s["apparent_temperature_c"]
        for s in samples
        if s["apparent_temperature_c"] is not None
    ]
    humidities = [s["humidity"] for s in samples if s["humidity"] is not None]
    winds = [s["wind_speed_kmh"] for s in samples if s["wind_speed_kmh"] is not None]
    precips = [s["precipitation_mm"] for s in samples if s["precipitation_mm"] is not None]

    return {
        "weather_temp_start_c": round(temps[0], 1),
        "weather_temp_end_c": round(temps[-1], 1),
        "weather_temp_max_c": round(max(temps), 1),
        "weather_temp_min_c": round(min(temps), 1),
        "weather_apparent_temp_max_c": round(max(apparents), 1) if apparents else None,
        "weather_humidity_avg": round(mean(humidities), 1) if humidities else None,
        "weather_wind_speed_avg_kmh": round(mean(winds), 1) if winds else None,
        "weather_precipitation_total_mm": round(sum(precips), 1),
    }


async def enrich_run(
    session: AsyncSession, run: Run, lat: float, lng: float, cache: FetchCache
) -> bool:
    """Write 30-minute weather samples for a run, then its summary columns.

    Returns False without writing anything when the archive has no data for
    the run's hours yet (the ~2–5 day lag) — skip, don't fail.
    """
    sample_values: list[dict[str, Any]] = []
    for elapsed in range(0, run.duration_seconds + 1, SAMPLE_INTERVAL_SECONDS):
        observed_at = run.started_at + timedelta(seconds=elapsed)

        payload = await _payload_for(lat, lng, observed_at.date().isoformat(), cache)
        if payload is None:
            return False
        local_dt = observed_at + timedelta(seconds=payload.get("utc_offset_seconds", 0))
        # Near local midnight the local date differs from the UTC date; the
        # hourly arrays cover one local day, so fetch the day being indexed.
        local_day = local_dt.date().isoformat()
        if local_day != observed_at.date().isoformat():
            payload = await _payload_for(lat, lng, local_day, cache)
            if payload is None:
                return False

        hourly = payload["hourly"]
        idx = local_dt.hour
        temperature = hourly["temperature_2m"][idx]
        if temperature is None:
            return False
        sample_values.append(
            {
                "run_id": run.id,
                "elapsed_seconds": elapsed,
                "observed_at": observed_at,
                "temperature_c": temperature,
                "apparent_temperature_c": hourly["apparent_temperature"][idx],
                "humidity": hourly["relative_humidity_2m"][idx],
                "wind_speed_kmh": hourly["wind_speed_10m"][idx],
                "precipitation_mm": hourly["precipitation"][idx],
            }
        )

    for values in sample_values:
        stmt = pg_insert(RunWeatherSample).values(**values)
        update_cols = {
            k: stmt.excluded[k]
            for k in values
            if k not in ("run_id", "elapsed_seconds")
        }
        stmt = stmt.on_conflict_do_update(
            constraint="uq_run_weather_sample", set_=update_cols
        )
        await session.execute(stmt)

    for field, value in compute_weather_summary(sample_values).items():
        setattr(run, field, value)
    await invalidate_insights(session, run.id)
    await session.commit()
    return True


async def backfill_weather(job_id: UUID) -> None:
    """Background task: enrich every run missing weather data.

    Opens its own session — the request's session is closed by the time
    this runs.
    """
    async with AsyncSessionLocal() as session:
        job = await session.get(ImportJob, job_id)
        if job is None:
            return
        try:
            user = await session.get(User, job.user_id)
            result = await session.execute(
                select(Run)
                .where(
                    Run.user_id == job.user_id,
                    Run.weather_temp_start_c.is_(None),
                )
                .order_by(Run.date)
            )
            runs = result.scalars().all()

            cache: FetchCache = {}
            enriched = 0
            for run in runs:
                lat = run.start_lat if run.start_lat is not None else user.home_lat
                lng = run.start_lng if run.start_lng is not None else user.home_lng
                if lat is None or lng is None or run.started_at is None:
                    continue
                if await enrich_run(session, run, lat, lng, cache):
                    enriched += 1

            await finish_job(
                session,
                job,
                status=(
                    ImportJobStatus.COMPLETED
                    if enriched == len(runs)
                    else ImportJobStatus.PARTIAL
                ),
                items_imported=enriched,
                items_total=len(runs),
            )
        except Exception as e:
            await session.rollback()
            await finish_job(session, job, status=ImportJobStatus.FAILED, error=str(e))
