"use client";

import { ArrowLeft, Pencil, RefreshCw, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useDemoMode } from "@/components/DemoProvider";
import { GlucoseCurveChart } from "@/components/charts/GlucoseCurveChart";
import { api, ApiError } from "@/lib/api";
import {
  cityFromLat,
  formatDate,
  formatDistance,
  formatDuration,
  formatGlucose,
  formatPace,
  formatTimeInRange,
} from "@/lib/format";
import type { Run, SimilarRun } from "@/lib/types";

export default function RunDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const demoMode = useDemoMode();
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
    return <p className="text-sm text-red-700">{error}</p>;
  }
  if (!run) {
    return <p className="text-sm text-sand">Loading…</p>;
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
  const city = cityFromLat(run.start_lat);

  return (
    <div className="space-y-3">
      {/* Hero — the screen's single gradient surface */}
      <div className="hero-gradient rounded-3xl px-5 pt-5 pb-5">
        <div className="flex justify-between items-center">
          <Link href="/runs" aria-label="Back to runs" className="text-clay">
            <ArrowLeft size={18} strokeWidth={1.75} />
          </Link>
          <div className="flex items-center gap-2">
            <span className="text-[11px] bg-white/55 text-clay px-2.5 py-0.5 rounded-full capitalize">
              {run.run_type}
            </span>
            {!demoMode && (
              <>
                <Link
                  href={`/runs/${run.id}/edit`}
                  aria-label="Edit run"
                  className="p-1.5 rounded-full bg-white/55 text-clay hover:bg-white/80"
                >
                  <Pencil size={13} strokeWidth={1.75} />
                </Link>
                <button
                  onClick={handleDelete}
                  disabled={deleting}
                  aria-label="Delete run"
                  className="p-1.5 rounded-full bg-white/55 text-red-700 hover:bg-white/80 disabled:opacity-50"
                >
                  <Trash2 size={13} strokeWidth={1.75} />
                </button>
              </>
            )}
          </div>
        </div>

        <p className="mt-3 text-4xl font-medium text-ink leading-none">
          {formatDistance(run.distance_km)}
        </p>
        <p className="mt-1.5 text-xs text-clay">
          {formatDate(run.date)}
          {city ? ` · ${city}` : ""}
        </p>

        <div className="flex gap-5 mt-3.5">
          <HeroStat value={formatDuration(run.duration_seconds)} label="time" />
          <HeroStat
            value={formatPace(run.avg_pace_seconds_per_km)}
            label="pace"
          />
          <HeroStat
            value={run.avg_hr ? `${run.avg_hr}` : "—"}
            label="avg hr"
          />
          {hasWeather && (
            <HeroStat
              value={`${Math.round(run.weather_temp_start_c!)}°C`}
              label={city ? city.toLowerCase() : "temp"}
            />
          )}
        </div>
      </div>

      <InsightSection runId={run.id} />

      {hasGlucose && (
        <Card>
          <div className="flex justify-between items-baseline mb-2.5">
            <p className="text-[13px] font-medium text-ink">
              Glucose
              {run.glucose_time_in_range_pct_during_run !== null &&
                ` · time in range ${formatTimeInRange(run.glucose_time_in_range_pct_during_run)}`}
            </p>
            {demoMode && (
              <span className="text-[10px] text-sand">glucose simulated</span>
            )}
          </div>
          <GlucoseCurveChart runId={run.id} />
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
          </StatGrid>
        </Card>
      )}

      <SimilarRunsSection runId={run.id} />

      {hasWeather && (
        <Card>
          <p className="text-[13px] font-medium text-ink mb-2.5">Weather</p>
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
        </Card>
      )}

      <Card>
        <p className="text-[13px] font-medium text-ink mb-2.5">Details</p>
        <StatGrid>
          <Stat
            label="RPE"
            value={run.perceived_effort ? `${run.perceived_effort}/10` : "—"}
          />
          <Stat label="Source" value={run.source} />
        </StatGrid>
        {run.notes && (
          <div className="mt-4">
            <p className="text-[10.5px] uppercase tracking-wide text-sand mb-1">
              Notes
            </p>
            <p className="text-sm text-ink whitespace-pre-wrap">{run.notes}</p>
          </div>
        )}
      </Card>
    </div>
  );
}

function HeroStat({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <p className="text-[15px] font-medium text-ink">{value}</p>
      <p className="text-[10.5px] text-clay">{label}</p>
    </div>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-white border-[0.5px] border-line rounded-2xl p-4">
      {children}
    </div>
  );
}

function StatGrid({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-3.5">
      {children}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10.5px] text-sand">{label}</p>
      <p className="text-[15px] text-ink">{value}</p>
    </div>
  );
}

function InsightSection({ runId }: { runId: string }) {
  const demoMode = useDemoMode();
  const [insight, setInsight] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    api
      .getInsight(runId)
      .then((res) => setInsight(res.content))
      .catch((e) =>
        setError(e instanceof ApiError ? e.message : "Could not load insight.")
      )
      .finally(() => setLoading(false));
  }, [runId]);

  const handleRegenerate = async () => {
    setRegenerating(true);
    setError(null);
    try {
      const res = await api.regenerateInsight(runId);
      setInsight(res.content);
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "Could not regenerate insight."
      );
    } finally {
      setRegenerating(false);
    }
  };

  return (
    <section className="glass-ai rounded-2xl p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-[13px] font-medium text-leaf-deep">Insight</h2>
        {!loading && !demoMode && (
          <button
            onClick={handleRegenerate}
            disabled={regenerating}
            aria-label="Regenerate insight"
            className="text-leaf-deep/70 hover:text-leaf-deep disabled:opacity-50"
          >
            <RefreshCw
              size={14}
              strokeWidth={1.75}
              className={regenerating ? "animate-spin" : undefined}
            />
          </button>
        )}
      </div>
      {loading && <p className="mt-2 text-sm text-clay">Analyzing this run…</p>}
      {error && <p className="mt-2 text-sm text-red-700">{error}</p>}
      {insight && (
        <p className="mt-2 text-sm leading-relaxed text-ink">{insight}</p>
      )}
    </section>
  );
}

function SimilarRunsSection({ runId }: { runId: string }) {
  const [runs, setRuns] = useState<SimilarRun[]>([]);
  useEffect(() => {
    api
      .getSimilarRuns(runId)
      .then((res) => setRuns(res.runs))
      .catch(() => setRuns([]));
  }, [runId]);

  if (runs.length === 0) return null;

  return (
    <section>
      <div className="flex justify-between items-baseline mb-2 mt-1 px-1">
        <p className="text-[13px] font-medium text-ink">Comparable runs</p>
        <Link
          href={`/runs/${runId}/compare`}
          className="text-[11px] font-medium text-leaf hover:underline"
        >
          Compare →
        </Link>
      </div>
      <div className="space-y-1.5">
        {runs.map((r) => (
          <Link
            key={r.run_id}
            href={`/runs/${r.run_id}`}
            className="flex justify-between items-center bg-white border-[0.5px] border-line rounded-2xl px-3.5 py-2.5"
          >
            <span className="text-xs text-ink capitalize">
              {formatDate(r.date)} · {r.run_type} ·{" "}
              {formatDistance(r.distance_km)}
            </span>
            <span className="text-[11px] font-medium text-leaf">
              {r.score.toFixed(2)}
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}
