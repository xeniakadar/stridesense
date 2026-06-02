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
