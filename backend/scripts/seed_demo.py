"""Seed the demo deployment with a rich, deterministic synthetic dataset.

Generates ~350 runs from Jan 1 2025 to today for the dev user with a
narrative structure a visitor can actually explore:

- A residence timeline (Phuket -> Hanoi -> Budapest -> Lisbon -> NYC ->
  Chicago -> San Francisco -> Lisbon -> NYC); every run carries that
  city's 2-decimal center coordinates and weather drawn from a per-city
  climate profile, with time-of-day temperature computed in the run's
  LOCAL time.
- A weekly training structure: weekend long runs, 1-2 quality sessions,
  easy/recovery fill, occasional rest weeks, and four races (Lisbon half
  May 2025, Chicago marathon Oct 12 2025, SF 10K Nov 2025, NYC 10K Jun
  2026). run_type_source is USER on every run.
- A scripted fitness arc: easy pace improves ~24 s/km across the span
  with plateaus, a marathon-build peak Aug-Oct 2025, a two-week
  post-marathon regression, and renewed progress in 2026. Pace, HR, and
  duration all derive from the arc; HR correlates with type and heat.
- Synthetic glucose for every run plus daily records via seed.py's
  generator, everything tagged DataSource.MANUAL (the demo UI captions
  glucose as simulated).

Output is DETERMINISTIC: the RNG is seeded from a fixed constant (plus
the user id, so parallel test users can't collide on generated PKs) —
same code, same end date, same bytes on every deploy.

Idempotent, with seed.py's guard: refuses to wipe imported (non-manual)
runs unless --force. Also clears stale daily briefs and canned ask
answers (their cited run ids die with the wiped runs).

    docker compose exec backend uv run python -m scripts.seed_demo
    docker compose exec backend uv run python -m scripts.seed_demo --force

Demo deploy sequence (run in this order):
    seed_demo -> embed_runs --apply -> pregenerate_insights
              -> pregenerate_ask_answers
"""

import asyncio
import math
import random
import sys
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
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

GENERATION_SEED = "stridesense-demo-v1"
DEMO_START = date(2025, 1, 1)


@dataclass(frozen=True)
class City:
    lat: float
    lng: float
    utc_offset_hours: int  # fixed offset — DST is noise a demo doesn't need
    jan_mean_c: float
    jul_mean_c: float
    diurnal_range_c: float
    humidity_mean: float
    humidity_std: float
    wet_chance: float
    dry_summer: bool = False  # Mediterranean pattern: summer rain is rare
    morning_fog: bool = False  # SF: humid foggy mornings


CITIES: dict[str, City] = {
    "phuket": City(7.89, 98.40, 7, 27.5, 28.5, 6.0, 80, 8, 0.35),
    "hanoi": City(21.03, 105.85, 7, 18.0, 29.0, 7.0, 78, 8, 0.25),
    "budapest": City(47.51, 19.05, 1, 0.0, 22.0, 8.0, 68, 12, 0.18),
    "lisbon": City(38.72, -9.14, 0, 11.5, 24.0, 8.0, 70, 12, 0.20, dry_summer=True),
    "nyc": City(40.78, -73.97, -5, 0.5, 25.0, 8.0, 64, 12, 0.22),
    "chicago": City(41.88, -87.62, -6, -4.0, 24.0, 9.0, 66, 12, 0.22),
    "sf": City(37.77, -122.42, -8, 11.0, 15.0, 7.0, 78, 10, 0.15, morning_fog=True),
}

# Residence timeline: (first_day, city_key). Each entry runs until the next
# one starts; the last runs to today.
RESIDENCE_TIMELINE: list[tuple[date, str]] = [
    (date(2025, 1, 1), "phuket"),
    (date(2025, 1, 8), "hanoi"),
    (date(2025, 1, 15), "budapest"),
    (date(2025, 2, 1), "lisbon"),
    (date(2025, 10, 1), "nyc"),
    (date(2025, 10, 11), "chicago"),
    (date(2025, 10, 18), "sf"),
    (date(2025, 12, 16), "lisbon"),
    (date(2026, 5, 1), "nyc"),
]

# (date, distance_km, kind) — kind picks race pace/HR off the easy-pace arc
RACES: list[tuple[date, float, str]] = [
    (date(2025, 5, 11), 21.1, "half"),  # Lisbon half-marathon
    (date(2025, 10, 12), 42.2, "marathon"),  # Chicago Marathon
    (date(2025, 11, 16), 10.0, "10k"),  # San Francisco 10K
    (date(2026, 6, 14), 10.0, "10k"),  # NYC 10K
]

