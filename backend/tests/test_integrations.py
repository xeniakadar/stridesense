from datetime import UTC, date, datetime
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import ImportJob, Run
from app.models.enums import DataSource, ImportJobStatus, ImportJobType
from app.services.ingest import finish_job, start_job, upsert_run


def _run_values(external_id: str, distance_km: float) -> dict:
    return {
        "user_id": get_settings().dev_user_id,
        "source": DataSource.STRAVA,
        "external_id": external_id,
        "date": date.today(),
        "started_at": datetime.now(UTC),
        "distance_km": distance_km,
        "duration_seconds": 2700,
    }


async def test_upsert_run_is_idempotent(session: AsyncSession) -> None:
    external_id = f"test-{uuid4()}"
    try:
        await upsert_run(session, _run_values(external_id, 10.0))
        await upsert_run(session, _run_values(external_id, 12.5))
        await session.commit()

        result = await session.execute(
            select(Run).where(
                Run.source == DataSource.STRAVA, Run.external_id == external_id
            )
        )
        runs = result.scalars().all()
        assert len(runs) == 1
        assert runs[0].distance_km == 12.5
    finally:
        await session.execute(delete(Run).where(Run.external_id == external_id))
        await session.commit()


async def test_upsert_run_preserves_coordinates_when_new_value_is_null(
    session: AsyncSession, isolated_user
) -> None:
    """A later import with no GPS (e.g. a stale export missing its GPX
    route) must not blank out coordinates a prior import already set."""
    external_id = f"test-{uuid4()}"
    try:
        await upsert_run(
            session,
            _run_values(external_id, 10.0)
            | {"user_id": isolated_user.id, "start_lat": 47.51, "start_lng": 19.08},
        )
        await upsert_run(
            session,
            _run_values(external_id, 10.0)
            | {"user_id": isolated_user.id, "start_lat": None, "start_lng": None},
        )
        await session.commit()

        result = await session.execute(
            select(Run).where(
                Run.source == DataSource.STRAVA, Run.external_id == external_id
            )
        )
        run = result.scalar_one()
        assert run.start_lat == 47.51
        assert run.start_lng == 19.08

        # A genuine new value still wins over the preserved old one
        await upsert_run(
            session,
            _run_values(external_id, 10.0)
            | {"user_id": isolated_user.id, "start_lat": 38.71, "start_lng": -9.14},
        )
        await session.commit()
        await session.refresh(run)
        assert run.start_lat == 38.71
        assert run.start_lng == -9.14
    finally:
        await session.execute(delete(Run).where(Run.external_id == external_id))
        await session.commit()


async def test_job_lifecycle_and_listing(
    client: AsyncClient, session: AsyncSession
) -> None:
    job = await start_job(
        session,
        get_settings().dev_user_id,
        DataSource.STRAVA,
        ImportJobType.INITIAL_SYNC,
    )
    try:
        assert job.status == ImportJobStatus.RUNNING
        assert job.started_at is not None

        await finish_job(
            session, job, status=ImportJobStatus.COMPLETED, items_imported=3
        )
        assert job.finished_at is not None

        response = await client.get("/integrations/jobs")
        assert response.status_code == 200
        listed = next(j for j in response.json() if j["id"] == str(job.id))
        assert listed["status"] == "completed"
        assert listed["items_imported"] == 3
        assert listed["error_message"] is None
    finally:
        await session.execute(delete(ImportJob).where(ImportJob.id == job.id))
        await session.commit()
