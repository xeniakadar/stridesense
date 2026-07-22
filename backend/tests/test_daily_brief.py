from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import DailyBrief
from app.services.daily_brief import (
    DAILY_BRIEF_MODEL,
    DailyBriefData,
    build_daily_context,
    invalidate_daily_briefs,
)


def _run_payload(run_date: date, **overrides) -> dict:
    return {
        "date": run_date.isoformat(),
        "run_type": "easy",
        "distance_km": 8.0,
        "duration_seconds": 2700,
        "perceived_effort": 4,
    } | overrides


# --- context assembly (pure) ---


def test_build_daily_context_full_data() -> None:
    data = DailyBriefData(
        sleep_score=82,
        sleep_score_avg=76.5,
        readiness_score=79,
        acwr=1.1,
        zone="optimal",
        days_since_hard_run=3,
    )
    context = build_daily_context(data, date(2026, 7, 22))
    assert "sleep" in context.lower()
    assert "82" in context and "76.5" in context
    assert "Readiness" in context and "79" in context
    assert "1.1" in context and "optimal" in context
    assert "3 day(s) ago" in context


def test_build_daily_context_omits_missing_sections() -> None:
    data = DailyBriefData(
        sleep_score=None,
        sleep_score_avg=None,
        readiness_score=None,
        acwr=1.4,
        zone="caution",
        days_since_hard_run=None,
    )
    context = build_daily_context(data, date(2026, 7, 22))
    assert "sleep" not in context.lower()
    assert "Readiness" not in context
    assert "hard run" not in context.lower()
    assert "Training load" in context and "1.4" in context


# --- endpoint, mocked at the lookup site ---


async def test_daily_brief_generates_once_and_caches(
    client: AsyncClient, isolated_user
) -> None:
    await client.post("/runs", json=_run_payload(date.today()))

    with patch(
        "app.api.daily_brief.generate_daily_brief",
        new=AsyncMock(return_value="An easy day would cost you nothing."),
    ) as mock_generate:
        first = await client.get("/daily-brief")
        assert first.status_code == 200
        assert first.json()["content"] == "An easy day would cost you nothing."
        assert first.json()["model"] == DAILY_BRIEF_MODEL

        second = await client.get("/daily-brief")
        assert second.status_code == 200
        assert second.json()["content"] == first.json()["content"]
        assert mock_generate.await_count == 1  # cached — one generation per day


async def test_daily_brief_without_sleep_is_load_only(
    client: AsyncClient, isolated_user
) -> None:
    # Runs exist (so load data is present) but no sleep records at all
    await client.post("/runs", json=_run_payload(date.today()))
    await client.post("/runs", json=_run_payload(date.today() - timedelta(days=3)))

    with patch(
        "app.api.daily_brief.generate_daily_brief",
        new=AsyncMock(return_value="Load looks steady."),
    ) as mock_generate:
        res = await client.get("/daily-brief")

    assert res.status_code == 200
    data = mock_generate.await_args.args[0]
    assert data.sleep_score is None
    assert data.readiness_score is None
    assert data.acwr is not None  # load section is the only content
    context = build_daily_context(data, date.today())
    assert "sleep" not in context.lower()
    assert "Training load" in context


async def test_daily_brief_no_data_answers_without_llm(
    client: AsyncClient, isolated_user
) -> None:
    with patch(
        "app.api.daily_brief.generate_daily_brief", new=AsyncMock()
    ) as mock_generate:
        res = await client.get("/daily-brief")

    assert res.status_code == 200
    assert res.json()["model"] is None
    assert mock_generate.await_count == 0


async def test_daily_brief_unavailable_returns_503(
    client: AsyncClient, isolated_user
) -> None:
    from app.services.insights import InsightUnavailableError

    await client.post("/runs", json=_run_payload(date.today()))

    with patch(
        "app.api.daily_brief.generate_daily_brief",
        new=AsyncMock(side_effect=InsightUnavailableError("no key")),
    ):
        res = await client.get("/daily-brief")
    assert res.status_code == 503


async def test_daily_brief_demo_serves_pregenerated_never_generates(
    client: AsyncClient, session: AsyncSession, isolated_user
) -> None:
    # A pre-generated brief from "yesterday" — demo serves it even though
    # its date has slipped
    session.add(
        DailyBrief(
            user_id=isolated_user.id,
            date=date.today() - timedelta(days=1),
            content="Pre-generated demo brief.",
            model=DAILY_BRIEF_MODEL,
        )
    )
    await session.commit()

    demo_settings = get_settings().model_copy(update={"demo_mode": True})
    with (
        patch("app.api.daily_brief.get_settings", return_value=demo_settings),
        patch(
            "app.api.daily_brief.generate_daily_brief", new=AsyncMock()
        ) as mock_generate,
    ):
        res = await client.get("/daily-brief")

    assert res.status_code == 200
    assert res.json()["content"] == "Pre-generated demo brief."
    assert mock_generate.await_count == 0


async def test_daily_brief_demo_without_rows_is_friendly(
    client: AsyncClient, isolated_user
) -> None:
    demo_settings = get_settings().model_copy(update={"demo_mode": True})
    with (
        patch("app.api.daily_brief.get_settings", return_value=demo_settings),
        patch(
            "app.api.daily_brief.generate_daily_brief", new=AsyncMock()
        ) as mock_generate,
    ):
        res = await client.get("/daily-brief")

    assert res.status_code == 200
    assert res.json()["model"] == "demo"
    assert "pre-generated" in res.json()["content"]
    assert mock_generate.await_count == 0


# --- invalidation (the Oura-sync hook calls this) ---


async def test_invalidate_daily_briefs_deletes_matching_dates(
    session: AsyncSession, isolated_user
) -> None:
    today = date.today()
    session.add_all(
        [
            DailyBrief(
                user_id=isolated_user.id,
                date=today,
                content="stale",
                model=DAILY_BRIEF_MODEL,
            ),
            DailyBrief(
                user_id=isolated_user.id,
                date=today - timedelta(days=1),
                content="untouched",
                model=DAILY_BRIEF_MODEL,
            ),
        ]
    )
    await session.commit()

    await invalidate_daily_briefs(session, isolated_user.id, [today])
    await session.commit()

    remaining = await session.execute(
        select(DailyBrief.content).where(DailyBrief.user_id == isolated_user.id)
    )
    assert list(remaining.scalars().all()) == ["untouched"]
