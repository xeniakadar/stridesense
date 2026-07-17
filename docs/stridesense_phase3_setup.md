# StrideSense — Phase 3 Setup Guide
## Real Data: Strava, Oura, Open-Meteo, and Apple Health

Phase 2 made StrideSense intelligent over seeded data. Phase 3 makes it real: live integrations feeding actual runs, actual recovery, actual weather, and — the distinctive one — your actual Linx CGM glucose via the Apple Health export path. Because the insight engine reasons over whatever context is present, it gets richer automatically as real data flows in. No changes to the insight logic; just more populated fields in the context block. That's the payoff of the grounded, source-agnostic design.

**What makes this phase different from 0–2:** until now, every bug was yours. From here, you're integrating with systems you don't control — OAuth token lifecycles, rate limits, undocumented quirks, exports measured in hundreds of megabytes, timestamps in mixed timezones. The engineering discipline shifts from "build it right" to "build it *defensively*": every import idempotent, every failure recoverable, every external call mockable.

**Lessons carried forward from the Phase 2 revisions** (these are load-bearing in this phase, not reminders):

- Optional dependencies fail at the point of use, not at startup — every integration credential gets an empty default.
- External services fail soft — imports record failure in `import_jobs`, they don't 500.
- Patch where the name is looked up; prove mocks fire by running the suite with credentials blanked.
- New columns/models: register → autogenerate → **read the migration** → apply.
- One PR, one integration.

---

## Scope

In scope:
- Seed-data guard (protect real data from the reseed wipe)
- Ingestion foundations: idempotent upserts, import-job tracking, background execution
- Open-Meteo weather enrichment (no auth — the warm-up integration)
- Strava OAuth + activity import (the flagship OAuth flow)
- Oura via personal access token (sleep / readiness / cycle)
- Apple Health XML import (glucose focus — your Linx data)
- Connections UI, import status, per-run source badges
- Tests with all external calls mocked

Explicitly out of scope:
- **Garmin** — consumer API is enterprise-gated; Garmin data arrives via Strava or Apple Health anyway
- **Strava webhooks** — real-time push sync; manual/scheduled pull is enough for one user. Phase 4+.
- **Multi-user auth** — OAuth here connects *data sources* to the dev user; it is not user login. Real auth is a different project.
- **Token encryption at rest** — tokens live in Postgres plaintext for dev; noted as a production-hardening item, not built now.
- **Apple Health workout import** — Strava covers runs; this phase imports *glucose* from Apple Health. Workouts from a second source would need the canonical-selection layer, which is deferred until there's a real conflict to resolve.

---

## Step 0 — Prerequisites and the seed guard

### 0a. Confirm Phase 2 is healthy

```bash
cd ~/Desktop/stridesense
docker compose up -d
docker compose exec backend uv run pytest
docker compose exec backend uv run ruff check .
```

### 0b. The seed guard — do this before importing anything real

The seed script's idempotent reset **deletes every run belonging to the dev user**. That was a feature while all data was fake. The moment real Strava activities or real glucose lands in your database, an absent-minded `seed` becomes a data-loss event — your imports are re-fetchable, but re-importing a 300 MB Apple Health export because of a reflex command is a bad afternoon.

Add a guard to `scripts/seed.py`: refuse to run when non-manual data exists, unless explicitly forced.

Near the top of `seed()`, after the session opens and before any deletes:

```python
        # Guard: refuse to wipe real imported data
        imported = await session.execute(
            select(Run).where(
                Run.user_id == dev_user_id,
                Run.source != DataSource.MANUAL,
            ).limit(1)
        )
        if imported.scalar_one_or_none() is not None and "--force" not in sys.argv:
            print(
                "Refusing to reseed: imported (non-manual) runs exist.\n"
                "Re-run with --force to wipe ALL data including imports."
            )
            return
```

Add `import sys` to the imports. Verify the guard by running `seed` (should still work — all current data is manual), then remember it exists: after your first Strava import, plain `seed` will refuse.

