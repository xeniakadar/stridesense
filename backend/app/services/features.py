"""Turn a Run (plus its context) into a normalized numeric feature vector
used for similarity matching and as structured input to the insight engine."""

from dataclasses import dataclass

from app.models import Run


@dataclass
class RunFeatures:
    """A flat, numeric representation of a run and its context.

    Every field is a float. None-able context (weather, glucose) is folded in
    only when present; callers check `has_weather` / `has_glucose` before
    relying on those dimensions.
    """

    distance_km: float
    pace_seconds_per_km: float
    avg_hr: float | None
    elevation_gain_m: float | None
    perceived_effort: float | None

    weather_temp_avg_c: float | None
    weather_humidity_avg: float | None

    glucose_avg_during_run: float | None
    glucose_time_in_range_pct: float | None

    @property
    def has_weather(self) -> bool:
        return self.weather_temp_avg_c is not None

    @property
    def has_glucose(self) -> bool:
        return self.glucose_avg_during_run is not None


def extract_features(run: Run) -> RunFeatures:
    """Pull the comparable signal out of a run row."""
    temp_avg = None
    if run.weather_temp_start_c is not None and run.weather_temp_end_c is not None:
        temp_avg = (run.weather_temp_start_c + run.weather_temp_end_c) / 2
    elif run.weather_temp_max_c is not None:
        temp_avg = run.weather_temp_max_c

    return RunFeatures(
        distance_km=run.distance_km,
        pace_seconds_per_km=run.avg_pace_seconds_per_km or 0.0,
        avg_hr=float(run.avg_hr) if run.avg_hr is not None else None,
        elevation_gain_m=run.elevation_gain_m,
        perceived_effort=(
            float(run.perceived_effort) if run.perceived_effort is not None else None
        ),
        weather_temp_avg_c=temp_avg,
        weather_humidity_avg=run.weather_humidity_avg,
        glucose_avg_during_run=run.glucose_avg_during_run_mg_dl,
        glucose_time_in_range_pct=run.glucose_time_in_range_pct_during_run,
    )
