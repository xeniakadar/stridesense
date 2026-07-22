from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, get_session
from app.core.config import get_settings
from app.models import Insight, Run, RunGlucoseSample
from app.schemas.analytics import (
    ComparisonRead,
    GlucoseSampleRead,
    InsightRead,
    SimilarRunRead,
    SimilarRunsRead,
)
from app.schemas.run import RunCreate, RunRead, RunUpdate
from app.services import (
    RunNotFoundError,
    create_run,
    delete_run,
    get_run,
    list_runs,
    update_run,
)
from app.services.insights import (
    INSIGHT_MODEL,
    InsightUnavailableError,
    generate_insight,
    invalidate_insights,
)
from app.services.similarity import (
    compare_to_similar,
    find_similar_runs,
    find_similar_runs_detailed,
)
from app.services.training_load import acwr_for_run

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunRead, status_code=status.HTTP_201_CREATED)
async def create_run_endpoint(
    payload: RunCreate,
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> RunRead:
    run = await create_run(session, user_id, payload)
    return RunRead.model_validate(run)


@router.get("", response_model=list[RunRead])
async def list_runs_endpoint(
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> list[RunRead]:
    runs = await list_runs(session, user_id)
    return [RunRead.model_validate(r) for r in runs]


@router.get("/{run_id}", response_model=RunRead)
async def get_run_endpoint(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> RunRead:
    try:
        run = await get_run(session, user_id, run_id)
    except RunNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return RunRead.model_validate(run)


@router.get("/{run_id}/similar", response_model=SimilarRunsRead)
async def get_similar_runs_endpoint(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
    limit: int = 5,
) -> SimilarRunsRead:
    target = await get_run(session, user_id, run_id)
    candidates = await list_runs(session, user_id, limit=500)
    pool = find_similar_runs_detailed(target, candidates, limit=limit)
    comparison = compare_to_similar(target, pool.runs)
    return SimilarRunsRead(
        runs=[
            SimilarRunRead(
                run_id=s.run.id,
                date=s.run.date,
                run_type=s.run.run_type,
                distance_km=s.run.distance_km,
                avg_pace_seconds_per_km=s.run.avg_pace_seconds_per_km,
                weather_temp_start_c=s.run.weather_temp_start_c,
                score=round(s.score, 3),
            )
            for s in pool.runs
        ],
        pool_size=pool.pool_size,
        type_fallback=pool.type_fallback,
        comparison=ComparisonRead(**vars(comparison)) if comparison else None,
    )

@router.get("/{run_id}/glucose-samples", response_model=list[GlucoseSampleRead])
async def get_glucose_samples_endpoint(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> list[GlucoseSampleRead]:
    try:
        await get_run(session, user_id, run_id)
    except RunNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    result = await session.execute(
        select(RunGlucoseSample)
        .where(RunGlucoseSample.run_id == run_id)
        .order_by(RunGlucoseSample.elapsed_seconds)
    )
    return [GlucoseSampleRead.model_validate(s) for s in result.scalars().all()]


@router.put("/{run_id}", response_model=RunRead)
async def update_run_endpoint(
    run_id: UUID,
    payload: RunUpdate,
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> RunRead:
    try:
        run = await update_run(session, user_id, run_id, payload)
    except RunNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return RunRead.model_validate(run)


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_run_endpoint(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> None:
    try:
        await delete_run(session, user_id, run_id)
    except RunNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

async def _generate_and_cache_insight(
    session: AsyncSession, user_id: UUID, run: Run, run_id: UUID
) -> Insight:
    candidates = await list_runs(session, user_id, limit=500)
    similar = find_similar_runs(run, candidates, limit=5)
    load = acwr_for_run(run, candidates)

    try:
        content = await generate_insight(run, similar, load)
    except InsightUnavailableError as e:
        raise HTTPException(
            status_code=503, detail="Insight temporarily unavailable"
        ) from e

    insight = Insight(run_id=run_id, content=content, model=INSIGHT_MODEL)
    session.add(insight)
    await session.commit()
    await session.refresh(insight)
    return insight


@router.get("/{run_id}/insight", response_model=InsightRead)
async def get_insight_endpoint(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> InsightRead:
    try:
        run = await get_run(session, user_id, run_id)
    except RunNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    existing = await session.execute(
        select(Insight)
        .where(Insight.run_id == run_id)
        .order_by(Insight.created_at.desc())
    )
    cached = existing.scalars().first()
    if cached:
        return InsightRead.model_validate(cached)

    if get_settings().demo_mode:
        # Demo never generates on demand — insights are pre-generated at
        # deploy time by scripts/pregenerate_insights.py. A run without one
        # gets a friendly explanation instead of an LLM call (not persisted).
        return InsightRead(
            id=uuid4(),
            run_id=run_id,
            content=(
                "Insights in this demo are pre-generated, and this run "
                "doesn't have one yet."
            ),
            model="demo",
            created_at=datetime.now(UTC),
        )

    insight = await _generate_and_cache_insight(session, user_id, run, run_id)
    return InsightRead.model_validate(insight)


@router.post("/{run_id}/insight/regenerate", response_model=InsightRead)
async def regenerate_insight_endpoint(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> InsightRead:
    try:
        run = await get_run(session, user_id, run_id)
    except RunNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    await invalidate_insights(session, run_id)
    await session.commit()

    insight = await _generate_and_cache_insight(session, user_id, run, run_id)
    return InsightRead.model_validate(insight)