**Why source-based rather than a count or a flag file:** the `source` column *is* the ground truth for "did this come from an integration." The guard reads the same signal everything else in the system reads. No extra state to maintain or forget.

### 0c. Home location for the dev user

Weather enrichment needs coordinates. Strava runs carry their own start lat/lng; manual and seeded runs don't. The fallback is a home location on the user.

Add two columns to the `User` model (`app/models/user.py`):

```python
    home_lat: Mapped[float | None] = mapped_column(Float)
    home_lng: Mapped[float | None] = mapped_column(Float)
```

(Check `Float` is imported in that file.) The model is already registered in `__init__.py` — this is a column add, not a new model. Autogenerate, **read the migration** (it should be two `add_column` calls on `users` and nothing else), apply:

```bash
docker compose exec backend uv run alembic revision --autogenerate -m "add home location to users"
# read the file
docker compose exec backend uv run alembic upgrade head
```

Set your location (Budapest, roughly — adjust to your actual area at whatever precision you're comfortable committing to a dev database):

```bash
docker compose exec postgres psql -U stridesense -d stridesense -c "
UPDATE users SET home_lat = 47.50, home_lng = 19.05
WHERE id = '00000000-0000-0000-0000-000000000001';
"
```

### Git

Branch `feat/seed-guard-and-home-location`, one commit each for the guard and the migration, PR, merge.

---

## Step 1 — Ingestion foundations

Three patterns every integration in this phase reuses. Build them once, properly.

### 1a. Idempotent upsert

Every import will run more than once — retries, re-syncs, overlapping date windows. Naive inserts crash on the second run (your `uq_runs_source_external` constraint fires); naive "check then insert" has race conditions. The right tool is Postgres's native upsert, which SQLAlchemy exposes as `on_conflict_do_update`.

Create `app/services/ingest.py`:

```python
"""Shared ingestion utilities: idempotent upserts and import-job tracking."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ImportJob, Run


async def upsert_run(session: AsyncSession, values: dict[str, Any]) -> None:
    """Insert a run, or update it if (user_id, source, external_id) exists.

    Idempotent by design: re-importing the same activity refreshes its data
    instead of crashing or duplicating."""
    stmt = pg_insert(Run).values(**values)
    update_cols = {
        k: stmt.excluded[k]
        for k in values
        if k not in ("id", "user_id", "source", "external_id")
    }
    stmt = stmt.on_conflict_do_update(
        constraint="uq_runs_source_external",
        set_=update_cols,
    )
    await session.execute(stmt)
```

**Why upsert-update rather than upsert-ignore:** sources revise their data. Strava recalculates distances; a re-synced activity should refresh the stored row, not be skipped because "we already have it." The conflict keys (`user_id`, `source`, `external_id`) never change; everything else follows the source.

### 1b. Import-job tracking

The `import_jobs` table has existed since Phase 0, unused. Now it earns its keep: every import creates a job row, transitions it through `pending → running → completed/failed`, and records counts and errors. This is what the UI polls, and what you read when an import dies at 2am.

Add to `app/services/ingest.py`:

```python
async def start_job(
    session: AsyncSession, user_id: UUID, source: str, job_type: str
) -> ImportJob:
    job = ImportJob(
        user_id=user_id,
        source=source,
        job_type=job_type,
        status="running",
        started_at=datetime.now(UTC),
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def finish_job(
    session: AsyncSession,
    job: ImportJob,
    *,
    status: str,
    records_processed: int = 0,
    error: str | None = None,
) -> None:
    job.status = status
    job.records_processed = records_processed
    job.error_message = error
    job.finished_at = datetime.now(UTC)
    await session.commit()
```

(Match the field names to your actual `ImportJob` model from Phase 0 — open `app/models/import_job.py` and align. If it lacks `records_processed` / `error_message` / timestamps, add them via a read-before-apply migration.)

### 1c. Background execution

Imports take seconds (Strava) to minutes (Apple Health). They cannot run inside a request handler. Full job-queue infrastructure (ARQ/Celery on the Redis that's been idling since Phase 0) is the production answer — and overkill for one user. The pragmatic middle: FastAPI's `BackgroundTasks` for the orchestration, with one crucial addition for the CPU-heavy XML parse: `asyncio.to_thread`, so parsing doesn't block the event loop that's serving your other requests.

The pattern every import endpoint will follow:

```python
@router.post("/sync", status_code=202)
async def trigger_sync(background_tasks: BackgroundTasks, ...):
    job = await start_job(...)
    background_tasks.add_task(run_the_import, job.id, ...)
    return {"job_id": str(job.id)}   # 202 Accepted: "working on it, poll the job"
```

**One sharp edge to respect:** the background task outlives the request, so it must NOT use the request's database session (which closes when the response returns). Every background import function opens its own session via `AsyncSessionLocal()`. Getting this wrong produces "session is closed" errors that look mystifying until you know the rule.

Plus a job-status endpoint for the UI to poll:

```python
@router.get("/jobs", response_model=list[ImportJobRead])
async def list_jobs(...):
    # recent jobs for the user, newest first
```

(`ImportJobRead` goes in `app/schemas/analytics.py`'s sibling — create `app/schemas/integrations.py` for this phase's shapes, imports complete from the first line.)

### Git

Branch `feat/ingestion-foundations`, commit `feat(ingest): add idempotent upsert and import job tracking`, PR, merge.

---

## Step 2 — Weather enrichment via Open-Meteo

The warm-up integration, chosen first deliberately: **no auth, no tokens, no rate-limit anxiety** — pure "call an API, map the response, write rows." It establishes the enrichment pattern the other integrations reuse, against the friendliest possible API.

### The design (from Phase 0, now implemented)

Three layers: per-run samples in `run_weather_samples` (one row per 30-minute mark, per the original sampling decision), denormalized summary on `runs` (the eight `weather_*` columns), and the `weather_observations` cache table (skip for now — one user doesn't re-fetch the same hour enough to matter; note it as an optimization).

Location resolution: run's own `start_lat/lng` if present (Strava runs will have it), else the user's home location, else skip with a note in the job.

### The client

Create `app/services/weather.py`:

```python
"""Open-Meteo historical weather client and run enrichment."""

from datetime import timedelta

import httpx

from app.models import Run, RunWeatherSample, User

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HOURLY_VARS = (
    "temperature_2m,relative_humidity_2m,apparent_temperature,"
    "precipitation,wind_speed_10m"
)
SAMPLE_INTERVAL_SECONDS = 30 * 60


async def fetch_hourly(lat: float, lng: float, day: str) -> dict:
    """Fetch one day of hourly weather. Returns Open-Meteo's hourly arrays."""
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            ARCHIVE_URL,
            params={
                "latitude": lat,
                "longitude": lng,
                "start_date": day,
                "end_date": day,
                "hourly": HOURLY_VARS,
                "timezone": "auto",
            },
        )
        resp.raise_for_status()
        return resp.json()["hourly"]
```

The enrichment function walks the run in 30-minute steps, indexes into the hourly arrays by each sample's local hour, writes a `RunWeatherSample` per step, then computes the eight summary columns from the samples (start/end/max/min temp, apparent max, humidity avg, wind avg, precipitation total) and sets them on the run — **exactly the computation the seed script fakes**. When this lands, the seed's weather generator and the real pipeline produce the same shape, which is the whole point of having faked it realistically.

Wire it into a small `POST /integrations/weather/backfill` endpoint using the Step 1 pattern: creates a job, background task iterates runs missing `weather_temp_start_c`, resolves location (run → home → skip), enriches, counts, finishes the job.

**Two defensive notes that will matter:**
- Open-Meteo's archive lags ~2–5 days behind the present. Enriching yesterday's run may 400 or return nulls — skip those runs and let a later backfill catch them, don't fail the job.
- `timezone: "auto"` makes the hourly arrays local to the coordinates, so indexing by the run's local hour is correct. If your `started_at` values are UTC (they are — the seed uses UTC), convert to the location's local time before indexing, or accept ±1–2h sampling error for v1 and note it. For Budapest runs this is a 1–2 hour offset; for the seed data's purposes it's cosmetic, but flag it in the PR notes as a known approximation.

### Verify

```bash
RUN_ID=... # a run older than ~5 days
curl -s -X POST "http://localhost:8000/integrations/weather/backfill" | python3 -m json.tool
# poll the job, then:
docker compose exec postgres psql -U stridesense -d stridesense -c "
SELECT date, weather_temp_start_c, weather_humidity_avg FROM runs
WHERE weather_temp_start_c IS NOT NULL ORDER BY date DESC LIMIT 5;"
```

Real temperatures for real dates at your coordinates — sanity-check one against a weather-history site.

### Git

Branch `feat/weather-enrichment`, PR, merge.

---

## Step 3 — Strava OAuth and activity import

The flagship integration: a real three-legged OAuth flow, token refresh, paginated import. This is the piece that demonstrates you can do OAuth, which is why it's worth doing properly rather than minimally.

### 3a. Register the app

At https://www.strava.com/settings/api create an application. Authorization callback domain: `localhost`. Note the Client ID and Client Secret. Check your app's rate limits on that page — Strava sets per-app limits (on the order of low hundreds of requests per 15 minutes; the exact numbers vary by app age and are shown in your settings). One user's import fits comfortably; just don't write retry loops that hammer.

Config (`app/core/config.py`), empty defaults per the Phase 2 pattern — the app runs keyless, Strava features fail at the point of use:

```python
    strava_client_id: str = ""
    strava_client_secret: str = ""
```

`.env` gets the real values; `docker-compose.yml` passes both through; **`ci.yml` gets nothing** (tests mock). `docker compose down && up -d`.

### 3b. The OAuth flow

Three endpoints in a new `app/api/integrations.py` router (`prefix="/integrations"`):

**`GET /integrations/strava/authorize`** — redirects the browser to Strava's consent screen:

```python
from urllib.parse import urlencode

STRAVA_AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"

@router.get("/strava/authorize")
async def strava_authorize() -> RedirectResponse:
    settings = get_settings()
    params = urlencode({
        "client_id": settings.strava_client_id,
        "redirect_uri": "http://localhost:8000/integrations/strava/callback",
        "response_type": "code",
        "scope": "activity:read_all",
        "approval_prompt": "auto",
    })
    return RedirectResponse(f"{STRAVA_AUTHORIZE_URL}?{params}")
```

**`GET /integrations/strava/callback`** — Strava redirects back with `?code=...`; exchange it for tokens and store the connection:

```python
@router.get("/strava/callback")
async def strava_callback(
    code: str,
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> RedirectResponse:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(STRAVA_TOKEN_URL, data={
            "client_id": settings.strava_client_id,
            "client_secret": settings.strava_client_secret,
            "code": code,
            "grant_type": "authorization_code",
        })
        resp.raise_for_status()
        tokens = resp.json()

    # upsert into oauth_connections (one row per user+provider)
    ...store access_token, refresh_token, expires_at (tokens["expires_at"] is epoch)...
    return RedirectResponse("http://localhost:3000/settings?connected=strava")
```

**Token refresh** — Strava access tokens live ~6 hours. Before any API call, check `expires_at`; if within a minute of expiry, POST the token URL with `grant_type=refresh_token` and the stored refresh token, then persist the new pair. Wrap this in a `get_valid_strava_token(session, user_id)` helper so import code never thinks about it.

**Do not log tokens.** Not in print statements, not in error messages, not in `raw_payload`. The token-shaped strings in your terminal scrollback are the leak vector nobody thinks about.

*(A `state` parameter for CSRF protection is part of production OAuth; for a localhost single-user dev flow it's acceptable to omit — note it in the PR as a known simplification.)*

### 3c. The import

`POST /integrations/strava/sync` using the Step 1 job pattern. The background function:

1. Gets a valid token
2. Pages through `GET https://www.strava.com/api/v3/athlete/activities?per_page=100&page=N` until an empty page
3. Filters to `type` in `("Run", "TrailRun")`
4. Maps each activity → `upsert_run` values:

```python
def map_strava_activity(activity: dict, user_id: UUID) -> dict:
    start = datetime.fromisoformat(activity["start_date"].replace("Z", "+00:00"))
    latlng = activity.get("start_latlng") or [None, None]
    return {
        "user_id": user_id,
        "source": DataSource.STRAVA,
        "external_id": str(activity["id"]),
        "external_url": f"https://www.strava.com/activities/{activity['id']}",
        "imported_at": datetime.now(UTC),
        "date": start.date(),
        "started_at": start,
        "distance_km": round(activity["distance"] / 1000, 2),
        "duration_seconds": activity["moving_time"],
        "avg_pace_seconds_per_km": (
            round(activity["moving_time"] / (activity["distance"] / 1000), 1)
            if activity["distance"] else None
        ),
        "avg_hr": activity.get("average_heartrate"),
        "max_hr": activity.get("max_heartrate"),
        "elevation_gain_m": activity.get("total_elevation_gain"),
        "run_type": RunType.OTHER,
        "run_type_source": RunTypeSource.DEFAULT,
        "raw_title": activity.get("name"),
        "start_lat": latlng[0],
        "start_lng": latlng[1],
        "raw_payload": activity,
    }
```

Mapping decisions worth noticing: `moving_time` not `elapsed_time` (pace should exclude your traffic-light stops); `run_type=OTHER` with `run_type_source=DEFAULT` because Strava doesn't know your training intent — you'll classify manually or via title heuristics later, and the `run_type_source` column exists precisely to record *who decided*; the full activity JSON goes into `raw_payload` so future you can re-map without re-fetching.

5. Counts upserts, finishes the job. Failures anywhere → `finish_job(status="failed", error=str(e))`, never an unhandled crash.

### Verify

Visit `http://localhost:8000/integrations/strava/authorize` in your browser, approve, land back on the settings redirect. Trigger the sync, poll the job, then look at `/runs` — your actual running history, with source `strava`, real coordinates ready for weather enrichment. Run the weather backfill again and watch your real runs get their real conditions.

### Git

Branch `feat/strava-integration`. This is the phase's biggest PR — the description should cover the OAuth flow shape, the refresh strategy, the mapping decisions, and the known simplifications (no state param, plaintext tokens).

---

## Step 4 — Oura via personal access token

Deliberately *not* OAuth. Oura supports personal access tokens (https://cloud.ouraring.com/personal-access-tokens), and for a single-user app a PAT is the honest architecture: one env var, zero flow, same data. You've already demonstrated OAuth with Strava; repeating the ceremony for Oura adds effort without adding signal. This asymmetry is itself a case-study point: *choose the auth mechanism per integration based on actual requirements, not uniformity.*

Config: `oura_pat: str = ""`, `.env` + compose, nothing in CI.

The import (`POST /integrations/oura/sync`, same job pattern) hits the v2 endpoints with `Authorization: Bearer {pat}`:

- `GET https://api.ouraring.com/v2/usercollection/daily_sleep?start_date=...&end_date=...` → map to `sleep_records` (score, durations, efficiency — align to your Phase 0 model's fields)
- `GET .../daily_readiness` → readiness scores (HRV balance, resting HR live here)
- Cycle insights, if your ring/membership exposes them → `cycle_records`, including `phase` — **the column verified in Phase 2 Step 0, now receiving real data.** If your account doesn't expose cycle data, the import simply writes nothing to that table; the schema waits.

Everything keyed `user_id + source + date`, upserted with the same `on_conflict` pattern (add an `upsert_sleep_record` sibling to `upsert_run`, against the sleep table's unique constraint). Recovery data is exactly what the RED-S detection from the future-data-types plan will eventually read — this step is what makes that future feature possible without further schema work.

Check the field mappings against Oura's current docs (https://cloud.ouraring.com/v2/docs) when implementing — response shapes are versioned and the docs are the source of truth.

### Git

Branch `feat/oura-integration`, PR, merge.

---

## Step 5 — Apple Health XML import (the glucose pipeline)

The most personally valuable integration and the most technically hostile file format. Your Linx CGM writes minute-level glucose to Apple Health; Apple Health exports everything as one XML file; that file is routinely **hundreds of megabytes** — years of heart-rate samples at second granularity from every device you've owned. The two engineering problems are memory and provenance.

### 5a. The upload endpoint

`POST /integrations/apple-health/upload` accepting the export zip:

```python
@router.post("/apple-health/upload", status_code=202)
async def upload_apple_health(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
):
    dest = Path(tempfile.mkdtemp()) / "export.zip"
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            out.write(chunk)
    job = await start_job(session, user_id, "apple_health", "glucose_import")
    background_tasks.add_task(import_apple_health_glucose, job.id, user_id, dest)
    return {"job_id": str(job.id)}
```

Chunked read — never `await file.read()` a 500 MB upload into memory in one call.

### 5b. The streaming parser

The rule for huge XML: **`iterparse` + `elem.clear()`**, never `ElementTree.parse()`. Parsing the whole tree into memory is how a 400 MB file becomes a 4 GB process and an OOM kill. `iterparse` streams elements one at a time; clearing each element after processing keeps memory flat regardless of file size.

Create `app/services/apple_health.py`:

```python
"""Streaming Apple Health export parser — glucose records only (for now)."""

import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree.ElementTree import iterparse

from app.models.enums import DataSource

GLUCOSE_TYPE = "HKQuantityTypeIdentifierBloodGlucose"
MMOL_TO_MGDL = 18.018


def parse_glucose_records(zip_path: Path):
    """Yield glucose readings from an Apple Health export zip, streaming.

    Yields dicts: observed_at (tz-aware), glucose_mg_dl, source_name.
    Memory-flat regardless of export size."""
    with zipfile.ZipFile(zip_path) as zf:
        # the export XML lives at apple_health_export/export.xml inside the zip
        xml_name = next(n for n in zf.namelist() if n.endswith("export.xml"))
        with zf.open(xml_name) as xml_file:
            for _, elem in iterparse(xml_file, events=("end",)):
                if elem.tag == "Record" and elem.get("type") == GLUCOSE_TYPE:
                    unit = elem.get("unit", "")
                    value = float(elem.get("value"))
                    if "mmol" in unit.lower():
                        value *= MMOL_TO_MGDL
                    yield {
                        # Apple Health format: "2026-06-11 07:14:33 +0200"
                        "observed_at": datetime.strptime(
                            elem.get("startDate"), "%Y-%m-%d %H:%M:%S %z"
                        ),
                        "glucose_mg_dl": round(value, 1),
                        "source_name": elem.get("sourceName", ""),
                    }
                elem.clear()  # THE line that keeps memory flat
```

Three details doing real work:

- **Unit conversion at the boundary.** Your locale (Hungary) means Apple Health likely stores mmol/L; the schema is canonically mg/dL (the Phase 1 decision). Convert once, at ingestion, exactly as designed.
- **Timezone-aware parsing.** The `%z` captures Apple's offset (`+0200`). Every downstream comparison against run windows is between aware datetimes — mixing naive and aware datetimes is a `TypeError` at best and a silent 2-hour data misalignment at worst.
- **`source_name` provenance.** Apple Health records which app wrote each sample. This is how the import distinguishes your Linx data from any other glucose source.

### 5c. The import function

The background task (`import_apple_health_glucose`) — remember: **its own `AsyncSessionLocal()` session**, never the request's — does four things:

1. **Stream and tag.** Iterate `parse_glucose_records`; tag each reading `DataSource.LINX_CGM` if `"linx" in source_name.lower()` else `DataSource.APPLE_HEALTH` — the config-by-source-name plan from the original Linx discussion, now real. Batch readings into memory-bounded chunks (e.g., 5,000) for insertion.

2. **Attach samples to runs.** Load the user's runs with `started_at`; for each reading falling inside a run's window (`started_at` to `started_at + duration_seconds`), write a `RunGlucoseSample` with the computed `elapsed_seconds`. Upsert on the sample table's unique constraint (`run_id, elapsed_seconds, source`) so re-imports are clean.

3. **Compute the run summaries.** For each run that gained samples: the eight `glucose_*` columns — start/end/min/max/avg during, the pre/post 60-minute window averages from readings adjacent to the run, time-in-range (70–140). *This is the seed script's glucose math applied to real readings* — same formulas, real inputs. If the logic is worth sharing, extract it into a `compute_glucose_summary(samples)` helper both the seed and the import call; the seed faked realistic data precisely so this moment would be a drop-in.

4. **Compute daily records.** Group all readings by local date → `glucose_daily_records` rows (avg/min/max, CV, GMI via the standard formula, overnight window), upserted on `user_id + source + date`.

Count everything into the job; any exception → `finish_job(status="failed", error=...)`.

### 5d. The real-data verification

This is the moment the whole glucose design proves out. Export from your phone (Settings → Health → Export All Health Data), upload the zip, poll the job, then:

```bash
docker compose exec postgres psql -U stridesense -d stridesense -c "
SELECT r.date, r.run_type, r.glucose_at_start_mg_dl, r.glucose_at_end_mg_dl,
       r.glucose_time_in_range_pct_during_run,
       (SELECT COUNT(*) FROM run_glucose_samples s WHERE s.run_id = r.id) AS samples
FROM runs r
WHERE r.glucose_at_start_mg_dl IS NOT NULL AND r.source = 'STRAVA'
ORDER BY r.date DESC LIMIT 10;"
```

Real Strava runs with real Linx glucose attached — the sensor → Linx app → Apple Health → export → StrideSense pipeline, end to end. Then open one of those runs in the UI: **the insight now narrates your actual physiology.** (One insight-cache note: runs that had insights generated before glucose arrived will serve the stale cached version. Delete their `insights` rows to regenerate with the enriched context — and file "invalidate insight cache when context changes" as a Phase 4 item.)

### Git

Branch `feat/apple-health-glucose-import`. PR notes should record: streaming-parse memory strategy, unit conversion, timezone handling, the Linx source tagging, and the cache-staleness known issue.

---

## Step 6 — Connections UI and source badges

Three frontend pieces, all straightforward against the endpoints that now exist:

**A settings/connections page** (`app/settings/page.tsx`): a Strava card whose Connect button links to `http://localhost:8000/integrations/strava/authorize` (a plain link — the OAuth dance is redirects, not fetch), a Sync Now button POSTing the sync endpoint, an Oura status card, and an Apple Health upload form (`<input type="file">` → `FormData` POST — note this request must NOT set `Content-Type: application/json`; let the browser set the multipart boundary, which means bypassing or special-casing your `request()` helper's default header).

**Import job status**: a list under the connections cards polling `GET /integrations/jobs` every few seconds while any job is `running` — status, records processed, error message if failed. Poll-with-`setInterval`-in-`useEffect`, cleared on unmount.

**Source badges on the run list**: a small label per row — `strava` orange-ish, `manual` gray, glucose droplet when `glucose_at_start_mg_dl` is present (the indicator-icon idea from the Phase 1 list-page discussion, now that mixed sources make it meaningful).

New types (`ImportJob`, connection status) go in `lib/types.ts`; new client methods in `lib/api.ts` — inside the `api` object, imports added in the same motion.

### Git

Branch `feat/connections-ui`, PR, merge.

---

## Step 7 — Tests

Every external call mocked; the suite green with every credential blanked. Two techniques beyond Phase 2's:

**Mock httpx at the transport level with `respx`** (add via `uv add --dev respx`). Patching functions worked for one LLM call; for integrations with multiple HTTP calls per flow, intercepting the HTTP layer is cleaner:

```python
import respx
from httpx import Response

@respx.mock
async def test_strava_sync_upserts_activities(client):
    respx.post("https://www.strava.com/oauth/token").mock(
        return_value=Response(200, json={"access_token": "t", "refresh_token": "r", "expires_at": 9999999999})
    )
    respx.get("https://www.strava.com/api/v3/athlete/activities").mock(
        side_effect=[
            Response(200, json=[STRAVA_ACTIVITY_FIXTURE]),
            Response(200, json=[]),   # second page empty → pagination terminates
        ]
    )
    ...trigger sync, await completion, assert the run exists with source=strava...
    ...trigger again, assert still exactly one run (idempotency)...
```

The **idempotency assertion is the one that matters** — import twice, count once. It's the property everything in this phase depends on.

**Fixture files for the parser.** A hand-written 20-record `tests/fixtures/apple_health_mini.zip` (a tiny `export.xml` zipped with the right internal path) covering: a Linx-sourced mmol/L record (tests conversion *and* tagging), a non-Linx record, readings inside and outside a run window, and a malformed record if you want to test skip-don't-crash. Parser tests run the generator over the fixture and assert exact values — `5.3 mmol/L` in, `95.5 mg/dL` out.

And the Phase 2 rules still apply: any remaining function-level mocks patch **where the name is looked up** (`app.api.integrations.X`, not the defining module), and the proof-of-isolation run:

```bash
docker compose exec -e ANTHROPIC_API_KEY= -e STRAVA_CLIENT_ID= -e STRAVA_CLIENT_SECRET= -e OURA_PAT= \
  backend uv run pytest -v
```

All green with everything blanked = CI-safe.

### Git

Branch `feat/phase3-tests`, PR, merge.

---

## Verification checklist for Phase 3

- [ ] Seed guard refuses to wipe once imported data exists (`--force` overrides)
- [ ] Weather backfill enriches runs with real Open-Meteo data (home-location fallback works)
- [ ] Strava OAuth completes; sync imports your real history; re-sync duplicates nothing
- [ ] Token refresh works (check after 6+ hours: sync succeeds without re-authorizing)
- [ ] Oura sync populates sleep/readiness (and cycle if available)
- [ ] Apple Health upload streams a full-size export without memory blowup
- [ ] Linx readings tagged `LINX_CGM`; mmol/L converted; samples attach to the right runs
- [ ] Real run + real glucose + real weather → the insight narrates actual physiology
- [ ] Every import failure lands in `import_jobs` as `failed` with an error message — nothing 500s
- [ ] Full suite green with ALL credentials blanked
- [ ] No token or key appears in any log line, error message, or committed file

---

## What Phase 3 sets up

With real multi-source data flowing, the deferred features from the future-data-types plan stop being hypothetical: RED-S pattern detection has real recovery + load + performance trends to read; cycle-phase analysis has real `phase` values joined to real runs; the canonical-selection layer has actual source conflicts to resolve the day you import Apple Health workouts alongside Strava. And Phase 4 (polish: insight cache invalidation, webhooks, pre-commit hooks, token encryption, the glucose-curve chart) has a live system to polish rather than a demo. The portfolio sentence this phase earns: *"the ingestion layer is idempotent, job-tracked, and source-tagged — my own CGM data flows through the same generic pipeline as any other source, which is the design paying off."*
