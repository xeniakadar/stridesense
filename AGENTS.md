# StrideSense — working conventions

## Project

Contextual running-analytics app. FastAPI + Postgres + SQLAlchemy/Alembic
backend; Next.js 15 + TypeScript frontend. Runs in Docker Compose.
Core design principle: deterministic models compute the numbers (cosine
similarity, ACWR); the LLM only narrates them over a grounded context
block it cannot deviate from.

## Workflow — follow strictly

- One branch per change, off up-to-date main. Never commit to main.
- Conventional commits: feat:, fix:, chore:, test:, docs:, refactor:.
- For multi-file or schema changes, briefly state your plan, then proceed
  without waiting — narrate decisions as you go. Single-file edits: just do them.
- After edits: run `docker compose exec backend uv run ruff check .` and
  the relevant tests before telling me it's done.

## Backend

- ruff with B008 ignored (FastAPI Depends pattern); imports sorted (I001).
- Pydantic run-CRUD schemas in app/schemas/run.py; analytics/insight
  shapes in app/schemas/analytics.py.
- New model? Register in app/models/**init**.py BEFORE autogenerate.
  Always read a generated migration before applying it.
- Tests: mock at the lookup site (app.api.X.func, not app.services...).
  Suite must pass with credentials blanked.
- Schema changes touch four layers in order: model → migration →
  Pydantic → TS types. Keep them in sync.
- Postgres enum values are stored UPPERCASE (e.g. source = 'OURA', 'GARMIN') — match case in raw SQL.

## Frontend

- API client methods go inside the `api` object in lib/api.ts.
- Recharts tooltip formatters: narrow with Number(value), never annotate
  the param as number.

## Mode for Phase 3

- Shipping mode: implement fully, but narrate the key decisions as you go
  so I can explain the code later. Still: plan before multi-file edits,
  run ruff + relevant tests before declaring done, never touch main.
- Commit your own work on the feature branch with conventional-commit
  messages; leave pushing and PR creation to me.
