import uuid
from datetime import date as date_type
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import DataSource


class GlucoseDailyRecord(Base):
    """Daily glucose summary — parallels SleepRecord in structure."""

    __tablename__ = "glucose_daily_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date_type] = mapped_column(nullable=False)
    source: Mapped[DataSource] = mapped_column(
        Enum(DataSource, name="data_source"), nullable=False
    )
    external_id: Mapped[str | None] = mapped_column(String(255))

    avg_glucose_mg_dl: Mapped[float | None] = mapped_column(Float)
    min_glucose_mg_dl: Mapped[float | None] = mapped_column(Float)
    max_glucose_mg_dl: Mapped[float | None] = mapped_column(Float)
    std_glucose_mg_dl: Mapped[float | None] = mapped_column(Float)

    time_in_range_pct: Mapped[float | None] = mapped_column(Float)
    glucose_variability_cv: Mapped[float | None] = mapped_column(Float)
    gmi: Mapped[float | None] = mapped_column(Float)

    overnight_avg_glucose_mg_dl: Mapped[float | None] = mapped_column(Float)
    overnight_min_glucose_mg_dl: Mapped[float | None] = mapped_column(Float)

    raw_payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "source", "date", name="uq_glucose_user_source_date"),
        Index("ix_glucose_user_date", "user_id", "date"),
    )


class RunGlucoseSample(Base):
    """Per-run glucose readings — parallels RunWeatherSample."""

    __tablename__ = "run_glucose_samples"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )

    elapsed_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    glucose_mg_dl: Mapped[float] = mapped_column(Float, nullable=False)
    trend: Mapped[str | None] = mapped_column(String(20))

    source: Mapped[DataSource] = mapped_column(
        Enum(DataSource, name="data_source"), nullable=False
    )
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("run_id", "elapsed_seconds", "source", name="uq_run_glucose_sample"),
        Index("ix_run_glucose_run_elapsed", "run_id", "elapsed_seconds"),
    )
