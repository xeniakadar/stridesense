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
from app.models.enums import CyclePhase, DataSource


class SleepRecord(Base):
    __tablename__ = "sleep_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # The day this sleep informs (night of May 14 → 15 stores as date=May 15)
    date: Mapped[date_type] = mapped_column(nullable=False)
    source: Mapped[DataSource] = mapped_column(Enum(DataSource, name="data_source"), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255))

    sleep_hours: Mapped[float | None] = mapped_column(Float)
    sleep_quality: Mapped[int | None] = mapped_column(Integer)  # source-dependent scale
    deep_sleep_hours: Mapped[float | None] = mapped_column(Float)
    rem_sleep_hours: Mapped[float | None] = mapped_column(Float)
    resting_hr: Mapped[int | None] = mapped_column(Integer)
    hrv: Mapped[float | None] = mapped_column(Float)
    body_temperature_deviation_c: Mapped[float | None] = mapped_column(Float)

    raw_payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "source", "date", name="uq_sleep_user_source_date"),
        Index("ix_sleep_user_date", "user_id", "date"),
    )


class CycleRecord(Base):
    __tablename__ = "cycle_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date_type] = mapped_column(nullable=False)
    source: Mapped[DataSource] = mapped_column(Enum(DataSource, name="data_source"), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255))

    cycle_day: Mapped[int | None] = mapped_column(Integer)
    phase: Mapped[CyclePhase | None] = mapped_column(Enum(CyclePhase, name="cycle_phase"))
    period_length: Mapped[int | None] = mapped_column(Integer)
    cycle_length: Mapped[int | None] = mapped_column(Integer)

    raw_payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "source", "date", name="uq_cycle_user_source_date"),
        Index("ix_cycle_user_date", "user_id", "date"),
    )
