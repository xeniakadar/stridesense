export type RunType =
  | "easy"
  | "long"
  | "interval"
  | "tempo"
  | "recovery"
  | "race"
  | "other";

export type DataSource =
  | "manual"
  | "strava"
  | "oura"
  | "apple_health"
  | "garmin"
  | "csv"
  | "fit_upload"
  | "linx_cgm"
  | "dexcom"
  | "libre";

export type RunTypeSource = "user" | "extracted" | "default";

export interface Run {
  id: string;
  user_id: string;
  date: string;
  started_at: string | null;
  run_type: RunType;
  run_type_source: RunTypeSource;
  source: DataSource;

  distance_km: number;
  duration_seconds: number;
  avg_pace_seconds_per_km: number | null;
  avg_hr: number | null;
  max_hr: number | null;
  elevation_gain_m: number | null;

  perceived_effort: number | null;
  notes: string | null;

  start_lat: number | null;
  start_lng: number | null;

  // Weather summary
  weather_temp_start_c: number | null;
  weather_temp_end_c: number | null;
  weather_temp_max_c: number | null;
  weather_temp_min_c: number | null;
  weather_apparent_temp_max_c: number | null;
  weather_humidity_avg: number | null;
  weather_wind_speed_avg_kmh: number | null;
  weather_precipitation_total_mm: number | null;

  // Glucose summary
  glucose_pre_run_60min_avg_mg_dl: number | null;
  glucose_at_start_mg_dl: number | null;
  glucose_at_end_mg_dl: number | null;
  glucose_avg_during_run_mg_dl: number | null;
  glucose_min_during_run_mg_dl: number | null;
  glucose_max_during_run_mg_dl: number | null;
  glucose_post_run_60min_avg_mg_dl: number | null;
  glucose_time_in_range_pct_during_run: number | null;

  created_at: string;
  updated_at: string;
}

export interface RunCreate {
  date: string;
  started_at?: string | null;
  run_type: RunType;
  distance_km: number;
  duration_seconds: number;
  avg_hr?: number | null;
  max_hr?: number | null;
  elevation_gain_m?: number | null;
  perceived_effort?: number | null;
  notes?: string | null;
  start_lat?: number | null;
  start_lng?: number | null;
}

export type RunUpdate = Partial<RunCreate>;

// Analytics shapes — defined now, used in step 9
export interface WeeklyMileagePoint {
  week_start: string;
  distance_km: number;
}

export interface PaceTrendPoint {
  date: string;
  pace_seconds_per_km: number;
}

export interface RunTypeDistributionItem {
  run_type: RunType;
  count: number;
  total_distance_km: number;
}
