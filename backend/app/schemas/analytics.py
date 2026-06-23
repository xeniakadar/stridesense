from datetime import date as date_type
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import RunType


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
