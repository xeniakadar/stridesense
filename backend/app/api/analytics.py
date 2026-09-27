from collections import defaultdict
from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, get_session
from app.models import GlucoseDailyRecord, Run
from app.schemas.analytics import (
    CitiesRead,
    CityStatsRead,
    GlucoseTrendPoint,
    LoadPointRead,
    MonthlyVolumePoint,
    RecordRead,
)
from app.services import latest_run_date, list_runs
from app.services.cities import cluster_cities
from app.services.records import compute_records
from app.services.training_load import compute_load_series

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/weekly-mileage")
async def weekly_mileage(
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> list[dict]:
    """Total km per ISO week for the 12 weeks ending in the week of the
    user's latest run (see latest_run_date)."""
    anchor = await latest_run_date(session, user_id)
    anchor_monday = anchor - timedelta(days=anchor.weekday())
    cutoff = anchor_monday - timedelta(weeks=11)

    result = await session.execute(
        select(Run).where(Run.user_id == user_id, Run.date >= cutoff)
    )
    runs = result.scalars().all()

    # Group by Monday of each ISO week
    by_week: dict[date, float] = defaultdict(float)
    for r in runs:
        monday = r.date - timedelta(days=r.date.weekday())
        by_week[monday] += r.distance_km

    # Fill in empty weeks so the chart doesn't have gaps
    output = []
    for i in range(11, -1, -1):
        week_start = anchor_monday - timedelta(weeks=i)
        output.append(
            {
                "week_start": week_start.isoformat(),
                "distance_km": round(by_week.get(week_start, 0.0), 2),
            }
        )

    return output


@router.get("/pace-trend")
async def pace_trend(
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> list[dict]:
    """Average pace for easy runs over the 90 days ending at the user's
    latest run, by date."""
    anchor = await latest_run_date(session, user_id)
    cutoff = anchor - timedelta(days=90)

    result = await session.execute(
        select(Run).where(
            Run.user_id == user_id,
            Run.date >= cutoff,
            Run.run_type == "easy",
            Run.avg_pace_seconds_per_km.isnot(None),
        ).order_by(Run.date)
    )
    runs = result.scalars().all()

    return [
        {
            "date": r.date.isoformat(),
            "pace_seconds_per_km": round(r.avg_pace_seconds_per_km, 1),
        }
        for r in runs
    ]


@router.get("/run-type-distribution")
async def run_type_distribution(
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> list[dict]:
    """Run-type breakdown for the 30 days ending at the user's latest run."""
    anchor = await latest_run_date(session, user_id)
    cutoff = anchor - timedelta(days=30)

    result = await session.execute(
        select(Run).where(Run.user_id == user_id, Run.date >= cutoff)
    )
    runs = result.scalars().all()

    grouped: dict[str, dict[str, float]] = defaultdict(
        lambda: {"count": 0, "total_distance_km": 0.0}
    )
    for r in runs:
        grouped[r.run_type]["count"] += 1
        grouped[r.run_type]["total_distance_km"] += r.distance_km

    return [
        {
            "run_type": run_type,
            "count": int(data["count"]),
            "total_distance_km": round(data["total_distance_km"], 2),
        }
        for run_type, data in sorted(grouped.items(), key=lambda x: -x[1]["count"])
    ]


@router.get("/monthly-volume", response_model=list[MonthlyVolumePoint])
async def monthly_volume(
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> list[MonthlyVolumePoint]:
    """Total km per calendar month for the 12 months ending in the month of
    the user's latest run, empty months included."""
    anchor = await latest_run_date(session, user_id)
    months: list[date] = []
    year, month = anchor.year, anchor.month
    for _ in range(12):
        months.append(date(year, month, 1))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    months.reverse()

    result = await session.execute(
        select(Run).where(Run.user_id == user_id, Run.date >= months[0])
    )
    by_month: dict[date, float] = defaultdict(float)
    for r in result.scalars().all():
        by_month[date(r.date.year, r.date.month, 1)] += r.distance_km

    return [
        MonthlyVolumePoint(month=m, distance_km=round(by_month.get(m, 0.0), 2))
        for m in months
    ]


@router.get("/records", response_model=list[RecordRead])
async def records_endpoint(
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> list[RecordRead]:
    result = await session.execute(select(Run).where(Run.user_id == user_id))
    runs = list(result.scalars().all())
    return [RecordRead.model_validate(r) for r in compute_records(runs)]


@router.get("/glucose-trend", response_model=list[GlucoseTrendPoint])
async def glucose_trend(
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> list[GlucoseTrendPoint]:
    """Daily time-in-range % for the 90 days ending at the user's latest
    run; empty when the user has no glucose data at all."""
    anchor = await latest_run_date(session, user_id)
    cutoff = anchor - timedelta(days=90)
    result = await session.execute(
        select(GlucoseDailyRecord)
        .where(
            GlucoseDailyRecord.user_id == user_id,
            GlucoseDailyRecord.date >= cutoff,
            GlucoseDailyRecord.time_in_range_pct.isnot(None),
        )
        .order_by(GlucoseDailyRecord.date)
    )
    return [
        GlucoseTrendPoint(date=rec.date, time_in_range_pct=rec.time_in_range_pct)
        for rec in result.scalars().all()
    ]


@router.get("/cities", response_model=CitiesRead)
async def cities_endpoint(
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> CitiesRead:
    result = await session.execute(select(Run).where(Run.user_id == user_id))
    runs = list(result.scalars().all())
    cities, unlocated_count = cluster_cities(runs)
    return CitiesRead(
        cities=[CityStatsRead.model_validate(c) for c in cities],
        unlocated_count=unlocated_count,
    )


@router.get("/training-load", response_model=list[LoadPointRead])
async def training_load_endpoint(
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> list[LoadPointRead]:
    runs = await list_runs(session, user_id, limit=1000)
    series = compute_load_series(runs)
    return [LoadPointRead(**vars(p)) for p in series]
