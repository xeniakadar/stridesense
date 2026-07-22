"""Seed the demo deployment from the committed marathon-block fixture.

Wipes the dev user's runs/glucose and loads scripts/fixtures/demo_block.json
(real runs, city-snapped and stripped — see export_demo_block.py), then
generates SYNTHETIC glucose for each run with the same generator seed.py
uses. Everything written here is tagged DataSource.MANUAL — the marker for
seeded, non-device data (the demo UI additionally captions glucose as
simulated).

Idempotent: re-running wipes and reloads the same fixture. Same guard as
seed.py — refuses to wipe imported (non-manual) runs unless --force:

    docker compose exec backend uv run python -m scripts.seed_demo
    docker compose exec backend uv run python -m scripts.seed_demo --force

Demo deploy sequence (run in this order):
    seed_demo -> embed_runs --apply -> pregenerate_insights
              -> pregenerate_ask_answers
"""

import asyncio
import json
import random
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import (
    AskDemoAnswer,
    DailyBrief,
    GlucoseDailyRecord,
    Run,
    RunGlucoseSample,
    User,
)
from app.models.enums import DataSource, RunType, RunTypeSource
from scripts.seed import (
    BASELINE_GLUCOSE_MEAN,
    BASELINE_GLUCOSE_STD,
    _generate_daily_glucose_record,
    _generate_glucose_for_run,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "demo_block.json"


def _run_from_fixture(user_id: UUID, row: dict) -> Run:
    return Run(
        id=uuid.uuid4(),
        user_id=user_id,
        date=datetime.fromisoformat(row["date"]).date(),
        started_at=(
            datetime.fromisoformat(row["started_at"]) if row["started_at"] else None
        ),
        source=DataSource.MANUAL,
        run_type=RunType(row["run_type"]),
        run_type_source=RunTypeSource.USER,
        distance_km=row["distance_km"],
        duration_seconds=row["duration_seconds"],
        avg_pace_seconds_per_km=row["avg_pace_seconds_per_km"],
        avg_hr=row["avg_hr"],
        start_lat=row["start_lat"],
        start_lng=row["start_lng"],
        weather_temp_start_c=row["weather_temp_start_c"],
        weather_temp_end_c=row["weather_temp_end_c"],
        weather_temp_max_c=row["weather_temp_max_c"],
        weather_temp_min_c=row["weather_temp_min_c"],
        weather_apparent_temp_max_c=row["weather_apparent_temp_max_c"],
        weather_humidity_avg=row["weather_humidity_avg"],
        weather_wind_speed_avg_kmh=row["weather_wind_speed_avg_kmh"],
        weather_precipitation_total_mm=row["weather_precipitation_total_mm"],
    )


async def load_demo_block(
    session: AsyncSession, user_id: UUID, rows: list[dict]
) -> dict[str, int]:
    """Wipe the user's runs/glucose/briefs and load the fixture with
    synthetic glucose. Idempotent — same fixture in, same state out.
    Doesn't touch the global ask_demo_answers table (main() handles it)."""
    await session.execute(
        delete(GlucoseDailyRecord).where(GlucoseDailyRecord.user_id == user_id)
    )
    # Stale briefs would narrate the wiped dataset
    await session.execute(delete(DailyBrief).where(DailyBrief.user_id == user_id))
    # Cascades to run_glucose_samples and insights via FKs
    await session.execute(delete(Run).where(Run.user_id == user_id))

    runs = [_run_from_fixture(user_id, row) for row in rows]

    # One glucose baseline (and one daily record) per calendar day across
    # the whole block — rest days included, and never a duplicate for
    # dates with two runs
    all_samples: list[RunGlucoseSample] = []
    daily_records: list[GlucoseDailyRecord] = []
    if runs:
        first = min(r.date for r in runs)
        last = max(r.date for r in runs)
        day_baselines = {
            first
            + timedelta(days=i): random.gauss(
                BASELINE_GLUCOSE_MEAN, BASELINE_GLUCOSE_STD
            )
            for i in range((last - first).days + 1)
        }
        for d, baseline in day_baselines.items():
            daily = _generate_daily_glucose_record(user_id, d, baseline)
            daily.source = DataSource.MANUAL
            daily_records.append(daily)

        for run in runs:
            if run.started_at is None:
                continue
            samples, summary = _generate_glucose_for_run(
                run, day_baselines[run.date]
            )
            for field, value in summary.items():
                setattr(run, field, value)
            for sample in samples:
                sample.source = DataSource.MANUAL  # synthetic, not device data
            all_samples.extend(samples)

    session.add_all(runs)
    await session.flush()
    session.add_all(all_samples)
    session.add_all(daily_records)
    await session.commit()

    return {
        "runs": len(runs),
        "glucose_samples": len(all_samples),
        "daily_records": len(daily_records),
    }


async def main() -> None:
    user_id = get_settings().dev_user_id
    rows = json.loads(FIXTURE_PATH.read_text())

    async with AsyncSessionLocal() as session:
        # Guard: refuse to wipe real imported data (same semantics as seed.py)
        imported = await session.execute(
            select(Run)
            .where(Run.user_id == user_id, Run.source != DataSource.MANUAL)
            .limit(1)
        )
        if imported.scalar_one_or_none() is not None and "--force" not in sys.argv:
            print(
                "Refusing to reseed: imported (non-manual) runs exist.\n"
                "Re-run with --force to wipe ALL data including imports."
            )
            return

        existing = await session.execute(select(User).where(User.id == user_id))
        if existing.scalar_one_or_none() is None:
            session.add(
                User(
                    id=user_id,
                    email="dev@stridesense.local",
                    display_name="Dev User",
                    source_priority={},
                )
            )
            await session.commit()
            print(f"Created dev user {user_id}")

        # Canned ask answers cite run ids that are about to be wiped
        await session.execute(delete(AskDemoAnswer))

        counts = await load_demo_block(session, user_id, rows)
        print(
            f"Loaded {counts['runs']} runs, {counts['glucose_samples']} synthetic "
            f"glucose samples, {counts['daily_records']} daily records"
        )
        print(
            "Next: embed_runs --apply -> pregenerate_insights -> "
            "pregenerate_ask_answers"
        )


if __name__ == "__main__":
    asyncio.run(main())
