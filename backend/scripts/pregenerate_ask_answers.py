"""Pre-generate the curated ask-your-history answers served in demo mode.

Demo mode disables free-form /ask; instead the UI offers these questions as
chips and the endpoint serves the stored answers verbatim. Run once at
deploy time, after seeding and after `scripts.embed_runs --apply` (retrieval
reads the stored run embeddings):

    docker compose exec backend uv run python -m scripts.pregenerate_ask_answers

Questions already stored are skipped, so re-running only fills gaps. To
change the set, edit QUESTIONS below and delete the stale rows from
ask_demo_answers first.
"""

import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import AskDemoAnswer
from app.services.ask import ASK_MODEL, generate_answer, retrieve
from app.services.insights import InsightUnavailableError

# The curated demo set — shown as tappable chips in the AskSection.
QUESTIONS = [
    "How do I handle running in hot weather?",
    "What do my long runs look like?",
    "Have I gotten faster on my easy runs?",
    "How do my runs in Lisbon compare to elsewhere?",
]


async def main() -> None:
    user_id = get_settings().dev_user_id

    async with AsyncSessionLocal() as session:
        existing = await session.execute(select(AskDemoAnswer.question))
        stored = set(existing.scalars().all())

        targets = [q for q in QUESTIONS if q not in stored]
        print(f"{len(QUESTIONS)} questions, {len(stored)} stored, {len(targets)} to generate")
        if not targets:
            print("Nothing to do.")
            return

        for i, question in enumerate(targets, start=1):
            retrieved = await retrieve(session, user_id, question, k=5)
            if not retrieved:
                print(f"[{i}/{len(targets)}] SKIP (no embedded runs): {question}")
                continue
            try:
                answer = await generate_answer(question, retrieved)
            except InsightUnavailableError as e:
                print(f"\nAborting at {question!r}: {e}")
                print("Progress so far is saved; re-run to resume.")
                return
            session.add(
                AskDemoAnswer(
                    question=question,
                    answer=answer,
                    model=ASK_MODEL,
                    cited_runs=[
                        {
                            "run_id": str(run.id),
                            "date": run.date.isoformat(),
                            "run_type": run.run_type.value,
                            "distance_km": run.distance_km,
                            "score": round(score, 3),
                        }
                        for run, score in retrieved
                    ],
                )
            )
            await session.commit()
            print(f"[{i}/{len(targets)}] {question}")

        print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
