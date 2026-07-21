"""Pre-generate and cache an insight for every run — the demo-mode deploy step.

Demo mode never generates insights on demand (the GET endpoint serves cached
rows only), so a demo deployment runs this once after seeding data, e.g.:

    docker compose exec backend uv run python -m scripts.embed_runs --apply
    docker compose exec backend uv run python -m scripts.pregenerate_insights
    docker compose exec backend uv run python -m scripts.pregenerate_ask_answers

Runs that already have a cached insight are skipped, so re-running is cheap
and resumes cleanly after an interruption. Commits after every run so
progress survives a crash. One LLM call per uncached run — expect it to
take a while on a full dataset.
"""

import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import Insight
from app.services import list_runs
from app.services.insights import (
    INSIGHT_MODEL,
    InsightUnavailableError,
    generate_insight,
)
from app.services.similarity import find_similar_runs
from app.services.training_load import acwr_for_run


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
            print("Nothing to do.")
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


if __name__ == "__main__":
    asyncio.run(main())