# The scripted fitness arc: easy pace (s/km) at control dates, linearly
# interpolated between them. Progress with plateaus, a build peak into the
# Oct 12 marathon, a two-week post-race regression, renewed 2026 progress.
EASY_PACE_ARC: list[tuple[date, float]] = [
    (date(2025, 1, 1), 395.0),
    (date(2025, 3, 1), 388.0),
    (date(2025, 5, 1), 386.0),  # plateau
    (date(2025, 7, 1), 384.0),
    (date(2025, 8, 1), 380.0),  # marathon build begins
    (date(2025, 10, 12), 372.0),  # peak fitness on race day
    (date(2025, 10, 26), 382.0),  # post-marathon regression
    (date(2025, 12, 1), 380.0),
    (date(2026, 3, 1), 375.0),
    (date(2026, 12, 31), 368.0),  # renewed steady progress
]

MARATHON_DATE = date(2025, 10, 12)
BUILD_START = date(2025, 8, 1)
BUILD_PEAK = date(2025, 9, 28)  # longest long run, two weeks out

# Relative to the easy-pace arc
PACE_FACTORS: dict[RunType, float] = {
    RunType.EASY: 1.0,
    RunType.RECOVERY: 1.13,
    RunType.LONG: 1.05,
    RunType.TEMPO: 0.83,
    RunType.INTERVAL: 0.87,
}
RACE_PACE_FACTORS = {"10k": 0.78, "half": 0.82, "marathon": 0.92}

HR_BASE: dict[RunType, int] = {
    RunType.EASY: 142,
    RunType.RECOVERY: 130,
    RunType.LONG: 149,
    RunType.TEMPO: 166,
    RunType.INTERVAL: 171,
}
RACE_HR_BASE = {"10k": 175, "half": 168, "marathon": 158}

EFFORT_RANGE: dict[RunType, tuple[int, int]] = {
    RunType.EASY: (3, 5),
    RunType.RECOVERY: (2, 4),
    RunType.LONG: (5, 7),
    RunType.TEMPO: (6, 8),
    RunType.INTERVAL: (7, 9),
    RunType.RACE: (8, 10),
}


def city_on(d: date) -> City:
    """The city of residence on a date, per the timeline."""
    current = RESIDENCE_TIMELINE[0][1]
    for start, key in RESIDENCE_TIMELINE:
        if d < start:
            break
        current = key
    return CITIES[current]


def easy_pace_on(d: date) -> float:
    """The arc's easy pace (s/km) on a date, linear between control points."""
    arc = EASY_PACE_ARC
    if d <= arc[0][0]:
        return arc[0][1]
    for (d0, p0), (d1, p1) in zip(arc, arc[1:], strict=False):
        if d0 <= d <= d1:
            progress = (d - d0).days / (d1 - d0).days
            return p0 + (p1 - p0) * progress
    return arc[-1][1]


def _day_mean_temp(city: City, d: date) -> float:
    """Seasonal daily-mean temperature: cosine between Jan and Jul means."""
    day_of_year = d.timetuple().tm_yday
    summer_factor = (1 - math.cos((day_of_year - 15) / 365.25 * 2 * math.pi)) / 2
    return city.jan_mean_c + (city.jul_mean_c - city.jan_mean_c) * summer_factor


def _temp_at_local_hour(city: City, d: date, local_hour: float) -> float:
    """Diurnal curve around the daily mean: coolest ~03:00, warmest ~15:00,
    in the city's LOCAL clock."""
    mean = _day_mean_temp(city, d)
    return mean + (city.diurnal_range_c / 2) * math.cos(
        (local_hour - 15) / 24 * 2 * math.pi
    )


def _weather_for(city: City, d: date, local_hour: int, duration_seconds: int) -> dict:
    temp_start = _temp_at_local_hour(city, d, local_hour) + random.uniform(-1.5, 1.5)
    end_hour = local_hour + duration_seconds / 3600
    temp_end = _temp_at_local_hour(city, d, end_hour) + random.uniform(-1.5, 1.5)
    temp_max = _temp_at_local_hour(city, d, 15) + random.uniform(-1, 2)
    temp_min = _temp_at_local_hour(city, d, 4) + random.uniform(-2, 1)

    humidity = random.gauss(city.humidity_mean, city.humidity_std)
    if city.morning_fog and local_hour < 11:
        humidity += 10
    humidity = max(25.0, min(98.0, humidity))

    wind = max(0.0, random.gauss(11, 6))

    wet_chance = city.wet_chance
    if city.dry_summer and d.month in (6, 7, 8, 9):
        wet_chance *= 0.25
    precip = round(random.uniform(0.5, 12.0), 1) if random.random() < wet_chance else 0.0

    apparent_max = temp_max + (humidity - 60) * 0.05 - wind * 0.1

    return {
        "weather_temp_start_c": round(temp_start, 1),
        "weather_temp_end_c": round(temp_end, 1),
        "weather_temp_max_c": round(temp_max, 1),
        "weather_temp_min_c": round(temp_min, 1),
        "weather_apparent_temp_max_c": round(apparent_max, 1),
        "weather_humidity_avg": round(humidity, 1),
        "weather_wind_speed_avg_kmh": round(wind, 1),
        "weather_precipitation_total_mm": precip,
    }


