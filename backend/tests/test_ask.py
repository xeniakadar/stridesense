from datetime import date
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Run
from app.services.ask import ASK_MODEL, retrieve
from app.services.insights import InsightUnavailableError


def _run_payload(run_date: date, **overrides) -> dict:
    return {
        "date": run_date.isoformat(),
        "run_type": "easy",
        "distance_km": 8.0,
        "duration_seconds": 2700,
    } | overrides


def _vec(*head: float) -> list[float]:
    """A 384-dim vector with the given leading components, zero-padded."""
    return list(head) + [0.0] * (384 - len(head))


# --- retrieve(): real pgvector query, mocked at the embedding boundary ---


async def test_retrieve_ranks_by_cosine_and_skips_unembedded(
    client: AsyncClient, session: AsyncSession, isolated_user
) -> None:
    ids = {}
    for key, day in [("best", 1), ("worse", 2), ("unembedded", 3)]:
        created = (
            await client.post("/runs", json=_run_payload(date(2026, 6, day)))
        ).json()
        ids[key] = created["id"]

    # Question will embed to e0; "best" is aligned with it, "worse" only partly
    result = await session.execute(select(Run).where(Run.id.in_(list(ids.values()))))
    runs = {str(r.id): r for r in result.scalars().all()}
    runs[ids["best"]].embedding = _vec(1.0)
    runs[ids["worse"]].embedding = _vec(0.6, 0.8)
    await session.commit()

    with patch("app.services.ask.embed", return_value=[_vec(1.0)]) as mock_embed:
        ranked = await retrieve(session, isolated_user.id, "hot weather runs", k=5)
        # Only the question is embedded at request time
        mock_embed.assert_called_once_with(["hot weather runs"])

    assert [str(r.id) for r, _ in ranked] == [ids["best"], ids["worse"]]
    scores = [score for _, score in ranked]
    assert scores[0] > scores[1]
    assert abs(scores[0] - 1.0) < 1e-6
    assert abs(scores[1] - 0.6) < 1e-6


async def test_retrieve_respects_k(
    client: AsyncClient, session: AsyncSession, isolated_user
) -> None:
    for day in range(1, 4):
        await client.post("/runs", json=_run_payload(date(2026, 6, day)))
    result = await session.execute(select(Run).where(Run.user_id == isolated_user.id))
    for i, run in enumerate(result.scalars().all()):
        run.embedding = _vec(1.0, float(i))
    await session.commit()

    with patch("app.services.ask.embed", return_value=[_vec(1.0)]):
        ranked = await retrieve(session, isolated_user.id, "anything", k=2)
    assert len(ranked) == 2


# --- POST /ask: mocked at the lookup site (app.api.ask.*) ---


def _fake_run(day: int) -> Run:
    from app.models.enums import RunType

    return Run(
        id=uuid4(),
        date=date(2026, 6, day),
        run_type=RunType.EASY,
        distance_km=8.0,
        duration_seconds=2700,
    )


async def test_ask_endpoint_answers_with_citations(
    client: AsyncClient, isolated_user
) -> None:
    run = _fake_run(14)
    with (
        patch(
            "app.api.ask.retrieve", new=AsyncMock(return_value=[(run, 0.87)])
        ) as mock_retrieve,
        patch(
            "app.api.ask.generate_answer",
            new=AsyncMock(return_value="Your run on 2026-06-14 was in hot weather."),
        ) as mock_generate,
    ):
        res = await client.post("/ask", json={"question": "how about hot weather?"})

    assert res.status_code == 200
    body = res.json()
    assert body["answer"] == "Your run on 2026-06-14 was in hot weather."
    assert body["model"] == ASK_MODEL
    assert body["cited_runs"] == [
        {
            "run_id": str(run.id),
            "date": "2026-06-14",
            "run_type": "easy",
            "distance_km": 8.0,
            "score": 0.87,
            "city": None,
        }
    ]
    assert mock_retrieve.await_count == 1
    assert mock_generate.await_count == 1


async def test_ask_endpoint_rejects_empty_question(
    client: AsyncClient, isolated_user
) -> None:
    with patch("app.api.ask.retrieve", new=AsyncMock()) as mock_retrieve:
        res = await client.post("/ask", json={"question": "   "})
    assert res.status_code == 400
    assert mock_retrieve.await_count == 0


async def test_ask_endpoint_no_embedded_runs(
    client: AsyncClient, isolated_user
) -> None:
    with (
        patch("app.api.ask.retrieve", new=AsyncMock(return_value=[])),
        patch("app.api.ask.generate_answer", new=AsyncMock()) as mock_generate,
    ):
        res = await client.post("/ask", json={"question": "anything?"})

    assert res.status_code == 200
    body = res.json()
    assert body["model"] is None
    assert body["cited_runs"] == []
    assert "embed" in body["answer"]
    assert mock_generate.await_count == 0  # no LLM call without context


async def test_ask_endpoint_unavailable_returns_503(
    client: AsyncClient, isolated_user
) -> None:
    with (
        patch(
            "app.api.ask.retrieve",
            new=AsyncMock(return_value=[(_fake_run(1), 0.5)]),
        ),
        patch(
            "app.api.ask.generate_answer",
            new=AsyncMock(side_effect=InsightUnavailableError("no key")),
        ),
    ):
        res = await client.post("/ask", json={"question": "why so slow?"})
    assert res.status_code == 503


async def test_ask_endpoint_demo_mode_returns_403(
    client: AsyncClient, isolated_user
) -> None:
    demo_settings = get_settings().model_copy(update={"demo_mode": True})
    with (
        patch("app.api.ask.get_settings", return_value=demo_settings),
        patch("app.api.ask.retrieve", new=AsyncMock()) as mock_retrieve,
    ):
        res = await client.post("/ask", json={"question": "hi"})

    assert res.status_code == 403
    assert "demo" in res.json()["detail"].lower()
    assert mock_retrieve.await_count == 0
