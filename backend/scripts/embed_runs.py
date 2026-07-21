"""Compute and store retrieval embeddings for runs (ask-your-history RAG).

For every run of the dev user, renders run_to_text(run) and compares its
sha256 (sentence_hash) against runs.embedding_text_hash. Runs whose stored
hash is missing or different get (re-)embedded with all-MiniLM-L6-v2 and
written back to runs.embedding; up-to-date runs are skipped. That hash
comparison IS the invalidation mechanism: anything that changes a run's
sentence — a re-import overwriting distance/pace, classify_runs.py --apply
changing run_type, weather backfill filling in temperature — makes the
stored hash stale, and the next pass of this script re-embeds exactly those
runs. No per-code-path hooks needed; just run this script after imports,
classification, or weather backfills:

    docker compose exec backend uv run python -m scripts.embed_runs
    docker compose exec backend uv run python -m scripts.embed_runs --apply

Dry run by default — prints how many runs would be embedded and why.
"""

import asyncio
import sys

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import Run
from app.services.ask import embed, run_to_text, sentence_hash


async def main() -> None:
    apply_changes = "--apply" in sys.argv
    user_id = get_settings().dev_user_id

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Run).where(Run.user_id == user_id))
        all_runs = list(result.scalars().all())

        new: list[tuple[Run, str, str]] = []      # never embedded
        stale: list[tuple[Run, str, str]] = []    # sentence changed since last embed
        for run in all_runs:
            text = run_to_text(run)
            digest = sentence_hash(text)
            if run.embedding_text_hash is None:
                new.append((run, text, digest))
            elif run.embedding_text_hash != digest:
                stale.append((run, text, digest))

        plan = new + stale
        print(
            f"{len(all_runs)} total runs: {len(new)} never embedded, "
            f"{len(stale)} stale (sentence changed), "
            f"{len(all_runs) - len(plan)} up to date"
        )
        if not plan:
            print("Nothing to do.")
            return

        if not apply_changes:
            for run, text, _ in plan[:5]:
                print(f"  {run.date.isoformat()}  {text}")
            if len(plan) > 5:
                print(f"  ... and {len(plan) - 5} more")
            print("\nDry run — nothing written. Re-run with --apply to execute.")
            return

        # One batched encode; the model loads once inside embed()
        vectors = embed([text for _, text, _ in plan])
        for (run, _, digest), vector in zip(plan, vectors, strict=True):
            run.embedding = vector
            run.embedding_text_hash = digest
        await session.commit()
        print(f"\nApplied: {len(plan)} runs embedded.")


if __name__ == "__main__":
    asyncio.run(main())
