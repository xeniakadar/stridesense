from datetime import date as date_type
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import DataSource, RunType


class SimilarRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: UUID
    date: date_type
    run_type: RunType
    distance_km: float
    avg_pace_seconds_per_km: float | None
    score: float


class LoadPointRead(BaseModel):
    date: date_type
    acute_load: float
    chronic_load: float
    acwr: float | None
    zone: str

class GlucoseSampleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    elapsed_seconds: int
    glucose_mg_dl: float
    trend: str | None
    source: DataSource


class InsightRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    content: str
    model: str
    created_at: datetime
