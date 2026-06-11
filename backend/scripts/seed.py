"""Seed the database with a dev user, ~6 months of runs, and glucose data."""

import asyncio
import random
import uuid
from datetime import UTC, date, datetime, time, timedelta
from statistics import mean
from uuid import UUID

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import GlucoseDailyRecord, Run, RunGlucoseSample, User
from app.models.enums import DataSource, RunType, RunTypeSource

# --- Run generation ---

RUN_TYPE_WEIGHTS: list[tuple[RunType, float]] = [
    (RunType.EASY, 0.50),
    (RunType.LONG, 0.15),
    (RunType.RECOVERY, 0.15),
    (RunType.TEMPO, 0.10),
    (RunType.INTERVAL, 0.08),
    (RunType.RACE, 0.02),
]

# (distance_min_km, distance_max_km, pace_min_sec_per_km, pace_max_sec_per_km, hr_mean, hr_std)
RUN_TYPE_PROFILES: dict[RunType, tuple[float, float, int, int, int, int]] = {
    RunType.EASY:     ( 5.0, 12.0, 330, 390, 142, 8),
    RunType.LONG:    (15.0, 32.0, 340, 400, 148, 7),
    RunType.RECOVERY: ( 3.0,  6.0, 380, 430, 130, 6),
    RunType.TEMPO:    ( 6.0, 12.0, 270, 310, 165, 6),
    RunType.INTERVAL: ( 6.0, 10.0, 280, 330, 170, 8),
    RunType.RACE:     ( 5.0, 42.2, 240, 310, 175, 5),
}

RUN_DAY_FREQUENCY = 5 / 7
NUM_DAYS_OF_HISTORY = 180

# --- Glucose generation ---

# Non-diabetic adult baseline (mg/dL)
BASELINE_GLUCOSE_MEAN = 95.0
BASELINE_GLUCOSE_STD = 6.0

# Per-run-type glucose response patterns:
#  pre_offset: how glucose differs from baseline before the run (fueled = higher)
#  during_change: net change from start of run to end of run
#  post_change: residual offset 60 min after the run ends
GLUCOSE_RESPONSE_BY_RUN_TYPE: dict[RunType, dict[str, tuple[float, float]]] = {
    RunType.EASY: {
        "pre_offset": (-5, 15),
        "during_change": (-5, 10),
        "post_change": (-5, 5),
    },
    RunType.LONG: {
        "pre_offset": (-5, 25),
        "during_change": (-30, 5),
        "post_change": (-15, 10),
    },
    RunType.RECOVERY: {
        "pre_offset": (-5, 5),
        "during_change": (-3, 5),
        "post_change": (-3, 5),
    },
    RunType.TEMPO: {
        "pre_offset": (-5, 15),
        "during_change": (5, 30),
        "post_change": (-10, 10),
    },
    RunType.INTERVAL: {
        "pre_offset": (0, 15),
        "during_change": (15, 45),
        "post_change": (-15, 5),
    },
    RunType.RACE: {
        "pre_offset": (10, 40),
        "during_change": (-20, 25),
        "post_change": (-25, 10),
    },
}

# 30-min sampling, matching the planned Linx-via-Apple-Health ingestion granularity
GLUCOSE_SAMPLE_INTERVAL_SECONDS = 30 * 60


def _pick_run_type() -> RunType:
    types, weights = zip(*RUN_TYPE_WEIGHTS, strict=True)
    return random.choices(types, weights=weights, k=1)[0]


def _random_start_time_for_date(d: date) -> datetime:
    """Most runs are early morning, some are after work."""
    hour = random.choices([6, 7, 8, 17, 18, 19], weights=[3, 4, 2, 1, 2, 1])[0]
    minute = random.randint(0, 59)
    return datetime.combine(d, time(hour, minute), tzinfo=UTC)


def _generate_run_metrics(run_type: RunType) -> dict:
    dist_min, dist_max, pace_min, pace_max, hr_mean, hr_std = RUN_TYPE_PROFILES[run_type]

    distance_km = round(random.uniform(dist_min, dist_max), 2)
    pace_per_km = random.randint(pace_min, pace_max)
    duration_seconds = int(distance_km * pace_per_km)
    avg_hr = max(100, min(190, int(random.gauss(hr_mean, hr_std))))
    perceived_effort = {
        RunType.EASY:     random.randint(3, 5),
        RunType.LONG:    random.randint(5, 7),
        RunType.RECOVERY: random.randint(2, 4),
        RunType.TEMPO:    random.randint(6, 8),
        RunType.INTERVAL: random.randint(7, 9),
        RunType.RACE:     random.randint(8, 10),
    }[run_type]

    return {
        "distance_km": distance_km,
        "duration_seconds": duration_seconds,
        "avg_pace_seconds_per_km": float(pace_per_km),
        "avg_hr": avg_hr,
        "perceived_effort": perceived_effort,
        "run_type": run_type,
    }


