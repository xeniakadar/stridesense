from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, get_session
from app.models import ImportJob
from app.models.enums import DataSource, ImportJobType
from app.schemas.integrations import ImportJobRead
from app.services.ingest import start_job
from app.services.oura import sync_oura
from app.services.weather import backfill_weather

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.post("/weather/backfill", status_code=status.HTTP_202_ACCEPTED)
async def weather_backfill_endpoint(
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> dict[str, str]:
    job = await start_job(
        session, user_id, DataSource.OPEN_METEO, ImportJobType.INCREMENTAL_SYNC
    )
    background_tasks.add_task(backfill_weather, job.id)
    return {"job_id": str(job.id)}


@router.post("/oura/sync", status_code=status.HTTP_202_ACCEPTED)
async def oura_sync_endpoint(
    background_tasks: BackgroundTasks,
    start_date: date | None = None,
    end_date: date | None = None,
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> dict[str, str]:
    end = end_date or date.today()
    start = start_date or end - timedelta(days=30)
    job = await start_job(
        session, user_id, DataSource.OURA, ImportJobType.INCREMENTAL_SYNC
    )
    background_tasks.add_task(sync_oura, job.id, start, end)
    return {"job_id": str(job.id)}


@router.get("/jobs", response_model=list[ImportJobRead])
async def list_jobs_endpoint(
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
    limit: int = 20,
) -> list[ImportJobRead]:
    result = await session.execute(
        select(ImportJob)
        .where(ImportJob.user_id == user_id)
        .order_by(ImportJob.created_at.desc())
        .limit(limit)
    )
    return [ImportJobRead.model_validate(j) for j in result.scalars().all()]