def _long_run_distance(d: date) -> float:
    """Long-run progression: a ramp to 32 km through the marathon build
    (with cutback weeks), a taper, modest otherwise."""
    if BUILD_START <= d <= BUILD_PEAK:
        progress = (d - BUILD_START).days / (BUILD_PEAK - BUILD_START).days
        base = 17 + 15 * progress
        if d.isocalendar().week % 3 == 0:  # cutback week
            base *= 0.75
        return round(base + random.uniform(-1, 1), 2)
    if BUILD_PEAK < d < MARATHON_DATE:  # taper
        return round(random.uniform(12, 15), 2)
    if MARATHON_DATE < d <= MARATHON_DATE + timedelta(days=21):  # recovery
        return round(random.uniform(9, 12), 2)
    return round(random.uniform(12, 18), 2)


def _distance_for(run_type: RunType, d: date) -> float:
    if run_type == RunType.LONG:
        return _long_run_distance(d)
    lo, hi = {
        RunType.EASY: (6.0, 10.0),
        RunType.RECOVERY: (4.0, 6.0),
        RunType.TEMPO: (7.0, 11.0),
        RunType.INTERVAL: (7.0, 10.0),
    }[run_type]
    return round(random.uniform(lo, hi), 2)


def _local_start_hour(run_type: RunType) -> int:
    """Long runs and races start early; the rest are morning-weighted."""
    if run_type in (RunType.LONG, RunType.RACE):
        return random.choice([7, 8])
    return random.choices([6, 7, 8, 17, 18], weights=[3, 4, 2, 1, 2])[0]


def _build_run(
    user_id: UUID,
    d: date,
    run_type: RunType,
    distance_km: float | None = None,
    race_kind: str | None = None,
) -> Run:
    city = city_on(d)
    local_hour = _local_start_hour(run_type)
    started_at = datetime.combine(
        d,
        time(local_hour, random.randint(0, 59)),
        tzinfo=timezone(timedelta(hours=city.utc_offset_hours)),
    )

    if distance_km is None:
        distance_km = _distance_for(run_type, d)
    # Weather needs a duration; pace needs the weather (heat penalty).
    # Break the loop with the pre-heat duration as the weather's input.
    base_pace = easy_pace_on(d) * (
        RACE_PACE_FACTORS[race_kind] if race_kind else PACE_FACTORS[run_type]
    )
    duration_guess = int(distance_km * base_pace)
    weather = _weather_for(city, d, local_hour, duration_guess)

    heat_factor = 1 + max(0.0, weather["weather_temp_start_c"] - 22) * 0.004
    pace = base_pace * heat_factor * random.gauss(1, 0.015)
    duration_seconds = int(distance_km * pace)

    hr_base = RACE_HR_BASE[race_kind] if race_kind else HR_BASE[run_type]
    heat_hr = max(0.0, weather["weather_temp_start_c"] - 16) * 0.7
    avg_hr = int(max(100, min(195, hr_base + heat_hr + random.gauss(0, 3))))

    effort_lo, effort_hi = EFFORT_RANGE[run_type]

    return Run(
        id=uuid.UUID(int=random.getrandbits(128), version=4),
        user_id=user_id,
        date=d,
        started_at=started_at,
        source=DataSource.MANUAL,
        run_type=run_type,
        run_type_source=RunTypeSource.USER,
        distance_km=distance_km,
        duration_seconds=duration_seconds,
        avg_pace_seconds_per_km=round(duration_seconds / distance_km, 1),
        avg_hr=avg_hr,
        perceived_effort=random.randint(effort_lo, effort_hi),
        start_lat=city.lat,
        start_lng=city.lng,
        **weather,
    )


