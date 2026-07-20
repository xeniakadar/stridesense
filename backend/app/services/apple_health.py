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
from xml.etree.ElementTree import Element, ParseError, iterparse

from sqlalchemy import delete, select

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


def _gpx_start_coords(
    zf: zipfile.ZipFile, names: list[str], path: str
) -> tuple[float, float] | None:
    """First trackpoint of a linked GPX route, rounded to ~1km.

    Privacy: only the first trkpt is read and only 2-decimal coordinates
    leave this function — full-precision tracks are never stored. A
    missing or malformed route file yields None, never an error.
    """
    member = next((n for n in names if n.endswith(path.lstrip("/"))), None)
    if member is None:
        return None
    try:
        with zf.open(member) as gpx_file:
            for _, elem in iterparse(gpx_file, events=("start",)):
                if elem.tag.rsplit("}", 1)[-1] == "trkpt":
                    return (
                        round(float(elem.get("lat")), 2),
                        round(float(elem.get("lon")), 2),
                    )
    except (ParseError, TypeError, ValueError):
        return None
    return None


def parse_running_workouts(zip_path: Path) -> list[dict[str, Any]]:
    """Pass 1: running <Workout> elements, sorted by start time.

    Distance/energy live in attributes (older exports) or in child
    WorkoutStatistics elements (newer exports); both shapes are handled.
    A child WorkoutRoute's GPX supplies rounded start coordinates.
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

        route = elem.find("WorkoutRoute/FileReference")
        workouts.append(
            {
                "started_at": started_at,
                "ended_at": ended_at,
                "duration_seconds": int(duration),
                "distance_km": distance_km,
                "energy_kcal": energy_kcal,
                "source_name": elem.get("sourceName", ""),
                "route_path": route.get("path") if route is not None else None,
                "start_lat": None,
                "start_lng": None,
                "raw": dict(elem.attrib),
            }
        )

    if any(w["route_path"] for w in workouts):
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            for workout in workouts:
                if not workout["route_path"]:
                    continue
                coords = _gpx_start_coords(zf, names, workout["route_path"])
                if coords is not None:
                    workout["start_lat"], workout["start_lng"] = coords

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
) -> tuple[dict[int, dict[str, list[float]]], list[tuple[datetime, float, str]]]:
    """Pass 2: stream <Record> elements once.

    Heart-rate values are grouped by workout-window index AND sourceName:
    a run's HR must come from the device that recorded the workout, never
    averaged across devices (a Garmin marathon at ~159 bpm was dragged to
    138 by Oura ring records sharing the window). Glucose is kept whole as
    (observed_at, mg/dL, source_name) because daily records need
    out-of-window readings too; CGM volume is minute-level at most, so
    this stays small even when the export itself is hundreds of MB.
    """
    starts = [w[0] for w in windows]
    ends = [w[1] for w in windows]
    hr_by_window: dict[int, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
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
                hr_by_window[index][elem.get("sourceName", "")].append(value)
        else:
            if "mmol" in elem.get("unit", "").lower():
                value *= MMOL_TO_MGDL
            glucose.append(
                (observed_at, round(value, 1), elem.get("sourceName", ""))
            )

    glucose.sort(key=lambda g: g[0])
    return hr_by_window, glucose


def _workout_source(source_name: str) -> DataSource:
    """Real export sourceNames: "Connect" is Garmin's app; Strava and Oura
    write under their own names; watches and run apps ("Xenia's Apple
    Watch", "Nike Run Club", "5K Runner") stay APPLE_HEALTH."""
    name = source_name.lower()
    if "garmin" in name or "connect" in name:
        return DataSource.GARMIN
    if "strava" in name:
        return DataSource.STRAVA
    if "oura" in name:
        return DataSource.OURA
    return DataSource.APPLE_HEALTH


def _window_gap(a: dict[str, Any], b: dict[str, Any]) -> timedelta:
    """Time between two workout windows; zero when they overlap."""
    return max(
        a["started_at"] - b["ended_at"],
        b["started_at"] - a["ended_at"],
        timedelta(0),
    )


# Highest priority first: the watch/app that actually recorded the run
# beats a phone-app upload, which beats an auto-detected guess.
SOURCE_PRIORITY: dict[DataSource, int] = {
    DataSource.GARMIN: 0,
    DataSource.STRAVA: 1,
    DataSource.APPLE_HEALTH: 2,
    DataSource.OURA: 3,
}

# Device-recorded twins (Garmin/Strava/AppleHealth all uploading the same
# watch recording) share near-identical timestamps — seconds of clock
# skew, confirmed against the real export, never more. Only Oura's
# auto-detection is imprecise enough to need the wide ADJACENT_WINDOW.
DEVICE_TWIN_WINDOW = timedelta(minutes=5)


def _duplicate_window(source_a: DataSource, source_b: DataSource) -> timedelta:
    return ADJACENT_WINDOW if DataSource.OURA in (source_a, source_b) else DEVICE_TWIN_WINDOW


def _cluster_duplicate_workouts(workouts: list[dict[str, Any]]) -> list[list[int]]:
    """Group workout indices that are the same physical run on different devices.

    Two workouts from DIFFERENT sources on the same date, within
    _duplicate_window() of each other, are the same run seen twice.
    Workouts from the SAME source are never merged this way — a second
    run by the same device on the same day is a real second run, not a
    duplicate. Union-find, so a chain of near-matches collapses
    transitively into one cluster — but the tight non-Oura window keeps
    that chain from snagging an unrelated same-source run that happens to
    fall within Oura's wider tolerance of a shared neighbor (a real
    export had two distinct Garmin runs an hour apart, one of which had
    a Strava twin; a single shared window size would have merged both
    Garmin runs into one and silently dropped a real workout).
    """
    n = len(workouts)
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
            si = _workout_source(workouts[i]["source_name"])
            sj = _workout_source(workouts[j]["source_name"])
            if (
                si != sj
                and workouts[i]["started_at"].date() == workouts[j]["started_at"].date()
                and _window_gap(workouts[i], workouts[j]) <= _duplicate_window(si, sj)
            ):
                union(i, j)

    clusters: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        clusters[find(i)].append(i)
    return list(clusters.values())


def _merge_duplicate_workouts(
    workouts: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Collapse same-run duplicates across devices to the highest-priority source.

    Within each cluster (see _cluster_duplicate_workouts), keep the
    highest-SOURCE_PRIORITY workout. If it has no GPS — real Garmin
    ("Connect") exports usually carry no WorkoutRoute — adopt rounded
    coordinates from whichever dropped duplicate does have them (Strava,
    a watch, or Oura routes for the same run often do). Dropped entries
    are never imported; the caller counts them as skipped duplicates.
    """
    kept: list[dict[str, Any]] = []
    dropped = 0
    for cluster in _cluster_duplicate_workouts(workouts):
        if len(cluster) == 1:
            kept.append(workouts[cluster[0]])
            continue
        cluster.sort(
            key=lambda i: SOURCE_PRIORITY[_workout_source(workouts[i]["source_name"])]
        )
        winner = workouts[cluster[0]]
        if winner["start_lat"] is None:
            for i in cluster[1:]:
                if workouts[i]["start_lat"] is not None:
                    winner["start_lat"] = workouts[i]["start_lat"]
                    winner["start_lng"] = workouts[i]["start_lng"]
                    break
        kept.append(winner)
        dropped += len(cluster) - 1
    kept.sort(key=lambda w: w["started_at"])
    return kept, dropped


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
            # Self-heal: earlier imports could leave distance <= 0 runs that
            # break RunRead serialization; a re-upload clears them
            await session.execute(
                delete(Run).where(Run.user_id == job.user_id, Run.distance_km <= 0)
            )
            await session.commit()

            parsed = await asyncio.to_thread(parse_running_workouts, zip_path)
            deduped, duplicates = _merge_duplicate_workouts(parsed)
            # A workout whose distance is missing, zero, negative, or so
            # small it rounds to the stored 0.0 can't satisfy the run
            # schema (distance_km > 0) — count it, skip it
            workouts = [
                w
                for w in deduped
                if w["distance_km"] is not None and round(w["distance_km"], 2) > 0
            ]
            skipped = len(deduped) - len(workouts)
            windows = [(w["started_at"], w["ended_at"]) for w in workouts]
            hr_by_window, glucose = await asyncio.to_thread(
                collect_records, zip_path, windows
            )
            times = [t for t, _, _ in glucose]

            for i, workout in enumerate(workouts):
                # Same-source only: HR from the device that recorded the run
                hr = hr_by_window.get(i, {}).get(workout["source_name"], [])
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
                        "distance_km": round(distance, 2),
                        "duration_seconds": workout["duration_seconds"],
                        "avg_pace_seconds_per_km": round(
                            workout["duration_seconds"] / distance, 1
                        ),
                        "avg_hr": round(mean(hr)) if hr else None,
                        "max_hr": int(max(hr)) if hr else None,
                        "start_lat": workout["start_lat"],
                        "start_lng": workout["start_lng"],
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

            imported = len(workouts) + samples_written + len(daily_groups)
            await finish_job(
                session,
                job,
                status=ImportJobStatus.COMPLETED,
                items_imported=imported,
                items_total=imported + skipped + duplicates,
                items_skipped_duplicates=duplicates,
            )
        except Exception as e:
            await session.rollback()
            await finish_job(session, job, status=ImportJobStatus.FAILED, error=str(e))
        finally:
            # Remove the upload's mkdtemp dir — but never a path we don't own
            if Path(tempfile.gettempdir()) in zip_path.parent.parents:
                shutil.rmtree(zip_path.parent, ignore_errors=True)
