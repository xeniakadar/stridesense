"""Streaming Apple Health export parser and import — workouts and glucose.

With Strava's API paywalled, Apple Health is the source for both: pass 1
extracts running Workouts, pass 2 extracts heart-rate and blood-glucose
Records and assigns them to the pass-1 workout windows. Both passes use
iterparse and clear as they go, so memory stays flat regardless of export
size.
"""

import asyncio
import shutil
import tempfile
import zipfile
from bisect import bisect_left, bisect_right
from collections import defaultdict
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any
from uuid import UUID
from xml.etree.ElementTree import Element, iterparse

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models import ImportJob, Run
from app.models.enums import DataSource, ImportJobStatus, RunType, RunTypeSource
from app.services.glucose import compute_daily_glucose, compute_glucose_summary
from app.services.ingest import (
    finish_job,
    upsert_glucose_daily,
    upsert_glucose_sample,
    upsert_run,
)

RUNNING_WORKOUT_TYPE = "HKWorkoutActivityTypeRunning"
HR_TYPE = "HKQuantityTypeIdentifierHeartRate"
GLUCOSE_TYPE = "HKQuantityTypeIdentifierBloodGlucose"
DISTANCE_STATISTIC = "HKQuantityTypeIdentifierDistanceWalkingRunning"
ENERGY_STATISTIC = "HKQuantityTypeIdentifierActiveEnergyBurned"
MMOL_TO_MGDL = 18.018
MILES_TO_KM = 1.609344
ADJACENT_WINDOW = timedelta(minutes=60)


def _iter_top_level(zip_path: Path) -> Iterator[Element]:
    """Yield each completed direct child of <HealthData>, keeping memory flat.

    Children of a yielded element (e.g. WorkoutStatistics inside Workout)
    are intact when it's yielded; after that the whole subtree is dropped
    via root.clear(), which also sheds the accumulated empty siblings.
    """
    with zipfile.ZipFile(zip_path) as zf:
        xml_name = next(n for n in zf.namelist() if n.endswith("export.xml"))
        with zf.open(xml_name) as xml_file:
            root: Element | None = None
            depth = 0
            for event, elem in iterparse(xml_file, events=("start", "end")):
                if event == "start":
                    if root is None:
                        root = elem
                    depth += 1
                    continue
                depth -= 1
                if depth == 1:
                    yield elem
                    root.clear()


def _parse_dt(raw: str) -> datetime:
    # Apple Health format: "2026-06-11 07:14:33 +0200"
    return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S %z")


def _to_km(value: float, unit: str) -> float:
    return value * MILES_TO_KM if unit.startswith("mi") else value


def _duration_seconds(raw: str, unit: str) -> float:
    value = float(raw)
    if unit.startswith("s"):
        return value
    if unit.startswith("h"):
        return value * 3600
    return value * 60  # Apple's default durationUnit is "min"


def parse_running_workouts(zip_path: Path) -> list[dict[str, Any]]:
    """Pass 1: running <Workout> elements, sorted by start time.

    Distance/energy live in attributes (older exports) or in child
    WorkoutStatistics elements (newer exports); both shapes are handled.
    """
    workouts: list[dict[str, Any]] = []
    for elem in _iter_top_level(zip_path):
        if elem.tag != "Workout":
            continue
        if elem.get("workoutActivityType") != RUNNING_WORKOUT_TYPE:
            continue
        started_at = _parse_dt(elem.get("startDate"))
        ended_at = _parse_dt(elem.get("endDate"))

        distance_km: float | None = None
        energy_kcal: float | None = None
        if elem.get("totalDistance"):
            distance_km = _to_km(
                float(elem.get("totalDistance")),
                elem.get("totalDistanceUnit", "km"),
            )
        if elem.get("totalEnergyBurned"):
            energy_kcal = float(elem.get("totalEnergyBurned"))
        for stat in elem.findall("WorkoutStatistics"):
            if stat.get("type") == DISTANCE_STATISTIC and stat.get("sum"):
                distance_km = _to_km(float(stat.get("sum")), stat.get("unit", "km"))
            elif stat.get("type") == ENERGY_STATISTIC and stat.get("sum"):
                energy_kcal = float(stat.get("sum"))

        raw_duration = elem.get("duration")
        duration = (
            _duration_seconds(raw_duration, elem.get("durationUnit", "min"))
            if raw_duration
            else (ended_at - started_at).total_seconds()
        )

        workouts.append(
            {
                "started_at": started_at,
                "ended_at": ended_at,
                "duration_seconds": int(duration),
                "distance_km": distance_km,
                "energy_kcal": energy_kcal,
                "source_name": elem.get("sourceName", ""),
                "raw": dict(elem.attrib),
            }
        )
    workouts.sort(key=lambda w: w["started_at"])
    return workouts


def _window_index(
    starts: list[datetime], ends: list[datetime], t: datetime
) -> int | None:
    i = bisect_right(starts, t) - 1
    if i >= 0 and t <= ends[i]:
        return i
    return None