def _plan_week(monday: date, start: date, end: date) -> list[tuple[date, RunType]]:
    """One week's schedule: (date, type) pairs, race days excluded (added
    separately). Weekend long run, 1-2 quality sessions, easy/recovery
    fill, occasional rest weeks."""
    week_days = [monday + timedelta(days=i) for i in range(7)]
    race_day = next(
        (rd for rd, _, _ in RACES if rd in week_days), None
    )
    rest_week = race_day is None and random.random() < 0.12
    marathon_week = race_day == MARATHON_DATE
    post_marathon = MARATHON_DATE < monday <= MARATHON_DATE + timedelta(days=14)

    plan: list[tuple[date, RunType]] = []

    # Long run on Sat or Sun — skipped on race weeks (the race replaces it)
    if race_day is None:
        long_day = week_days[random.choice([5, 6])]
        plan.append((long_day, RunType.RECOVERY if post_marathon else RunType.LONG))

    # Quality: Tuesday, plus Thursday more often than not — none on rest,
    # race, or post-marathon weeks
    if not rest_week and race_day is None and not post_marathon:
        plan.append((week_days[1], random.choice([RunType.TEMPO, RunType.INTERVAL])))
        if random.random() < 0.55:
            plan.append(
                (week_days[3], random.choice([RunType.TEMPO, RunType.INTERVAL]))
            )

    # Fill with easy/recovery up to the week's run target
    target = 3 if (rest_week or marathon_week or post_marathon) else random.choice(
        [4, 4, 5, 5]
    )
    taken = {d for d, _ in plan} | ({race_day} if race_day else set())
    for day in (week_days[0], week_days[2], week_days[4], week_days[3]):
        if len(plan) + (1 if race_day else 0) >= target:
            break
        if day in taken:
            continue
        plan.append(
            (day, random.choices([RunType.EASY, RunType.RECOVERY], [0.78, 0.22])[0])
        )
        taken.add(day)

    return [(d, t) for d, t in plan if start <= d <= end]


def generate_dataset(
    user_id: UUID, start: date = DEMO_START, end: date | None = None
) -> tuple[list[Run], list[RunGlucoseSample], list[GlucoseDailyRecord]]:
    """The full deterministic dataset, in memory. Seeding the RNG from the
    fixed constant (plus user id, so concurrent test users get distinct
    generated PKs) makes two calls byte-identical."""
    end = end or date.today()
    random.seed(f"{GENERATION_SEED}-{user_id}")

    runs: list[Run] = []
    monday = start - timedelta(days=start.weekday())
    while monday <= end:
        for d, run_type in sorted(_plan_week(monday, start, end)):
            runs.append(_build_run(user_id, d, run_type))
        monday += timedelta(days=7)

    for race_date, distance_km, kind in RACES:
        if start <= race_date <= end:
            runs.append(
                _build_run(
                    user_id, race_date, RunType.RACE,
                    distance_km=distance_km, race_kind=kind,
                )
            )

    runs.sort(key=lambda r: (r.date, r.started_at))

    # Glucose: one baseline and one daily record per calendar day
    samples: list[RunGlucoseSample] = []
    daily_records: list[GlucoseDailyRecord] = []
    day_baselines: dict[date, float] = {}
    for i in range((end - start).days + 1):
        d = start + timedelta(days=i)
        day_baselines[d] = random.gauss(BASELINE_GLUCOSE_MEAN, BASELINE_GLUCOSE_STD)
        daily = _generate_daily_glucose_record(user_id, d, day_baselines[d])
        daily.source = DataSource.MANUAL
        daily_records.append(daily)

    for run in runs:
        run_samples, summary = _generate_glucose_for_run(run, day_baselines[run.date])
        for field, value in summary.items():
            setattr(run, field, value)
        for sample in run_samples:
            sample.source = DataSource.MANUAL  # synthetic, not device data
        samples.extend(run_samples)

    return runs, samples, daily_records


async def load_demo_data(session: AsyncSession, user_id: UUID) -> dict[str, int]:
    """Wipe the user's runs/glucose/briefs and load a fresh generation.
    Idempotent — deterministic generator in, same state out. Doesn't touch
    the global ask_demo_answers table (main() handles it)."""
    await session.execute(
        delete(GlucoseDailyRecord).where(GlucoseDailyRecord.user_id == user_id)
    )
    # Stale briefs would narrate the wiped dataset
    await session.execute(delete(DailyBrief).where(DailyBrief.user_id == user_id))
    # Cascades to run_glucose_samples and insights via FKs
    await session.execute(delete(Run).where(Run.user_id == user_id))

    runs, samples, daily_records = generate_dataset(user_id)

    session.add_all(runs)
    await session.flush()
    session.add_all(samples)
    session.add_all(daily_records)
    await session.commit()

    return {
        "runs": len(runs),
        "glucose_samples": len(samples),
        "daily_records": len(daily_records),
    }


async def main() -> None:
    user_id = get_settings().dev_user_id

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

        counts = await load_demo_data(session, user_id)
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
