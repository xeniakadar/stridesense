from contextlib import contextmanager
from datetime import date
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import AskDemoAnswer, Insight

# Every module that reads demo_mode looks up get_settings in its own
# namespace — patch all three lookup sites at once.
_DEMO_SITES = (
    "app.main.get_settings",       # read-only middleware + /config
    "app.api.runs.get_settings",   # insight GET
    "app.api.ask.get_settings",    # /ask + /ask/demo-questions
)


@contextmanager
def demo_mode():
    demo_settings = get_settings().model_copy(update={"demo_mode": True})
    with (
        patch(_DEMO_SITES[0], return_value=demo_settings),
        patch(_DEMO_SITES[1], return_value=demo_settings),
        patch(_DEMO_SITES[2], return_value=demo_settings),
    ):
        yield


def _run_payload(run_date: date) -> dict:
    return {
        "date": run_date.isoformat(),
        "run_type": "easy",
        "distance_km": 8.0,
        "duration_seconds": 2700,
    }


@pytest_asyncio.fixture
async def canned_answer(session: AsyncSession):
    """A stored demo Q&A row, cleaned up afterwards (shared dev database)."""
    row = AskDemoAnswer(
        question="How do I handle running in hot weather?",
        answer="Your run on 2026-06-14 shows you slow down about 20s/km in heat.",
        model="claude-sonnet-4-6",
        cited_runs=[
            {
                "run_id": str(uuid4()),
                "date": "2026-06-14",
                "run_type": "easy",
                "distance_km": 8.0,
                "score": 0.87,
            }
        ],
    )
    session.add(row)
    await session.commit()
    yield row
    await session.execute(delete(AskDemoAnswer).where(AskDemoAnswer.id == row.id))
    await session.commit()


async def test_config_endpoint(client: AsyncClient) -> None:
    res = await client.get("/config")
    assert res.status_code == 200
    assert res.json() == {"demo_mode": False}

    with demo_mode():
        res = await client.get("/config")
    assert res.json() == {"demo_mode": True}


async def test_mutating_requests_403_in_demo(
    client: AsyncClient, isolated_user
) -> None:
    with demo_mode():
        for method, path in [
            ("POST", "/runs"),
            ("PUT", f"/runs/{uuid4()}"),
            ("DELETE", f"/runs/{uuid4()}"),
            ("POST", f"/runs/{uuid4()}/insight/regenerate"),
            ("POST", "/integrations/oura/sync"),
        ]:
            res = await client.request(
                method, path, json={} if method in {"POST", "PUT"} else None
            )
            assert res.status_code == 403, f"{method} {path}"
            assert res.json() == {"detail": "Demo is read-only"}

        # Reads still work
        res = await client.get("/runs")
        assert res.status_code == 200


async def test_insight_get_serves_cache_never_generates(
    client: AsyncClient, session: AsyncSession, isolated_user
) -> None:
    created = (await client.post("/runs", json=_run_payload(date(2026, 6, 1)))).json()
    session.add(
        Insight(run_id=created["id"], content="cached narration", model="claude-sonnet-4-6")
    )
    await session.commit()

    with (
        demo_mode(),
        patch("app.api.runs.generate_insight", new=AsyncMock()) as mock_generate,
    ):
        res = await client.get(f"/runs/{created['id']}/insight")

    assert res.status_code == 200
    assert res.json()["content"] == "cached narration"
    assert mock_generate.await_count == 0


async def test_insight_get_uncached_demo_returns_friendly_message(
    client: AsyncClient, isolated_user
) -> None:
    created = (await client.post("/runs", json=_run_payload(date(2026, 6, 2)))).json()

    with (
        demo_mode(),
        patch("app.api.runs.generate_insight", new=AsyncMock()) as mock_generate,
    ):
        res = await client.get(f"/runs/{created['id']}/insight")

    assert res.status_code == 200
    body = res.json()
    assert "pre-generated" in body["content"]
    assert body["model"] == "demo"
    assert mock_generate.await_count == 0


async def test_ask_demo_serves_canned_answer_verbatim(
    client: AsyncClient, isolated_user, canned_answer
) -> None:
    with (
        demo_mode(),
        patch("app.api.ask.retrieve", new=AsyncMock()) as mock_retrieve,
        patch("app.api.ask.generate_answer", new=AsyncMock()) as mock_generate,
    ):
        res = await client.post("/ask", json={"question": canned_answer.question})

    assert res.status_code == 200
    body = res.json()
    assert body["answer"] == canned_answer.answer
    assert body["model"] == canned_answer.model
    assert body["cited_runs"] == canned_answer.cited_runs
    # Neither retrieval nor generation runs in demo mode
    assert mock_retrieve.await_count == 0
    assert mock_generate.await_count == 0


async def test_ask_demo_unknown_question_403(
    client: AsyncClient, isolated_user, canned_answer
) -> None:
    with demo_mode():
        res = await client.post("/ask", json={"question": "something else entirely"})
    assert res.status_code == 403
    assert "example questions" in res.json()["detail"]


async def test_demo_questions_endpoint(
    client: AsyncClient, canned_answer
) -> None:
    # Outside demo mode the list is empty regardless of stored rows
    res = await client.get("/ask/demo-questions")
    assert res.status_code == 200
    assert res.json() == []

    with demo_mode():
        res = await client.get("/ask/demo-questions")
    assert canned_answer.question in res.json()