def collect_records(
    zip_path: Path, windows: list[tuple[datetime, datetime]]
) -> tuple[dict[int, list[float]], list[tuple[datetime, float, str]]]:
    """Pass 2: stream <Record> elements once.

    Returns heart-rate values grouped by the workout-window index they fall
    in, and every glucose reading as (observed_at, mg/dL, source_name) —
    glucose is kept whole because daily records need out-of-window readings
    too. CGM volume is minute-level at most, so this stays small even when
    the export itself is hundreds of MB.
    """
    starts = [w[0] for w in windows]
    ends = [w[1] for w in windows]
    hr_by_window: dict[int, list[float]] = defaultdict(list)
    glucose: list[tuple[datetime, float, str]] = []

    for elem in _iter_top_level(zip_path):
        if elem.tag != "Record":
            continue
        record_type = elem.get("type")
        if record_type not in (HR_TYPE, GLUCOSE_TYPE):
            continue
        try:
            observed_at = _parse_dt(elem.get("startDate"))
            value = float(elem.get("value"))
        except (TypeError, ValueError):
            continue  # malformed record: skip, don't crash the import

        if record_type == HR_TYPE:
            index = _window_index(starts, ends, observed_at)
            if index is not None:
                hr_by_window[index].append(value)
        else:
            if "mmol" in elem.get("unit", "").lower():
                value *= MMOL_TO_MGDL
            glucose.append(
                (observed_at, round(value, 1), elem.get("sourceName", ""))
            )

    glucose.sort(key=lambda g: g[0])
    return hr_by_window, glucose


def _workout_source(source_name: str) -> DataSource:
    return (
        DataSource.GARMIN
        if "garmin" in source_name.lower()
        else DataSource.APPLE_HEALTH
    )


def _glucose_source(source_name: str) -> DataSource:
    return (
        DataSource.LINX_CGM
        if "linx" in source_name.lower()
        else DataSource.APPLE_HEALTH
    )


def _avg_in(
    glucose: list[tuple[datetime, float, str]],
    times: list[datetime],
    lo: datetime,
    hi: datetime,
) -> float | None:
    values = [v for _, v, _ in glucose[bisect_left(times, lo) : bisect_right(times, hi)]]
    return mean(values) if values else None


async def import_apple_health(job_id: UUID, zip_path: Path) -> None:
    """Background task: import runs and glucose from an Apple Health export.

    Opens its own session — the request's session is closed by the time
    this runs. Parsing is CPU-bound, so it happens in a thread.
    """
    async with AsyncSessionLocal() as session:
        job = await session.get(ImportJob, job_id)
        if job is None:
            return
        try:
            workouts = await asyncio.to_thread(parse_running_workouts, zip_path)
            windows = [(w["started_at"], w["ended_at"]) for w in workouts]
            hr_by_window, glucose = await asyncio.to_thread(
                collect_records, zip_path, windows
            )
            times = [t for t, _, _ in glucose]

            for i, workout in enumerate(workouts):
                hr = hr_by_window.get(i, [])
                distance = workout["distance_km"]
                await upsert_run(
                    session,
                    {
                        "user_id": job.user_id,
                        "source": _workout_source(workout["source_name"]),
                        "external_id": workout["started_at"].isoformat(),
                        "imported_at": datetime.now(UTC),
                        "date": workout["started_at"].date(),
                        "started_at": workout["started_at"],
                        "distance_km": round(distance, 2) if distance else 0.0,
                        "duration_seconds": workout["duration_seconds"],
                        "avg_pace_seconds_per_km": (
                            round(workout["duration_seconds"] / distance, 1)
                            if distance
                            else None
                        ),
                        "avg_hr": round(mean(hr)) if hr else None,
                        "max_hr": int(max(hr)) if hr else None,
                        "run_type": RunType.OTHER,
                        "run_type_source": RunTypeSource.DEFAULT,
                        "raw_title": None,
                        "raw_payload": workout["raw"],
                    },
                )
            await session.commit()

            result = await session.execute(
                select(Run).where(
                    Run.user_id == job.user_id,
                    Run.external_id.in_(
                        [w["started_at"].isoformat() for w in workouts]
                    ),
                )
            )
            runs_by_external_id = {r.external_id: r for r in result.scalars().all()}

            samples_written = 0
            for workout in workouts:
                run = runs_by_external_id[workout["started_at"].isoformat()]
                start, end = workout["started_at"], workout["ended_at"]
                during = glucose[bisect_left(times, start) : bisect_right(times, end)]
                for observed_at, mg_dl, source_name in during:
                    await upsert_glucose_sample(
                        session,
                        {
                            "run_id": run.id,
                            "elapsed_seconds": int(
                                (observed_at - start).total_seconds()
                            ),
                            "observed_at": observed_at,
                            "glucose_mg_dl": mg_dl,
                            "source": _glucose_source(source_name),
                        },
                    )
                    samples_written += 1
                # A window with zero readings simply gets no summary
                if during:
                    summary = compute_glucose_summary(
                        [v for _, v, _ in during],
                        pre_run_avg=_avg_in(
                            glucose, times, start - ADJACENT_WINDOW, start
                        ),
                        post_run_avg=_avg_in(
                            glucose, times, end, end + ADJACENT_WINDOW
                        ),
                    )
                    for field, value in summary.items():
                        setattr(run, field, value)

            daily_groups: dict[tuple[DataSource, Any], list[tuple[datetime, float]]]
            daily_groups = defaultdict(list)
            for observed_at, mg_dl, source_name in glucose:
                key = (_glucose_source(source_name), observed_at.date())
                daily_groups[key].append((observed_at, mg_dl))
            for (source, day), readings in daily_groups.items():
                await upsert_glucose_daily(
                    session,
                    {
                        "user_id": job.user_id,
                        "source": source,
                        "date": day,
                        **compute_daily_glucose(readings),
                    },
                )
            await session.commit()

            total = len(workouts) + samples_written + len(daily_groups)
            await finish_job(
                session,
                job,
                status=ImportJobStatus.COMPLETED,
                items_imported=total,
                items_total=total,
            )
        except Exception as e:
            await session.rollback()
            await finish_job(session, job, status=ImportJobStatus.FAILED, error=str(e))
        finally:
            # Remove the upload's mkdtemp dir — but never a path we don't own
            if Path(tempfile.gettempdir()) in zip_path.parent.parents:
                shutil.rmtree(zip_path.parent, ignore_errors=True)
