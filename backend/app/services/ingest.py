"""Shared ingestion utilities: idempotent upserts and import-job tracking."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.models import GlucoseDailyRecord, ImportJob, Run, RunGlucoseSample, SleepRecord
from app.models.enums import DataSource, ImportJobStatus, ImportJobType


async def _upsert_on_constraint(
    session: AsyncSession,
    model: type[Base],
    values: dict[str, Any],
    constraint: str,
    conflict_keys: tuple[str, ...],
    preserve_existing: tuple[str, ...] = (),
) -> None:
    """Insert a row, or refresh every non-key column on conflict.

    Idempotent by design: re-importing the same record refreshes its data
    instead of crashing or duplicating.

    `preserve_existing` columns are COALESCEd instead of overwritten: a
    fresh None never clobbers a value the row already has (e.g. a stale
    export with a missing GPX route must not blank out coordinates a
    prior import or the city-adoption script already set). A real,
    non-null new value still wins.
    """
    stmt = pg_insert(model).values(**values)
    update_cols: dict[str, Any] = {}
    for k in values:
        if k in ("id", *conflict_keys):
            continue
        if k in preserve_existing:
            update_cols[k] = func.coalesce(stmt.excluded[k], getattr(model, k))
        else:
            update_cols[k] = stmt.excluded[k]
    stmt = stmt.on_conflict_do_update(constraint=constraint, set_=update_cols)
    await session.execute(stmt)


async def upsert_run(session: AsyncSession, values: dict[str, Any]) -> None:
    """Insert a run, or update it if (user_id, source, external_id) exists."""
    await _upsert_on_constraint(
        session,
        Run,
        values,
        constraint="uq_runs_source_external",
        conflict_keys=("user_id", "source", "external_id"),
        preserve_existing=("start_lat", "start_lng"),
    )


async def upsert_sleep_record(session: AsyncSession, values: dict[str, Any]) -> None:
    """Insert a sleep record, or update it if (user_id, source, date) exists."""
    await _upsert_on_constraint(
        session,
        SleepRecord,
        values,
        constraint="uq_sleep_user_source_date",
        conflict_keys=("user_id", "source", "date"),
    )


async def upsert_glucose_sample(session: AsyncSession, values: dict[str, Any]) -> None:
    """Insert a run glucose sample, or update it if (run_id, elapsed_seconds, source) exists."""
    await _upsert_on_constraint(
        session,
        RunGlucoseSample,
        values,
        constraint="uq_run_glucose_sample",
        conflict_keys=("run_id", "elapsed_seconds", "source"),
    )


async def upsert_glucose_daily(session: AsyncSession, values: dict[str, Any]) -> None:
    """Insert a daily glucose record, or update it if (user_id, source, date) exists."""
    await _upsert_on_constraint(
        session,
        GlucoseDailyRecord,
        values,
        constraint="uq_glucose_user_source_date",
        conflict_keys=("user_id", "source", "date"),
    )


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
