"""Shared ingestion utilities: idempotent upserts and import-job tracking."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ImportJob, Run
from app.models.enums import DataSource, ImportJobStatus, ImportJobType


async def upsert_run(session: AsyncSession, values: dict[str, Any]) -> None:
    """Insert a run, or update it if (user_id, source, external_id) exists.

    Idempotent by design: re-importing the same activity refreshes its data
    instead of crashing or duplicating.
    """
    stmt = pg_insert(Run).values(**values)
    update_cols = {
        k: stmt.excluded[k]
        for k in values
        if k not in ("id", "user_id", "source", "external_id")
    }
    stmt = stmt.on_conflict_do_update(
        constraint="uq_runs_source_external",
        set_=update_cols,
    )
    await session.execute(stmt)


async def start_job(
    session: AsyncSession,
    user_id: UUID,
    source: DataSource,
    job_type: ImportJobType,
) -> ImportJob:
    job = ImportJob(
        user_id=user_id,
        source=source,
        job_type=job_type,
        status=ImportJobStatus.RUNNING,
        started_at=datetime.now(UTC),
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def finish_job(
    session: AsyncSession,
    job: ImportJob,
    *,
    status: ImportJobStatus,
    items_imported: int = 0,
    items_skipped_duplicates: int = 0,
    items_failed: int = 0,
    items_total: int | None = None,
    error: str | None = None,
) -> None:
    job.status = status
    job.items_imported = items_imported
    job.items_skipped_duplicates = items_skipped_duplicates
    job.items_failed = items_failed
    job.items_total = items_total
    job.error_message = error
    job.finished_at = datetime.now(UTC)
    await session.commit()
