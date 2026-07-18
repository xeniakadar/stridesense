"""Oura v2 API client (personal access token) and recovery import.

Note: Oura API v2 exposes no cycle endpoint (checked against spec 1.35),
so this import fills sleep_records only; cycle_records waits for a source.
"""

from datetime import date
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import ImportJob
from app.models.enums import DataSource, ImportJobStatus
from app.services.ingest import finish_job, upsert_sleep_record

OURA_BASE_URL = "https://api.ouraring.com/v2/usercollection"


async def _fetch_collection(
    client: httpx.AsyncClient, path: str, start_date: date, end_date: date
) -> list[dict]:
    """Fetch every document of one collection, following next_token pages."""
    docs: list[dict] = []
    next_token: str | None = None
    while True:
        params: dict[str, str] = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
        if next_token:
            params["next_token"] = next_token
        resp = await client.get(f"{OURA_BASE_URL}/{path}", params=params)
        resp.raise_for_status()
        payload = resp.json()
        docs.extend(payload["data"])
        next_token = payload.get("next_token")
        if not next_token:
            return docs


def _hours(seconds: int | None) -> float | None:
    return round(seconds / 3600, 2) if seconds is not None else None


def merge_oura_days(
    user_id: UUID,
    daily_sleep: list[dict],
    sleep_periods: list[dict],
    readiness: list[dict],
) -> list[dict[str, Any]]:
    """Merge the three collections into one sleep_records row per day.

    daily_sleep carries only the 0–100 score; durations/HR/HRV live in the
    detailed sleep periods; temperature deviation lives in daily readiness.
    """
    by_day: dict[str, dict[str, Any]] = {}

    def record(day: str) -> dict[str, Any]:
        return by_day.setdefault(
            day,
            {
                "user_id": user_id,
                "source": DataSource.OURA,
                "date": date.fromisoformat(day),
                "raw_payload": {},
            },
        )

    for doc in daily_sleep:
        rec = record(doc["day"])
        rec["sleep_quality"] = doc.get("score")
        rec.setdefault("external_id", doc.get("id"))
        rec["raw_payload"]["daily_sleep"] = doc

    for doc in sleep_periods:
        # Naps and rests also appear here; the night's sleep is long_sleep.
        # If a night is split into several periods, keep the longest.
        if doc.get("type") != "long_sleep":
            continue
        rec = record(doc["day"])
        kept = rec["raw_payload"].get("sleep")
        if kept and (kept.get("total_sleep_duration") or 0) >= (
            doc.get("total_sleep_duration") or 0
        ):
            continue
        rec["raw_payload"]["sleep"] = doc
        rec["sleep_hours"] = _hours(doc.get("total_sleep_duration"))
        rec["deep_sleep_hours"] = _hours(doc.get("deep_sleep_duration"))
        rec["rem_sleep_hours"] = _hours(doc.get("rem_sleep_duration"))
        # Oura's reported resting heart rate is the night's lowest
        rec["resting_hr"] = doc.get("lowest_heart_rate")
        rec["hrv"] = doc.get("average_hrv")
        rec.setdefault("external_id", doc.get("id"))

    for doc in readiness:
        rec = record(doc["day"])
        rec["body_temperature_deviation_c"] = doc.get("temperature_deviation")
        rec.setdefault("external_id", doc.get("id"))
        rec["raw_payload"]["daily_readiness"] = doc

    return [by_day[day] for day in sorted(by_day)]


async def sync_oura(job_id: UUID, start_date: date, end_date: date) -> None:
    """Background task: import Oura sleep/readiness into sleep_records.

    Opens its own session — the request's session is closed by the time
    this runs.
    """
    async with AsyncSessionLocal() as session:
        job = await session.get(ImportJob, job_id)
        if job is None:
            return
        try:
            pat = get_settings().oura_pat
            if not pat:
                await finish_job(
                    session,
                    job,
                    status=ImportJobStatus.FAILED,
                    error="OURA_PAT is not configured",
                )
                return

            async with httpx.AsyncClient(
                timeout=20, headers={"Authorization": f"Bearer {pat}"}
            ) as client:
                daily_sleep = await _fetch_collection(
                    client, "daily_sleep", start_date, end_date
                )
                sleep_periods = await _fetch_collection(
                    client, "sleep", start_date, end_date
                )
                readiness = await _fetch_collection(
                    client, "daily_readiness", start_date, end_date
                )

            records = merge_oura_days(job.user_id, daily_sleep, sleep_periods, readiness)
            await _upsert_all(session, records)
            await finish_job(
                session,
                job,
                status=ImportJobStatus.COMPLETED,
                items_imported=len(records),
                items_total=len(records),
            )
        except Exception as e:
            await session.rollback()
            await finish_job(session, job, status=ImportJobStatus.FAILED, error=str(e))


async def _upsert_all(session: AsyncSession, records: list[dict[str, Any]]) -> None:
    for values in records:
        await upsert_sleep_record(session, values)
    await session.commit()
