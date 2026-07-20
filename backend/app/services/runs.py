from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Run
from app.models.enums import DataSource, RunTypeSource
from app.schemas.run import RunCreate, RunUpdate
from app.services.insights import invalidate_insights

# Fields whose change makes a cached insight's narration stale.
INSIGHT_RELEVANT_FIELDS = frozenset(
    {"run_type", "distance_km", "duration_seconds", "avg_hr", "max_hr"}
)


class RunNotFoundError(Exception):
    """Raised when a requested run doesn't exist or doesn't belong to the user."""

    def __init__(self, run_id: UUID):
        self.run_id = run_id
        super().__init__(f"Run {run_id} not found")


def _compute_pace_seconds_per_km(distance_km: float, duration_seconds: int) -> float | None:
    """Return pace in seconds per kilometer, or None if distance is zero."""
    if distance_km <= 0:
        return None
    return duration_seconds / distance_km


async def create_run(
    session: AsyncSession,
    user_id: UUID,
    payload: RunCreate,
) -> Run:
    """Create a manually-entered run for a user."""
    run = Run(
        user_id=user_id,
        source=DataSource.MANUAL,
        run_type_source=RunTypeSource.USER,
        avg_pace_seconds_per_km=_compute_pace_seconds_per_km(
            payload.distance_km, payload.duration_seconds
        ),
        **payload.model_dump(),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def get_run(session: AsyncSession, user_id: UUID, run_id: UUID) -> Run:
    """Fetch a single run by id, scoped to the user. Raises if not found."""
    result = await session.execute(
        select(Run).where(Run.id == run_id, Run.user_id == user_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise RunNotFoundError(run_id)
    return run


async def list_runs(
    session: AsyncSession,
    user_id: UUID,
    limit: int = 500,
) -> list[Run]:
    """Return the user's runs, most recent first."""
    result = await session.execute(
        select(Run)
        .where(Run.user_id == user_id)
        .order_by(Run.date.desc(), Run.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def update_run(
    session: AsyncSession,
    user_id: UUID,
    run_id: UUID,
    payload: RunUpdate,
) -> Run:
    """Apply a partial update to a run."""
    run = await get_run(session, user_id, run_id)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(run, field, value)

    # A manually chosen run_type is a permanent decision — it must never
    # be silently overwritten by a later classify_runs.py pass.
    if "run_type" in update_data:
        run.run_type_source = RunTypeSource.USER

    # Re-derive pace if distance or duration changed
    if "distance_km" in update_data or "duration_seconds" in update_data:
        run.avg_pace_seconds_per_km = _compute_pace_seconds_per_km(
            run.distance_km, run.duration_seconds
        )

    if INSIGHT_RELEVANT_FIELDS & update_data.keys():
        await invalidate_insights(session, run.id)

    await session.commit()
    await session.refresh(run)
    return run


async def delete_run(session: AsyncSession, user_id: UUID, run_id: UUID) -> None:
    """Delete a run. Raises if not found."""
    run = await get_run(session, user_id, run_id)
    await session.delete(run)
    await session.commit()
