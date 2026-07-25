# StrideSense

> Contextual running performance analysis. Explains _why_ a run felt the way it did by combining workout, recovery, weather, and training data.

**Status:** in development (Phase 0 — foundations)

## Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Postgres 16, Redis 7
- **Frontend:** Next.js 15 (App Router), TypeScript, Tailwind CSS
- **Infrastructure:** Docker Compose

## Getting started

Requires Docker Desktop. From the repo root:

```bash
cp .env.example .env
docker compose up --build
docker compose exec backend uv run alembic upgrade head
```

Then open `http://localhost:3000`. You should see two green health checks.

After importing runs (Oura sync, Apple Health upload, weather backfill) or
re-classifying them (`scripts/classify_runs.py`), refresh the ask-your-history
embeddings — the script hashes each run's rendered sentence, so it re-embeds
only runs whose data actually changed:

```bash
docker compose exec backend uv run python -m scripts.embed_runs          # dry run
docker compose exec backend uv run python -m scripts.embed_runs --apply
```

## Demo deployment

A demo deployment (DEMO_MODE=true) seeds a deterministic synthetic dataset
— ~350 runs since Jan 2025 with a residence timeline (Phuket → Hanoi →
Budapest → Lisbon → NYC → Chicago → SF → Lisbon → NYC), per-city climate,
four races, and a scripted fitness arc — then pre-generates everything the
read-only UI serves. Run in order:

```bash
docker compose exec backend uv run python -m scripts.seed_demo
docker compose exec backend uv run python -m scripts.embed_runs --apply
docker compose exec backend uv run python -m scripts.pregenerate_insights
docker compose exec backend uv run python -m scripts.pregenerate_ask_answers
```

Everything in the demo dataset is synthetic and tagged `manual`; the UI
captions glucose as simulated. (`scripts/export_demo_block.py` still exists
for exporting a privacy-scrubbed block of real runs, but is no longer part
of the demo path.)

Note: the AI-output format (single-bold emphasis rules in the brief,
insight, and ask prompts) and the demo data (synthetic nightly
sleep_records feeding the daily brief) both changed in July 2026. The
deploy pipeline's seed → embed → pregenerate sequence above regenerates
everything correctly on its own. Locally, reseed and re-pregenerate
(`seed_demo`, then `pregenerate_insights` / `pregenerate_ask_answers`)
to see briefs, insights, and answers in the new format with sleep data.

## Repo layout

```
.
├── backend/        FastAPI API + SQLAlchemy models + Alembic migrations
├── frontend/       Next.js app
├── docker/         Shared Docker config
├── docs/           Architecture, decisions, case study notes
└── docker-compose.yml
```

## Roadmap

See `docs/roadmap.md`. Currently working on Phase 0 (foundations).

## License

MIT
