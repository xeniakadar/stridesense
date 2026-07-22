"""Pre-generate and cache an insight per run plus today's daily brief.

Demo mode never generates on demand (the insight GET serves cached rows
only; /daily-brief serves the newest pre-generated brief), so a demo
deployment runs this once after seeding data, e.g.:

    docker compose exec backend uv run python -m scripts.embed_runs --apply
    docker compose exec backend uv run python -m scripts.pregenerate_insights
    docker compose exec backend uv run python -m scripts.pregenerate_ask_answers

Runs that already have a cached insight are skipped, so re-running is cheap
and resumes cleanly after an interruption. Commits after every run so
progress survives a crash. One LLM call per uncached run — expect it to
take a while on a full dataset.
"""

import asyncio
from datetime import date

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import DailyBrief, Insight
from app.services import list_runs
from app.services.daily_brief import (
    DAILY_BRIEF_MODEL,
    gather_daily_data,
    generate_daily_brief,
)
from app.services.insights import (
    INSIGHT_MODEL,
    InsightUnavailableError,
    generate_insight,
)
from app.services.similarity import find_similar_runs
from app.services.training_load import acwr_for_run


async def pregenerate_daily_brief(session, user_id) -> None:
    """Today's brief, so the demo has one to serve (skips if it exists)."""
    today = date.today()
    existing = await session.execute(
        select(DailyBrief).where(
            DailyBrief.user_id == user_id, DailyBrief.date == today
        )
    )
    if existing.scalar_one_or_none():
        print("Daily brief for today already cached.")
        return
    data = await gather_daily_data(session, user_id, today)
    if not data.has_anything():
        print("No data for a daily brief — skipped.")
        return
    content = await generate_daily_brief(data, today)
    session.add(
        DailyBrief(
            user_id=user_id, date=today, content=content, model=DAILY_BRIEF_MODEL
        )
    )
    await session.commit()
    print("Daily brief generated and cached.")


async def main() -> None:
    user_id = get_settings().dev_user_id

    async with AsyncSessionLocal() as session:
        runs = await list_runs(session, user_id, limit=10_000)
        cached = await session.execute(select(Insight.run_id))
        cached_ids = set(cached.scalars().all())

        targets = [r for r in runs if r.id not in cached_ids]
        print(
            f"{len(runs)} runs, {len(runs) - len(targets)} already cached, "
            f"{len(targets)} to generate"
        )
        if not targets:
            print("All insights already cached.")
            await pregenerate_daily_brief(session, user_id)
            return

        for i, run in enumerate(targets, start=1):
            similar = find_similar_runs(run, runs, limit=5)
            load = acwr_for_run(run, runs)
            try:
                content = await generate_insight(run, similar, load)
            except InsightUnavailableError as e:
                print(f"\nAborting at {run.date.isoformat()}: {e}")
                print(f"Progress so far is saved ({i - 1} generated); re-run to resume.")
                return
            session.add(Insight(run_id=run.id, content=content, model=INSIGHT_MODEL))
            await session.commit()
            print(f"[{i}/{len(targets)}] {run.date.isoformat()} {run.run_type.value}")

        print(f"\nDone: {len(targets)} insights generated and cached.")
        await pregenerate_daily_brief(session, user_id)


if __name__ == "__main__":
    asyncio.run(main())
