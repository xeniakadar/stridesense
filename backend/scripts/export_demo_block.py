"""Export the Oct 2025 marathon block to the committed demo fixture.

Exports the dev user's runs from BLOCK_START to BLOCK_END to
scripts/fixtures/demo_block.json — the dataset a public demo deployment
seeds from (see scripts/seed_demo.py). The fixture lives in a public
repo, so privacy is enforced structurally:

- Fields are WHITELISTED, never blacklisted: date, started_at, distance,
  duration, pace, avg HR, run type, coords, weather. raw_payload, notes,
  and external ids never enter the row dict at all.
- start_lat/lng are snapped to the nearest city-center coordinate
  (Lisbon / NYC / Chicago) — no full-precision home locations.

The exporter fails loudly with NO output file when any run in the range
is missing start_lat or still has run_type_source = 'DEFAULT': the block
must be fully located and classified (classify_runs.py or the edit UI)
before it can become the demo dataset.

    docker compose exec backend uv run python -m scripts.export_demo_block
"""

import asyncio
import json
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import Run
from app.models.enums import RunTypeSource

BLOCK_START = date(2025, 9, 15)
BLOCK_END = date(2025, 10, 19)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "demo_block.json"

# City centers the coordinates snap to — nothing more precise leaves the DB
CITY_CENTERS: dict[str, tuple[float, float]] = {
    "lisbon": (38.72, -9.14),
    "nyc": (40.78, -73.97),
    "chicago": (41.88, -87.62),
}

# The complete public surface of a fixture row. Anything not listed here
# does not exist in the export.
FIXTURE_FIELDS = (
    "date",
    "started_at",
    "distance_km",
    "duration_seconds",
    "avg_pace_seconds_per_km",
    "avg_hr",
    "run_type",
    "start_lat",
    "start_lng",
    "weather_temp_start_c",
    "weather_temp_end_c",
    "weather_temp_max_c",
    "weather_temp_min_c",
    "weather_apparent_temp_max_c",
    "weather_humidity_avg",
    "weather_wind_speed_avg_kmh",
    "weather_precipitation_total_mm",
)


def snap_to_city(lat: float, lng: float) -> tuple[float, float]:
    """The nearest city-center coordinate (squared-distance metric)."""
    return min(
        CITY_CENTERS.values(),
        key=lambda center: (lat - center[0]) ** 2 + (lng - center[1]) ** 2,
    )


def validate_block(runs: list[Run]) -> list[str]:
    """Every problem that blocks export, one line each. Empty = exportable."""
    errors: list[str] = []
    if not runs:
        errors.append("no runs in the export range")
    for run in runs:
        if run.start_lat is None or run.start_lng is None:
            errors.append(f"{run.date.isoformat()}: start_lat/lng is null — locate it first")
        if run.run_type_source == RunTypeSource.DEFAULT:
            errors.append(
                f"{run.date.isoformat()}: run_type_source is DEFAULT — classify it first"
            )
    return errors


def to_fixture_row(run: Run) -> dict:
    """One public fixture row. Built from scratch (whitelist), never by
    copying-and-deleting from the model."""
    lat, lng = snap_to_city(run.start_lat, run.start_lng)
    return {
        "date": run.date.isoformat(),
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "distance_km": run.distance_km,
        "duration_seconds": run.duration_seconds,
        "avg_pace_seconds_per_km": run.avg_pace_seconds_per_km,
        "avg_hr": run.avg_hr,
        "run_type": run.run_type.value,
        "start_lat": lat,
        "start_lng": lng,
        "weather_temp_start_c": run.weather_temp_start_c,
        "weather_temp_end_c": run.weather_temp_end_c,
        "weather_temp_max_c": run.weather_temp_max_c,
        "weather_temp_min_c": run.weather_temp_min_c,
        "weather_apparent_temp_max_c": run.weather_apparent_temp_max_c,
        "weather_humidity_avg": run.weather_humidity_avg,
        "weather_wind_speed_avg_kmh": run.weather_wind_speed_avg_kmh,
        "weather_precipitation_total_mm": run.weather_precipitation_total_mm,
    }


def build_fixture(runs: list[Run]) -> list[dict]:
    """Validate the whole block, then map it. Raises before producing any
    output when the block isn't export-ready — no partial fixtures."""
    errors = validate_block(runs)
    if errors:
        raise ValueError(
            "Block is not export-ready:\n  " + "\n  ".join(errors)
        )
    return [to_fixture_row(r) for r in sorted(runs, key=lambda r: r.date)]


async def main() -> None:
    user_id = get_settings().dev_user_id

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Run).where(
                Run.user_id == user_id,
                Run.date >= BLOCK_START,
                Run.date <= BLOCK_END,
            )
        )
        runs = list(result.scalars().all())

    print(f"{len(runs)} runs in {BLOCK_START} .. {BLOCK_END}")
    try:
        rows = build_fixture(runs)
    except ValueError as e:
        print(f"\n{e}\nNothing written.")
        sys.exit(1)

    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(json.dumps(rows, indent=2) + "\n")
    print(f"Wrote {len(rows)} runs to {FIXTURE_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