def _generate_glucose_for_run(
    run: Run,
    day_baseline: float,
) -> tuple[list[RunGlucoseSample], dict]:
    """Generate per-run samples and the denormalized summary for run.glucose_*."""
    pattern = GLUCOSE_RESPONSE_BY_RUN_TYPE[run.run_type]
    pre_offset = random.uniform(*pattern["pre_offset"])
    during_change = random.uniform(*pattern["during_change"])
    post_offset = random.uniform(*pattern["post_change"])

    glucose_at_start = day_baseline + pre_offset
    glucose_at_end_target = glucose_at_start + during_change

    samples: list[RunGlucoseSample] = []
    values: list[float] = []

    # Walk 30-min steps from t=0, plus one final sample at exact end
    t_steps = list(range(0, run.duration_seconds + 1, GLUCOSE_SAMPLE_INTERVAL_SECONDS))
    if t_steps[-1] != run.duration_seconds:
        t_steps.append(run.duration_seconds)

    for t in t_steps:
        progress = t / run.duration_seconds if run.duration_seconds > 0 else 0
        value = glucose_at_start + (during_change * progress) + random.gauss(0, 3)
        value = max(50.0, min(220.0, value))  # clamp to plausible range

        samples.append(
            RunGlucoseSample(
                run_id=run.id,
                elapsed_seconds=t,
                observed_at=run.started_at + timedelta(seconds=t),
                glucose_mg_dl=round(value, 1),
                source=DataSource.APPLE_HEALTH,
            )
        )
        values.append(value)

    pre_run_avg = day_baseline + random.uniform(-3, 3)
    post_run_avg = max(50.0, min(220.0, glucose_at_end_target + post_offset + random.gauss(0, 3)))
    in_range = sum(1 for v in values if 70 <= v <= 140)
    tir = (in_range / len(values)) * 100

    summary = {
        "glucose_pre_run_60min_avg_mg_dl": round(pre_run_avg, 1),
        "glucose_at_start_mg_dl": round(values[0], 1),
        "glucose_at_end_mg_dl": round(values[-1], 1),
        "glucose_avg_during_run_mg_dl": round(mean(values), 1),
        "glucose_min_during_run_mg_dl": round(min(values), 1),
        "glucose_max_during_run_mg_dl": round(max(values), 1),
        "glucose_post_run_60min_avg_mg_dl": round(post_run_avg, 1),
        "glucose_time_in_range_pct_during_run": round(tir, 1),
    }

    return samples, summary


def _generate_daily_glucose_record(
    user_id: UUID,
    d: date,
    day_baseline: float,
) -> GlucoseDailyRecord:
    daily_avg = day_baseline + random.uniform(-3, 8)
    daily_min = max(60.0, daily_avg - random.uniform(15, 30))
    daily_max = min(200.0, daily_avg + random.uniform(20, 50))

    cv = random.uniform(18, 32)  # healthy CV is typically <30%
    std_dev = (daily_avg * cv) / 100
    tir = random.uniform(75, 95)

    overnight_avg = day_baseline - random.uniform(0, 8)
    overnight_min = overnight_avg - random.uniform(3, 10)

    # GMI = 3.31 + 0.02392 × mean glucose (standard CGM formula)
    gmi = 3.31 + 0.02392 * daily_avg

    return GlucoseDailyRecord(
        user_id=user_id,
        date=d,
        source=DataSource.APPLE_HEALTH,
        avg_glucose_mg_dl=round(daily_avg, 1),
        min_glucose_mg_dl=round(daily_min, 1),
        max_glucose_mg_dl=round(daily_max, 1),
        std_glucose_mg_dl=round(std_dev, 1),
        time_in_range_pct=round(tir, 1),
        glucose_variability_cv=round(cv, 1),
        gmi=round(gmi, 2),
        overnight_avg_glucose_mg_dl=round(overnight_avg, 1),
        overnight_min_glucose_mg_dl=round(overnight_min, 1),
    )


async def seed() -> None:
    settings = get_settings()
    dev_user_id: UUID = settings.dev_user_id

    async with AsyncSessionLocal() as session:
        # Ensure dev user exists
        existing = await session.execute(select(User).where(User.id == dev_user_id))
        user = existing.scalar_one_or_none()
        if user is None:
            session.add(
                User(
                    id=dev_user_id,
                    email="dev@stridesense.local",
                    display_name="Dev User",
                    source_priority={},
                )
            )
            print(f"Created dev user {dev_user_id}")

        # Idempotent reset. Deleting runs cascades to run_glucose_samples via FK.
        await session.execute(
            delete(GlucoseDailyRecord).where(GlucoseDailyRecord.user_id == dev_user_id)
        )
        deleted = await session.execute(delete(Run).where(Run.user_id == dev_user_id))
        await session.commit()
        if deleted.rowcount:
            print(f"Deleted {deleted.rowcount} existing runs and related data")

        all_runs: list[Run] = []
        all_samples: list[RunGlucoseSample] = []
        all_daily_records: list[GlucoseDailyRecord] = []

        today = date.today()
        for day_offset in range(NUM_DAYS_OF_HISTORY):
            run_date = today - timedelta(days=day_offset)
            day_baseline = random.gauss(BASELINE_GLUCOSE_MEAN, BASELINE_GLUCOSE_STD)

            # Daily glucose summary every day, regardless of whether there's a run
            all_daily_records.append(
                _generate_daily_glucose_record(dev_user_id, run_date, day_baseline)
            )

            # Skip non-run days
            if random.random() > RUN_DAY_FREQUENCY:
                continue

            run_type = _pick_run_type()
            metrics = _generate_run_metrics(run_type)
            run = Run(
                id=uuid.uuid4(),  # explicit, so we can reference it below
                user_id=dev_user_id,
                date=run_date,
                started_at=_random_start_time_for_date(run_date),
                source=DataSource.MANUAL,
                run_type_source=RunTypeSource.USER,
                **metrics,
            )

            samples, glucose_summary = _generate_glucose_for_run(run, day_baseline)
            for field, value in glucose_summary.items():
                setattr(run, field, value)

            all_runs.append(run)
            all_samples.extend(samples)

        session.add_all(all_runs)
        await session.flush()
        session.add_all(all_samples)
        session.add_all(all_daily_records)
        await session.commit()

        print(f"Created {len(all_runs)} runs with {len(all_samples)} glucose samples")
        print(f"Created {len(all_daily_records)} daily glucose records")


if __name__ == "__main__":
    asyncio.run(seed())
