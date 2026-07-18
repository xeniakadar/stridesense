from datetime import date

import pytest
import respx
from httpx import AsyncClient, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import ImportJob, SleepRecord
from app.models.enums import DataSource
from app.services.oura import OURA_BASE_URL

DAY1 = date(2026, 6, 1)
DAY2 = date(2026, 6, 2)

DAILY_SLEEP_PAGE_1 = {
    "data": [{"id": "ds-1", "day": DAY1.isoformat(), "score": 82}],
    "next_token": "tok",
}
DAILY_SLEEP_PAGE_2 = {
    "data": [{"id": "ds-2", "day": DAY2.isoformat(), "score": 70}],
    "next_token": None,
}
SLEEP_PERIODS = {
    "data": [
        {
            "id": "sl-1",
            "day": DAY1.isoformat(),
            "type": "long_sleep",
            "total_sleep_duration": 27000,
            "deep_sleep_duration": 5400,
            "rem_sleep_duration": 3600,
            "lowest_heart_rate": 52,
            "average_hrv": 55,
        },
        # a nap the same day must not overwrite the night's numbers
        {
            "id": "sl-nap",
            "day": DAY1.isoformat(),
            "type": "late_nap",
            "total_sleep_duration": 3600,
            "lowest_heart_rate": 60,
            "average_hrv": 40,
        },
    ],
    "next_token": None,
}
DAILY_READINESS = {
    "data": [
        {
            "id": "rd-1",
            "day": DAY1.isoformat(),
            "score": 75,
            "temperature_deviation": -0.2,
        }
    ],
    "next_token": None,
}


@pytest.fixture
def oura_pat(monkeypatch):
    monkeypatch.setattr(get_settings(), "oura_pat", "test-pat")


async def _fetch_records(session: AsyncSession) -> dict[date, SleepRecord]:
    result = await session.execute(
        select(SleepRecord).where(
            SleepRecord.user_id == get_settings().dev_user_id,
            SleepRecord.source == DataSource.OURA,
            SleepRecord.date.in_([DAY1, DAY2]),
        )
    )
    return {r.date: r for r in result.scalars().all()}


async def _cleanup(session: AsyncSession, job_ids: list[str]) -> None:
    await session.execute(
        delete(SleepRecord).where(
            SleepRecord.user_id == get_settings().dev_user_id,
            SleepRecord.source == DataSource.OURA,
            SleepRecord.date.in_([DAY1, DAY2]),
        )
    )
    await session.execute(delete(ImportJob).where(ImportJob.id.in_(job_ids)))
    await session.commit()


async def _trigger_sync(client: AsyncClient) -> str:
    response = await client.post(
        "/integrations/oura/sync",
        params={"start_date": DAY1.isoformat(), "end_date": DAY2.isoformat()},
    )
    assert response.status_code == 202
    return response.json()["job_id"]


@respx.mock
async def test_oura_sync_maps_fields_and_is_idempotent(
    client: AsyncClient, session: AsyncSession, oura_pat
) -> None:
    respx.get(f"{OURA_BASE_URL}/daily_sleep").mock(
        side_effect=[
            Response(200, json=DAILY_SLEEP_PAGE_1),
            Response(200, json=DAILY_SLEEP_PAGE_2),
        ]
        * 2  # two syncs, two pages each
    )
    respx.get(f"{OURA_BASE_URL}/sleep").mock(
        return_value=Response(200, json=SLEEP_PERIODS)
    )
    respx.get(f"{OURA_BASE_URL}/daily_readiness").mock(
        return_value=Response(200, json=DAILY_READINESS)
    )

    job_ids = []
    try:
        job_ids.append(await _trigger_sync(client))

        records = await _fetch_records(session)
        assert set(records) == {DAY1, DAY2}
        night = records[DAY1]
        assert night.sleep_quality == 82
        assert night.sleep_hours == 7.5
        assert night.deep_sleep_hours == 1.5
        assert night.rem_sleep_hours == 1.0
        assert night.resting_hr == 52
        assert night.hrv == 55
        assert night.body_temperature_deviation_c == -0.2
        assert set(night.raw_payload) == {"daily_sleep", "sleep", "daily_readiness"}
        # day 2 was on the second page — proves pagination is followed
        assert records[DAY2].sleep_quality == 70
        assert records[DAY2].sleep_hours is None

        job = await session.get(ImportJob, job_ids[0])
        assert job.status.value == "completed"
        assert job.items_imported == 2

        # Re-sync: upsert refreshes, never duplicates
        job_ids.append(await _trigger_sync(client))
        records = await _fetch_records(session)
        assert len(records) == 2
        assert records[DAY1].sleep_hours == 7.5
    finally:
        await _cleanup(session, job_ids)


async def test_oura_sync_without_pat_fails_job_not_request(
    client: AsyncClient, session: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(get_settings(), "oura_pat", "")

    job_ids = []
    try:
        job_ids.append(await _trigger_sync(client))
        job = await session.get(ImportJob, job_ids[0])
        assert job.status.value == "failed"
        assert "OURA_PAT" in job.error_message
        assert await _fetch_records(session) == {}
    finally:
        await _cleanup(session, job_ids)
