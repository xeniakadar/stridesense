from datetime import UTC, date, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
import respx
from httpx import AsyncClient, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import ImportJob, OAuthConnection, SleepRecord
from app.models.enums import DataSource, OAuthProvider
from app.services.oura import OURA_AUTHORIZE_URL, OURA_BASE_URL, OURA_TOKEN_URL

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
TOKEN_RESPONSE = {
    "token_type": "bearer",
    "access_token": "new-access",
    "refresh_token": "new-refresh",
    "expires_in": 86400,
}


@pytest.fixture
def oura_creds(monkeypatch):
    monkeypatch.setattr(get_settings(), "oura_client_id", "test-client")
    monkeypatch.setattr(get_settings(), "oura_client_secret", "test-secret")


async def _add_connection(
    session: AsyncSession, *, expires_in_seconds: int
) -> OAuthConnection:
    connection = OAuthConnection(
        user_id=get_settings().dev_user_id,
        provider=OAuthProvider.OURA,
        access_token_encrypted="stored-access",
        refresh_token_encrypted="stored-refresh",
        token_expires_at=datetime.now(UTC) + timedelta(seconds=expires_in_seconds),
    )
    session.add(connection)
    await session.commit()
    return connection


def _mock_collections() -> None:
    respx.get(f"{OURA_BASE_URL}/daily_sleep").mock(
        side_effect=[
            Response(200, json=DAILY_SLEEP_PAGE_1),
            Response(200, json=DAILY_SLEEP_PAGE_2),
        ]
        * 2  # enough for two syncs of two pages each
    )
    respx.get(f"{OURA_BASE_URL}/sleep").mock(
        return_value=Response(200, json=SLEEP_PERIODS)
    )
    respx.get(f"{OURA_BASE_URL}/daily_readiness").mock(
        return_value=Response(200, json=DAILY_READINESS)
    )


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
    await session.execute(
        delete(OAuthConnection).where(
            OAuthConnection.user_id == get_settings().dev_user_id,
            OAuthConnection.provider == OAuthProvider.OURA,
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
    client: AsyncClient, session: AsyncSession, oura_creds
) -> None:
    # Valid token, so any hit on the (unmocked) token endpoint would error
    _mock_collections()
    await _add_connection(session, expires_in_seconds=3600)

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


@respx.mock
async def test_oura_sync_refreshes_expired_token(
    client: AsyncClient, session: AsyncSession, oura_creds
) -> None:
    _mock_collections()
    token_route = respx.post(OURA_TOKEN_URL).mock(
        return_value=Response(200, json=TOKEN_RESPONSE)
    )
    connection = await _add_connection(session, expires_in_seconds=-60)

    job_ids = []
    try:
        job_ids.append(await _trigger_sync(client))

        assert token_route.called
        grant = parse_qs(token_route.calls.last.request.content.decode())
        assert grant["grant_type"] == ["refresh_token"]
        assert grant["refresh_token"] == ["stored-refresh"]

        await session.refresh(connection)
        assert connection.access_token_encrypted == "new-access"
        assert connection.refresh_token_encrypted == "new-refresh"
        assert connection.token_expires_at > datetime.now(UTC)

        job = await session.get(ImportJob, job_ids[0])
        assert job.status.value == "completed"
        assert len(await _fetch_records(session)) == 2
    finally:
        await _cleanup(session, job_ids)


async def test_oura_sync_without_connection_fails_job(
    client: AsyncClient, session: AsyncSession, oura_creds
) -> None:
    job_ids = []
    try:
        job_ids.append(await _trigger_sync(client))
        job = await session.get(ImportJob, job_ids[0])
        assert job.status.value == "failed"
        assert "authorize" in job.error_message
        assert await _fetch_records(session) == {}
    finally:
        await _cleanup(session, job_ids)


async def test_oura_sync_without_credentials_fails_job(
    client: AsyncClient, session: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(get_settings(), "oura_client_id", "")
    monkeypatch.setattr(get_settings(), "oura_client_secret", "")

    job_ids = []
    try:
        job_ids.append(await _trigger_sync(client))
        job = await session.get(ImportJob, job_ids[0])
        assert job.status.value == "failed"
        assert "credentials" in job.error_message
    finally:
        await _cleanup(session, job_ids)


@respx.mock
async def test_oura_oauth_flow(
    client: AsyncClient, session: AsyncSession, oura_creds
) -> None:
    token_route = respx.post(OURA_TOKEN_URL).mock(
        return_value=Response(200, json=TOKEN_RESPONSE)
    )

    try:
        response = await client.get("/integrations/oura/authorize")
        assert response.status_code == 307
        location = urlparse(response.headers["location"])
        assert response.headers["location"].startswith(OURA_AUTHORIZE_URL)
        query = parse_qs(location.query)
        assert query["client_id"] == ["test-client"]
        assert query["response_type"] == ["code"]
        assert query["scope"] == ["daily"]
        state = query["state"][0]

        # Forged/expired state is rejected
        bad = await client.get(
            "/integrations/oura/callback", params={"code": "c", "state": "forged"}
        )
        assert bad.status_code == 400

        response = await client.get(
            "/integrations/oura/callback", params={"code": "auth-code", "state": state}
        )
        assert response.status_code == 307
        assert response.headers["location"].endswith("connected=oura")

        grant = parse_qs(token_route.calls.last.request.content.decode())
        assert grant["grant_type"] == ["authorization_code"]
        assert grant["code"] == ["auth-code"]

        result = await session.execute(
            select(OAuthConnection).where(
                OAuthConnection.user_id == get_settings().dev_user_id,
                OAuthConnection.provider == OAuthProvider.OURA,
            )
        )
        connection = result.scalar_one()
        assert connection.access_token_encrypted == "new-access"
        assert connection.token_expires_at > datetime.now(UTC)

        # The state is one-time: replaying the callback is rejected
        replay = await client.get(
            "/integrations/oura/callback", params={"code": "c", "state": state}
        )
        assert replay.status_code == 400
    finally:
        await _cleanup(session, [])
