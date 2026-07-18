"""Oura v2 API client (OAuth2) and recovery import.

Oura deprecated personal access tokens in Dec 2025; new integrations
authenticate via the OAuth2 authorization-code flow (authorize/token URLs
per API spec 1.35).

Note: Oura API v2 exposes no cycle endpoint (checked against spec 1.35),
so this import fills sleep_records only; cycle_records waits for a source.
"""

import secrets
import time
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import ImportJob, OAuthConnection
from app.models.enums import DataSource, ImportJobStatus, OAuthProvider
from app.services.ingest import finish_job, upsert_sleep_record

OURA_BASE_URL = "https://api.ouraring.com/v2/usercollection"
OURA_AUTHORIZE_URL = "https://cloud.ouraring.com/oauth/authorize"
OURA_TOKEN_URL = "https://api.ouraring.com/oauth/token"
OURA_REDIRECT_URI = "http://localhost:8000/integrations/oura/callback"
OURA_SCOPE = "daily"
TOKEN_REFRESH_LEEWAY_SECONDS = 60
STATE_TTL_SECONDS = 600

# Issued OAuth states awaiting the callback. In-process is enough for a
# single-user dev server; a multi-process deployment would need Redis.
_pending_states: dict[str, float] = {}


class OuraNotConnectedError(Exception):
    pass


def build_authorize_url() -> str:
    params = urlencode(
        {
            "client_id": get_settings().oura_client_id,
            "redirect_uri": OURA_REDIRECT_URI,
            "response_type": "code",
            "scope": OURA_SCOPE,
            "state": issue_oauth_state(),
        }
    )
    return f"{OURA_AUTHORIZE_URL}?{params}"


def issue_oauth_state() -> str:
    now = time.monotonic()
    for state, issued in list(_pending_states.items()):
        if now - issued > STATE_TTL_SECONDS:
            del _pending_states[state]
    state = secrets.token_urlsafe(24)
    _pending_states[state] = now
    return state


def consume_oauth_state(state: str) -> bool:
    """One-time check that a callback state was issued by us and is fresh."""
    issued = _pending_states.pop(state, None)
    return issued is not None and time.monotonic() - issued <= STATE_TTL_SECONDS


async def _token_request(grant: dict[str, str]) -> dict:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            OURA_TOKEN_URL,
            data={
                **grant,
                "client_id": settings.oura_client_id,
                "client_secret": settings.oura_client_secret,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def _get_connection(
    session: AsyncSession, user_id: UUID
) -> OAuthConnection | None:
    result = await session.execute(
        select(OAuthConnection).where(
            OAuthConnection.user_id == user_id,
            OAuthConnection.provider == OAuthProvider.OURA,
        )
    )
    return result.scalar_one_or_none()


def _apply_tokens(connection: OAuthConnection, tokens: dict) -> None:
    connection.access_token_encrypted = tokens["access_token"]
    # Refresh responses may rotate the refresh token; keep the old one if not
    if tokens.get("refresh_token"):
        connection.refresh_token_encrypted = tokens["refresh_token"]
    connection.token_expires_at = datetime.now(UTC) + timedelta(
        seconds=tokens.get("expires_in", 0)
    )
    if tokens.get("scope"):
        connection.scope = tokens["scope"]


async def exchange_oura_code(session: AsyncSession, user_id: UUID, code: str) -> None:
    """Exchange the callback code for tokens and upsert the connection."""
    tokens = await _token_request(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": OURA_REDIRECT_URI,
        }
    )
    connection = await _get_connection(session, user_id)
    if connection is None:
        connection = OAuthConnection(
            user_id=user_id,
            provider=OAuthProvider.OURA,
            access_token_encrypted=tokens["access_token"],
        )
        session.add(connection)
    _apply_tokens(connection, tokens)
    await session.commit()


async def get_valid_oura_token(session: AsyncSession, user_id: UUID) -> str:
    """Return a usable access token, refreshing it first if near expiry."""
    connection = await _get_connection(session, user_id)
    if connection is None:
        raise OuraNotConnectedError(
            "Oura is not connected — visit /integrations/oura/authorize"
        )
    expires_at = connection.token_expires_at
    if expires_at is not None and expires_at <= datetime.now(UTC) + timedelta(
        seconds=TOKEN_REFRESH_LEEWAY_SECONDS
    ):
        if not connection.refresh_token_encrypted:
            raise OuraNotConnectedError(
                "Oura token expired and no refresh token is stored — reauthorize"
            )
        tokens = await _token_request(
            {
                "grant_type": "refresh_token",
                "refresh_token": connection.refresh_token_encrypted,
            }
        )
        _apply_tokens(connection, tokens)
        await session.commit()
    return connection.access_token_encrypted


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
            settings = get_settings()
            if not settings.oura_client_id or not settings.oura_client_secret:
                await finish_job(
                    session,
                    job,
                    status=ImportJobStatus.FAILED,
                    error="Oura client credentials are not configured",
                )
                return
            try:
                token = await get_valid_oura_token(session, job.user_id)
            except OuraNotConnectedError as e:
                await finish_job(
                    session, job, status=ImportJobStatus.FAILED, error=str(e)
                )
                return

            async with httpx.AsyncClient(
                timeout=20, headers={"Authorization": f"Bearer {token}"}
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
