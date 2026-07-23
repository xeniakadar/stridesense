from collections import defaultdict
from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, get_session
from app.models import Run
from app.schemas.analytics import CitiesRead, CityStatsRead, LoadPointRead
from app.services import list_runs
from app.services.cities import cluster_cities
from app.services.training_load import compute_load_series

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/weekly-mileage")
async def weekly_mileage(
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> list[dict]:
    """Total km per ISO week for the last 12 weeks."""
    today = date.today()
    cutoff = today - timedelta(weeks=12)

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
    current_monday = today - timedelta(days=today.weekday())
    for i in range(11, -1, -1):
        week_start = current_monday - timedelta(weeks=i)
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
    """Average pace for easy runs over the last 90 days, by date."""
    cutoff = date.today() - timedelta(days=90)

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
    """Run-type breakdown for the last 30 days."""
    cutoff = date.today() - timedelta(days=30)

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
