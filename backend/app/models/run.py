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
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import DataSource, RunType, RunTypeSource


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Temporal
    date: Mapped[date_type] = mapped_column(nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Source tracking — the heart of the source-aware design
    source: Mapped[DataSource] = mapped_column(
        Enum(DataSource, name="data_source"), nullable=False, default=DataSource.MANUAL
    )
    external_id: Mapped[str | None] = mapped_column(String(255))
    external_url: Mapped[str | None] = mapped_column(String(500))
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)

    # Core metrics
    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_pace_seconds_per_km: Mapped[float | None] = mapped_column(Float)
    avg_hr: Mapped[int | None] = mapped_column(Integer)
    max_hr: Mapped[int | None] = mapped_column(Integer)
    elevation_gain_m: Mapped[float | None] = mapped_column(Float)

    # Run classification
    run_type: Mapped[RunType] = mapped_column(
        Enum(RunType, name="run_type"), nullable=False, default=RunType.OTHER
    )
    run_type_source: Mapped[RunTypeSource] = mapped_column(
        Enum(RunTypeSource, name="run_type_source"),
        nullable=False,
        default=RunTypeSource.DEFAULT,
    )

    # Subjective
    perceived_effort: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)

    # From source (Strava titles, descriptions, etc.)
    raw_title: Mapped[str | None] = mapped_column(String(500))
    raw_description: Mapped[str | None] = mapped_column(Text)
    extracted_tags: Mapped[list | None] = mapped_column(JSONB)

    # Location — used for weather matching
    start_lat: Mapped[float | None] = mapped_column(Float)
    start_lng: Mapped[float | None] = mapped_column(Float)

    # Denormalized weather summary — computed once when weather samples are ingested.
    # Used by similarity engine, fatigue scoring, and analytics queries for speed.
    # Detailed per-sample data lives in run_weather_samples.
    weather_temp_start_c: Mapped[float | None] = mapped_column(Float)
    weather_temp_end_c: Mapped[float | None] = mapped_column(Float)
    weather_temp_max_c: Mapped[float | None] = mapped_column(Float)
    weather_temp_min_c: Mapped[float | None] = mapped_column(Float)
    weather_apparent_temp_max_c: Mapped[float | None] = mapped_column(Float)
    weather_humidity_avg: Mapped[float | None] = mapped_column(Float)
    weather_wind_speed_avg_kmh: Mapped[float | None] = mapped_column(Float)
    weather_precipitation_total_mm: Mapped[float | None] = mapped_column(Float)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        # Dedup: same external run can't be imported twice
        UniqueConstraint("user_id", "source", "external_id", name="uq_runs_source_external"),
        # Hot path: user's runs in reverse chronological order
        Index("ix_runs_user_date", "user_id", "date"),
        # For similarity matching by run type
        Index("ix_runs_user_type_date", "user_id", "run_type", "date"),
    )
