from datetime import date as date_type
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DataSource, RunType, RunTypeSource


class RunBase(BaseModel):
    """Shared fields between create, update, and read."""

    date: date_type
    started_at: datetime | None = None
    run_type: RunType = RunType.OTHER

    distance_km: float = Field(gt=0, lt=200, description="Distance in kilometers")
    duration_seconds: int = Field(gt=0, description="Total moving time in seconds")
    avg_hr: int | None = Field(default=None, gt=30, lt=250)
    max_hr: int | None = Field(default=None, gt=30, lt=250)
    elevation_gain_m: float | None = Field(default=None, ge=0)

    perceived_effort: int | None = Field(default=None, ge=1, le=10)
    notes: str | None = Field(default=None, max_length=2000)

    start_lat: float | None = Field(default=None, ge=-90, le=90)
    start_lng: float | None = Field(default=None, ge=-180, le=180)


class RunCreate(RunBase):
    """Payload for POST /runs — all base fields, no system fields."""

    pass


class RunUpdate(BaseModel):
    """Payload for PUT /runs/{id} — every field optional (partial update)."""

    date: date_type | None = None
    started_at: datetime | None = None
    run_type: RunType | None = None
    distance_km: float | None = Field(default=None, gt=0, lt=200)
    duration_seconds: int | None = Field(default=None, gt=0)
    avg_hr: int | None = Field(default=None, gt=30, lt=250)
    max_hr: int | None = Field(default=None, gt=30, lt=250)
    elevation_gain_m: float | None = Field(default=None, ge=0)
    perceived_effort: int | None = Field(default=None, ge=1, le=10)
    notes: str | None = Field(default=None, max_length=2000)
    start_lat: float | None = Field(default=None, ge=-90, le=90)
    start_lng: float | None = Field(default=None, ge=-180, le=180)


class RunRead(RunBase):
    """Response shape for GET /runs and GET /runs/{id}."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    source: DataSource
    run_type_source: RunTypeSource
    avg_pace_seconds_per_km: float | None

    # Weather summary
    weather_temp_start_c: float | None = None
    weather_temp_end_c: float | None = None
    weather_temp_max_c: float | None = None
    weather_temp_min_c: float | None = None
    weather_apparent_temp_max_c: float | None = None
    weather_humidity_avg: float | None = None
    weather_wind_speed_avg_kmh: float | None = None
    weather_precipitation_total_mm: float | None = None

    # Glucose summary
    glucose_pre_run_60min_avg_mg_dl: float | None = None
    glucose_at_start_mg_dl: float | None = None
    glucose_at_end_mg_dl: float | None = None
    glucose_avg_during_run_mg_dl: float | None = None
    glucose_min_during_run_mg_dl: float | None = None
    glucose_max_during_run_mg_dl: float | None = None
    glucose_post_run_60min_avg_mg_dl: float | None = None
    glucose_time_in_range_pct_during_run: float | None = None

    created_at: datetime
    updated_at: datetime
