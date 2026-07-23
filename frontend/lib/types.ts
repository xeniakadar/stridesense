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
  | "libre"
  | "open_meteo";

export type RunTypeSource = "user" | "extracted" | "default" | "inferred";

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

export interface SimilarRun {
  run_id: string;
  date: string;
  run_type: RunType;
  distance_km: number;
  avg_pace_seconds_per_km: number | null;
  weather_temp_start_c: number | null;
  score: number;
}

// This run minus the median of its comparables; null when either side
// lacks the metric. Negative pace/HR = faster/lower.
export interface Comparison {
  pace_delta_seconds_per_km: number | null;
  avg_hr_delta: number | null;
  weather_temp_delta_c: number | null;
  glucose_delta_mg_dl: number | null;
}

export interface SimilarRunsResponse {
  runs: SimilarRun[];
  pool_size: number;
  type_fallback: boolean;
  comparison: Comparison | null;
}

export interface LoadPoint {
  date: string;
  acute_load: number;
  chronic_load: number;
  acwr: number | null;
  zone: "detraining" | "optimal" | "caution" | "danger" | "building";
}

// Integrations (phase 3)
export type ImportJobStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "partial";

export type ImportJobType =
  | "initial_sync"
  | "incremental_sync"
  | "csv_upload"
  | "file_upload";

export interface ImportJob {
  id: string;
  source: DataSource;
  job_type: ImportJobType;
  status: ImportJobStatus;
  items_total: number | null;
  items_imported: number;
  items_skipped_duplicates: number;
  items_failed: number;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
  created_at: string;
}

export interface JobAccepted {
  job_id: string;
}

export interface Insight {
  id: string;
  run_id: string;
  content: string;
  model: string;
  created_at: string;
}

export interface CityStats {
  name: string;
  country_code: string | null;
  lat: number;
  lng: number;
  run_count: number;
  total_km: number;
  first_run_date: string;
  last_run_date: string;
  min_temp_c: number | null;
  max_temp_c: number | null;
  has_race: boolean;
}

export interface CitiesResponse {
  cities: CityStats[];
  unlocated_count: number;
}

export interface DailyBrief {
  date: string;
  content: string;
  // null when the backend answered without the LLM (no data yet)
  model: string | null;
  created_at: string;
}

export interface AppConfig {
  demo_mode: boolean;
}

export interface CitedRun {
  run_id: string;
  date: string;
  run_type: RunType;
  distance_km: number;
  score: number;
}

export interface AskAnswer {
  answer: string;
  // null when the backend answered without the LLM (no embedded runs)
  model: string | null;
  cited_runs: CitedRun[];
}

export interface GlucoseSample {
  elapsed_seconds: number;
  glucose_mg_dl: number;
  trend: string | null;
  source: DataSource;
}
