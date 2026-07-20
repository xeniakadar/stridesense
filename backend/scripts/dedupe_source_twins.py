"""One-off: retroactively merge cross-source duplicate runs already imported.

The generalized dedupe in the Apple Health import (SOURCE_PRIORITY +
window clustering) only guards future imports; it can't undo rows from
before the fix. This applies the identical rule directly to `runs`:
group by overlapping time windows across DIFFERENT sources, keep the
highest-priority one (GARMIN > STRAVA > APPLE_HEALTH > OURA), adopt
coordinates from a dropped duplicate if the kept run lacks them, and
delete the rest.

Dry run by default — prints the planned merges for review.
Run with --apply to execute:

    docker compose exec backend uv run python -m scripts.dedupe_source_twins
    docker compose exec backend uv run python -m scripts.dedupe_source_twins --apply
"""

import asyncio
import sys
from datetime import timedelta
from uuid import UUID

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import Run
from app.models.enums import DataSource
from app.services.apple_health import SOURCE_PRIORITY, _duplicate_window


def _window_gap(a: Run, b: Run) -> timedelta:
    a_end = a.started_at + timedelta(seconds=a.duration_seconds)
    b_end = b.started_at + timedelta(seconds=b.duration_seconds)
    return max(a.started_at - b_end, b.started_at - a_end, timedelta(0))


def _cluster(runs: list[Run]) -> list[list[int]]:
    n = len(runs)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    for i in range(n):
        for j in range(i + 1, n):
            if (
                runs[i].source != runs[j].source
                and runs[i].date == runs[j].date
                and _window_gap(runs[i], runs[j])
                <= _duplicate_window(runs[i].source, runs[j].source)
            ):
                union(i, j)

    clusters: dict[int, list[int]] = {}
    for i in range(n):
        clusters.setdefault(find(i), []).append(i)
    return [c for c in clusters.values() if len(c) > 1]


WEATHER_COLUMNS = (
    "weather_temp_start_c",
    "weather_temp_end_c",
    "weather_temp_max_c",
    "weather_temp_min_c",
    "weather_apparent_temp_max_c",
    "weather_humidity_avg",
    "weather_wind_speed_avg_kmh",
    "weather_precipitation_total_mm",
)


async def main() -> None:
    apply_changes = "--apply" in sys.argv
    user_id: UUID = get_settings().dev_user_id

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Run)
            .where(Run.user_id == user_id, Run.source != DataSource.MANUAL)
            .order_by(Run.date)
        )
        runs = list(result.scalars().all())
        clusters = _cluster(runs)

        print(f"{len(runs)} imported runs, {len(clusters)} duplicate cluster(s)\n")
        if not clusters:
            print("Nothing to do.")
            return

        print(f"{'date':<12} {'keep':<8} {'drop':<20} coords adopted")
        print("-" * 62)
        plan = []
        for cluster in clusters:
            members = sorted(
                (runs[i] for i in cluster),
                key=lambda r: SOURCE_PRIORITY[r.source],
            )
            winner, losers = members[0], members[1:]
            adopted = None
            if winner.start_lat is None:
                donor = next((r for r in losers if r.start_lat is not None), None)
                if donor is not None:
                    adopted = (donor.start_lat, donor.start_lng)
            plan.append((winner, losers, adopted))
            print(
                f"{winner.date.isoformat():<12} {winner.source.value:<8} "
                f"{','.join(loser.source.value for loser in losers):<20} "
                f"{adopted if adopted else ''}"
            )

        total_dropped = sum(len(losers) for _, losers, _ in plan)
        print(f"\n{len(plan)} runs kept, {total_dropped} duplicate rows to delete.")

        if not apply_changes:
            print("\nDry run — nothing written. Re-run with --apply to execute.")
            return

        for winner, losers, adopted in plan:
            if adopted is not None:
                winner.start_lat, winner.start_lng = adopted
                for column in WEATHER_COLUMNS:
                    setattr(winner, column, None)
            await session.execute(delete(Run).where(Run.id.in_(loser.id for loser in losers)))
        await session.commit()
        print(
            f"\nApplied: {total_dropped} duplicate runs deleted. Run the weather "
            "backfill to refresh any runs whose coordinates changed."
        )


if __name__ == "__main__":
    asyncio.run(main())
