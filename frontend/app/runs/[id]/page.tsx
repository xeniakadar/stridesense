"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import {
  formatDate,
  formatDistance,
  formatDuration,
  formatGlucose,
  formatPace,
  formatTimeInRange,
} from "@/lib/format";
import type { Run } from "@/lib/types";

export default function RunDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    api
      .getRun(params.id)
      .then(setRun)
      .catch((e) =>
        setError(e instanceof ApiError ? e.message : "Could not load run.")
      );
  }, [params.id]);

  if (error) {
    return <p className="text-sm text-red-600">{error}</p>;
  }
  if (!run) {
    return <p className="text-sm text-gray-500">Loading…</p>;
  }

  const handleDelete = async () => {
    if (!confirm("Delete this run? This can't be undone.")) return;
    setDeleting(true);
    try {
      await api.deleteRun(run.id);
      router.push("/runs");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Delete failed.");
      setDeleting(false);
    }
  };

  const hasWeather = run.weather_temp_start_c !== null;
  const hasGlucose = run.glucose_at_start_mg_dl !== null;

  return (
    <div className="max-w-3xl space-y-8">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-gray-500">{formatDate(run.date)}</p>
          <h1 className="text-2xl font-medium capitalize">
            {run.run_type} run
          </h1>
        </div>
        <div className="flex gap-2">
          <Link
            href={`/runs/${run.id}/edit`}
            className="px-3 py-1.5 text-sm rounded border border-gray-300 hover:bg-gray-50"
          >
            Edit
          </Link>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="px-3 py-1.5 text-sm rounded border border-red-300 text-red-700 hover:bg-red-50 disabled:opacity-50"
          >
            {deleting ? "Deleting…" : "Delete"}
          </button>
        </div>
      </div>

      <Section title="Summary">
        <StatGrid>
          <Stat label="Distance" value={formatDistance(run.distance_km)} />
          <Stat label="Duration" value={formatDuration(run.duration_seconds)} />
          <Stat label="Pace" value={formatPace(run.avg_pace_seconds_per_km)} />
          <Stat label="Avg HR" value={run.avg_hr ? `${run.avg_hr} bpm` : "—"} />
          <Stat
            label="RPE"
            value={run.perceived_effort ? `${run.perceived_effort}/10` : "—"}
          />
          <Stat label="Source" value={run.source} />
        </StatGrid>
        {run.notes && (
          <div className="mt-6">
            <p className="text-xs uppercase tracking-wide text-gray-500 mb-1">
              Notes
            </p>
            <p className="text-sm text-gray-800 whitespace-pre-wrap">
              {run.notes}
            </p>
          </div>
        )}
      </Section>

      {hasWeather && (
        <Section title="Weather">
          <StatGrid>
            <Stat
              label="Temp at start"
              value={
                run.weather_temp_start_c !== null
                  ? `${Math.round(run.weather_temp_start_c)}°C`
                  : "—"
              }
            />
            <Stat
              label="Temp at end"
              value={
                run.weather_temp_end_c !== null
                  ? `${Math.round(run.weather_temp_end_c)}°C`
                  : "—"
              }
            />
            <Stat
              label="Apparent max"
              value={
                run.weather_apparent_temp_max_c !== null
                  ? `${Math.round(run.weather_apparent_temp_max_c)}°C`
                  : "—"
              }
            />
            <Stat
              label="Humidity (avg)"
              value={
                run.weather_humidity_avg !== null
                  ? `${Math.round(run.weather_humidity_avg)}%`
                  : "—"
              }
            />
            <Stat
              label="Wind (avg)"
              value={
                run.weather_wind_speed_avg_kmh !== null
                  ? `${Math.round(run.weather_wind_speed_avg_kmh)} km/h`
                  : "—"
              }
            />
            <Stat
              label="Precip total"
              value={
                run.weather_precipitation_total_mm !== null
                  ? `${run.weather_precipitation_total_mm.toFixed(1)} mm`
                  : "—"
              }
            />
          </StatGrid>
        </Section>
      )}

      {hasGlucose && (
        <Section title="Glucose">
          <StatGrid>
            <Stat
              label="Pre-run (60min avg)"
              value={formatGlucose(run.glucose_pre_run_60min_avg_mg_dl)}
            />
            <Stat
              label="At start"
              value={formatGlucose(run.glucose_at_start_mg_dl)}
            />
            <Stat
              label="At end"
              value={formatGlucose(run.glucose_at_end_mg_dl)}
            />
            <Stat
              label="Min during"
              value={formatGlucose(run.glucose_min_during_run_mg_dl)}
            />
            <Stat
              label="Max during"
              value={formatGlucose(run.glucose_max_during_run_mg_dl)}
            />
            <Stat
              label="Post-run (60min avg)"
              value={formatGlucose(run.glucose_post_run_60min_avg_mg_dl)}
            />
            <Stat
              label="Avg during"
              value={formatGlucose(run.glucose_avg_during_run_mg_dl)}
            />
            <Stat
              label="Time in range"
              value={formatTimeInRange(
                run.glucose_time_in_range_pct_during_run
              )}
            />
          </StatGrid>
        </Section>
      )}
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h2 className="text-sm font-medium uppercase tracking-wide text-gray-500 mb-3">
        {title}
      </h2>
      {children}
    </section>
  );
}

function StatGrid({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-4">
      {children}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-gray-500">{label}</p>
      <p className="text-base text-gray-900">{value}</p>
    </div>
  );
}
