from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, get_session
from app.models import ImportJob
from app.schemas.integrations import ImportJobRead

router = APIRouter(prefix="/integrations", tags=["integrations"])


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
