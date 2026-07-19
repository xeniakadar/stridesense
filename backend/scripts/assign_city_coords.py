"""One-off: adopt city-level coordinates for runs missing a location.

For each run with null start_lat, find the nearest-in-time run within
±14 days that HAS coordinates and copy its rounded (city-level) coords,
nulling the run's weather columns so the next backfill refreshes them
with location-correct data. Runs with no anchor in the window stay
untouched.

Dry run by default — prints the planned adoptions for review.
Run with --apply to execute:

    docker compose exec backend uv run python -m scripts.assign_city_coords
    docker compose exec backend uv run python -m scripts.assign_city_coords --apply
"""

import asyncio
import sys

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import Run

ANCHOR_WINDOW_DAYS = 14

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

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Run)
            .where(Run.user_id == get_settings().dev_user_id)
            .order_by(Run.date)
        )
        runs = result.scalars().all()
        anchors = [r for r in runs if r.start_lat is not None and r.start_lng is not None]
        targets = [r for r in runs if r.start_lat is None]

        adoptions: list[tuple[Run, Run, int]] = []
        for run in targets:
            anchor = min(
                anchors,
                key=lambda a: abs((a.date - run.date).days),
                default=None,
            )
            if anchor is None:
                continue
            gap_days = abs((anchor.date - run.date).days)
            if gap_days > ANCHOR_WINDOW_DAYS:
                continue
            adoptions.append((run, anchor, gap_days))

        print(
            f"{len(runs)} runs, {len(anchors)} with coords, "
            f"{len(targets)} missing, {len(adoptions)} adoptable "
            f"(±{ANCHOR_WINDOW_DAYS}d window)\n"
        )
        if not adoptions:
            print("Nothing to do.")
            return

        print(f"{'run date':<12} {'source':<14} {'adopted city':<18} anchor")
        print("-" * 62)
        for run, anchor, gap_days in adoptions:
            coords = f"{round(anchor.start_lat, 2)}, {round(anchor.start_lng, 2)}"
            print(
                f"{run.date.isoformat():<12} {run.source.value:<14} "
                f"{coords:<18} {anchor.date.isoformat()} ({gap_days}d away)"
            )

        if not apply_changes:
            print("\nDry run — nothing written. Re-run with --apply to execute.")
            return

        for run, anchor, _ in adoptions:
            run.start_lat = round(anchor.start_lat, 2)
            run.start_lng = round(anchor.start_lng, 2)
            for column in WEATHER_COLUMNS:
                setattr(run, column, None)
        await session.commit()
        print(
            f"\nApplied: {len(adoptions)} runs updated and their weather "
            "cleared — run the weather backfill to refresh them."
        )


if __name__ == "__main__":
    asyncio.run(main())
