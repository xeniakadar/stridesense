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
    weather_temp_start_c: float | None
    score: float


class ComparisonRead(BaseModel):
    """This run minus the median of its comparables; None when either side
    lacks the metric. Negative pace/HR = faster/lower."""

    pace_delta_seconds_per_km: float | None
    avg_hr_delta: float | None
    weather_temp_delta_c: float | None
    glucose_delta_mg_dl: float | None


class SimilarRunsRead(BaseModel):
    runs: list[SimilarRunRead]
    pool_size: int
    type_fallback: bool
    comparison: ComparisonRead | None


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


class MonthlyVolumePoint(BaseModel):
    month: date_type  # first day of the month
    distance_km: float


class RecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: str
    run_id: UUID | None  # None for biggest_week — it isn't one run
    date: date_type  # week start for biggest_week
    distance_km: float
    duration_seconds: int | None
    avg_pace_seconds_per_km: float | None


class GlucoseTrendPoint(BaseModel):
    date: date_type
    time_in_range_pct: float


class CityStatsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    country_code: str | None
    lat: float
    lng: float
    run_count: int
    total_km: float
    first_run_date: date_type
    last_run_date: date_type
    min_temp_c: float | None
    max_temp_c: float | None
    has_race: bool


class CitiesRead(BaseModel):
    cities: list[CityStatsRead]
    unlocated_count: int


class DailyBriefRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date_type
    content: str
    # None when the brief was produced without the LLM (no data yet)
    model: str | None
    created_at: datetime


class AskRequest(BaseModel):
    question: str


class CitedRunRead(BaseModel):
    run_id: UUID
    date: date_type
    run_type: RunType
    distance_km: float
    score: float
    # None when the run has no coordinates or no known city resolves;
    # defaulted so demo answers pre-generated before this field parse fine
    city: str | None = None


class AskAnswerRead(BaseModel):
    answer: str
    # None when the answer was produced without the LLM (e.g. no embedded
    # runs to retrieve from)
    model: str | None
    cited_runs: list[CitedRunRead]
