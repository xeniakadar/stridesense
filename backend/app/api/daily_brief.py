from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, get_session
from app.core.config import get_settings
from app.models import DailyBrief
from app.schemas.analytics import DailyBriefRead
from app.services.daily_brief import (
    DAILY_BRIEF_MODEL,
    gather_daily_data,
    generate_daily_brief,
)
from app.services.insights import InsightUnavailableError

router = APIRouter(prefix="/daily-brief", tags=["daily-brief"])


@router.get("", response_model=DailyBriefRead)
async def get_daily_brief(
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> DailyBriefRead:
    today = date.today()

    cached = await session.execute(
        select(DailyBrief).where(
            DailyBrief.user_id == user_id, DailyBrief.date == today
        )
    )
    row = cached.scalar_one_or_none()
    if row:
        return DailyBriefRead.model_validate(row)

    if get_settings().demo_mode:
        # Demo never generates live. Serve the newest pre-generated brief
        # (scripts/pregenerate_insights.py writes one at deploy time) even
        # if its date has slipped, else a friendly placeholder.
        latest = await session.execute(
            select(DailyBrief)
            .where(DailyBrief.user_id == user_id)
            .order_by(DailyBrief.date.desc())
        )
        newest = latest.scalars().first()
        if newest:
            return DailyBriefRead.model_validate(newest)
        return DailyBriefRead(
            date=today,
            content=(
                "The daily overview in this demo is pre-generated, and "
                "there isn't one yet."
            ),
            model="demo",
            created_at=datetime.now(UTC),
        )

    data = await gather_daily_data(session, user_id, today)
    if not data.has_anything():
        # Nothing to narrate — don't call the LLM, don't cache
        return DailyBriefRead(
            date=today,
            content=(
                "Not enough data for an overview yet — import some runs or "
                "connect Oura to get started."
            ),
            model=None,
            created_at=datetime.now(UTC),
        )

    try:
        content = await generate_daily_brief(data, today)
    except InsightUnavailableError as e:
        raise HTTPException(
            status_code=503, detail="Daily overview temporarily unavailable"
        ) from e

    brief = DailyBrief(
        user_id=user_id, date=today, content=content, model=DAILY_BRIEF_MODEL
    )
    session.add(brief)
    await session.commit()
    await session.refresh(brief)
    return DailyBriefRead.model_validate(brief)
