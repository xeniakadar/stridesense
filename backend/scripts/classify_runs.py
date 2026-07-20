"""One-off: infer run_type for runs nobody ever classified.

For runs where run_type_source == DEFAULT (neither the source nor the
user ever said what kind of run this was), infers run_type from the
user's own pace/distance/HR distribution. Conservative by design: only
runs with a clear statistical signature get classified; everything
else is left OTHER for the user (or a future pass) to decide. Rows the
user classified themselves (run_type_source == USER) are never
touched — a manual choice is permanent (enforced separately: saving a
run_type through the edit form sets run_type_source=USER).

Classification order (first match wins):
  1. RACE     — distance matches a marathon (42.195km) or half
                (21.0975km) within a tight tolerance, regardless of pace.
  2. LONG     — distance is a clear outlier vs. the user's own history
                (z >= LONG_DISTANCE_Z).
  3. RECOVERY — pace is clearly slower than typical, distance is not a
                long run, and HR (if known) is not elevated.
  4. TEMPO    — pace is clearly faster than typical, HR (if known) is
                elevated, and it isn't simultaneously a long run.
  Anything else stays OTHER, untouched.

EASY and INTERVAL are deliberately never inferred. EASY was tried first
as "pace and distance both near the user's mean" — but the mean is, by
definition, where most of a runner's history sits: against the real
dev dataset that rule alone classified 81% of all runs, which is a
conservative classifier's opposite. A typical run isn't a *clear*
signal, it's the absence of one — indistinguishable from "unclassified"
without more context than pace/distance/HR provide. INTERVAL fails for
a different reason: a single average pace/HR number can't distinguish
interval work from sustained tempo without lap-level splits, which
this schema doesn't capture. Both would mean guessing, not inferring.

Dry run by default — prints the planned classifications for review.
Run with --apply to execute:

    docker compose exec backend uv run python -m scripts.classify_runs
    docker compose exec backend uv run python -m scripts.classify_runs --apply
"""

import asyncio
import sys
from statistics import mean, pstdev

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import Run
from app.models.enums import RunType, RunTypeSource
from app.services.insights import invalidate_insights

# Need a real distribution to z-score against — too few runs and every
# z-score is noise, not signal.
MIN_SAMPLE_SIZE = 8

MARATHON_KM = 42.195
HALF_MARATHON_KM = 21.0975
RACE_TOLERANCE_KM = 1.0
HALF_RACE_TOLERANCE_KM = 0.5

LONG_DISTANCE_Z = 1.5
RECOVERY_PACE_Z = 1.0
TEMPO_PACE_Z = -1.0
TEMPO_HR_Z = 0.5

Distribution = tuple[float, float]  # (mean, stddev)


def _z(value: float, dist: Distribution) -> float:
    m, sd = dist
    return (value - m) / sd


def _distribution(values: list[float]) -> Distribution | None:
    if len(values) < MIN_SAMPLE_SIZE:
        return None
    m = mean(values)
    sd = pstdev(values) or 1.0
    return m, sd


def classify(
    run: Run,
    pace_dist: Distribution | None,
    distance_dist: Distribution | None,
    hr_dist: Distribution | None,
) -> RunType | None:
    """Return the inferred RunType, or None to leave the run as OTHER."""
    if abs(run.distance_km - MARATHON_KM) <= RACE_TOLERANCE_KM:
        return RunType.RACE
    if abs(run.distance_km - HALF_MARATHON_KM) <= HALF_RACE_TOLERANCE_KM:
        return RunType.RACE

    if (
        distance_dist is None
        or pace_dist is None
        or run.avg_pace_seconds_per_km is None
    ):
        return None

    dist_z = _z(run.distance_km, distance_dist)
    pace_z = _z(run.avg_pace_seconds_per_km, pace_dist)
    hr_z = _z(run.avg_hr, hr_dist) if run.avg_hr is not None and hr_dist else None

    if dist_z >= LONG_DISTANCE_Z:
        return RunType.LONG

    if pace_z >= RECOVERY_PACE_Z and dist_z <= 0 and (hr_z is None or hr_z <= 0):
        return RunType.RECOVERY

    if (
        pace_z <= TEMPO_PACE_Z
        and dist_z <= LONG_DISTANCE_Z
        and (hr_z is None or hr_z >= TEMPO_HR_Z)
    ):
        return RunType.TEMPO

    return None


def _format_pace(seconds_per_km: float | None) -> str:
    if seconds_per_km is None:
        return "—"
    return f"{int(seconds_per_km // 60)}:{int(seconds_per_km % 60):02d}/km"


async def main() -> None:
    apply_changes = "--apply" in sys.argv
    user_id = get_settings().dev_user_id

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Run).where(Run.user_id == user_id))
        all_runs = list(result.scalars().all())

        pace_dist = _distribution(
            [r.avg_pace_seconds_per_km for r in all_runs if r.avg_pace_seconds_per_km]
        )
        distance_dist = _distribution([r.distance_km for r in all_runs])
        hr_dist = _distribution([r.avg_hr for r in all_runs if r.avg_hr])

        targets = [r for r in all_runs if r.run_type_source == RunTypeSource.DEFAULT]
        plan = [
            (run, inferred)
            for run in targets
            if (inferred := classify(run, pace_dist, distance_dist, hr_dist))
            is not None
        ]

        print(
            f"{len(all_runs)} total runs, {len(targets)} unclassified (DEFAULT), "
            f"{len(plan)} with a clear enough signature to infer\n"
        )
        if pace_dist is None or distance_dist is None:
            print(
                f"Fewer than {MIN_SAMPLE_SIZE} runs with pace/distance data — "
                "not enough history to classify confidently."
            )
            return
        if not plan:
            print("Nothing to do.")
            return

        print(f"{'date':<12} {'source':<14} {'distance':<10} {'pace':<10} run_type")
        print("-" * 62)
        for run, inferred in plan:
            print(
                f"{run.date.isoformat():<12} {run.source.value:<14} "
                f"{run.distance_km:<10.2f} {_format_pace(run.avg_pace_seconds_per_km):<10} "
                f"{inferred.value}"
            )

        if not apply_changes:
            print("\nDry run — nothing written. Re-run with --apply to execute.")
            return

        for run, inferred in plan:
            run.run_type = inferred
            run.run_type_source = RunTypeSource.INFERRED
            await invalidate_insights(session, run.id)
        await session.commit()
        print(f"\nApplied: {len(plan)} runs classified.")


if __name__ == "__main__":
    asyncio.run(main())
