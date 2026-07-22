"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import {
  cityFromLat,
  formatDate,
  formatDateShort,
  formatPace,
} from "@/lib/format";
import type { Comparison, Run, SimilarRunsResponse } from "@/lib/types";

export default function CompareRunPage() {
  const params = useParams<{ id: string }>();
  const [run, setRun] = useState<Run | null>(null);
  const [similar, setSimilar] = useState<SimilarRunsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getRun(params.id)
      .then(setRun)
      .catch((e) =>
        setError(e instanceof ApiError ? e.message : "Could not load run.")
      );
    api
      .getSimilarRuns(params.id)
      .then(setSimilar)
      .catch(() => setSimilar(null));
  }, [params.id]);

  if (error) return <p className="text-sm text-red-700">{error}</p>;
  if (!run || !similar) return <p className="text-sm text-sand">Loading…</p>;

  const city = cityFromLat(run.start_lat);
  const n = similar.runs.length;
  const comparison = similar.comparison;

  return (
    <div className="space-y-3">
      {/* Small gradient header — the screen's single gradient surface */}
      <div className="hero-gradient rounded-3xl px-5 pt-4 pb-4">
        <div className="flex items-center justify-between">
          <Link
            href={`/runs/${run.id}`}
            aria-label="Back to run"
            className="text-clay"
          >
            <ArrowLeft size={18} strokeWidth={1.75} />
          </Link>
          <p className="text-[13px] font-medium text-ink">vs similar runs</p>
          <span className="w-[18px]" />
        </div>
        <p className="mt-2.5 text-xs text-clay">
          {formatDate(run.date)} · {run.run_type} · {run.distance_km} km
          {city ? ` · ${city}` : ""}
        </p>
        <p className="mt-0.5 text-[11.5px] text-clay">
          compared with your {n} closest{" "}
          {similar.type_fallback ? "" : `${run.run_type} `}runs
          {similar.type_fallback
            ? ` — not enough ${run.run_type} runs, so all types are included`
            : similar.pool_size < 8
              ? ` — small sample (${similar.pool_size} candidates)`
              : ""}
        </p>
      </div>

      {n === 0 ? (
        <p className="text-sm text-sand px-1">
          No comparable runs yet — log a few more and come back.
        </p>
      ) : (
        <>
          {comparison && <DeltaCards comparison={comparison} />}

          {comparison && (
            <div className="glass-ai rounded-2xl p-3.5">
              <p className="text-[11.5px] leading-relaxed text-leaf-deep">
                {interpret(comparison, run.run_type)}
              </p>
            </div>
          )}

          <div className="bg-white border-[0.5px] border-line rounded-2xl p-4">
            <p className="text-[13px] font-medium text-ink mb-2.5">
              Pace, this run vs each
            </p>
            <PaceBars run={run} similar={similar} />
          </div>

          <section>
            <p className="text-[13px] font-medium text-ink mb-2 px-1">
              The {n} comparable{n === 1 ? "" : "s"}
            </p>
            <div className="space-y-1.5">
              {similar.runs.map((s) => (
                <Link
                  key={s.run_id}
                  href={`/runs/${s.run_id}`}
                  className="flex justify-between items-center bg-white border-[0.5px] border-line rounded-2xl px-3.5 py-2.5"
                >
                  <span className="text-xs text-ink">
                    {formatDate(s.date)} · {s.distance_km} km
                    {s.weather_temp_start_c !== null
                      ? ` · ${Math.round(s.weather_temp_start_c)}°C`
                      : ""}
                  </span>
                  <span className="text-[11px] font-medium text-leaf">
                    {s.score.toFixed(2)}
                  </span>
                </Link>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}

/** Green ink ONLY for unambiguously positive deltas (faster pace, lower
 * HR); everything else stays neutral brown — inform, don't grade. */
function DeltaCards({ comparison }: { comparison: Comparison }) {
  const cards: {
    key: string;
    label: string;
    value: string;
    sub: string;
    positive: boolean;
  }[] = [];

  const pace = comparison.pace_delta_seconds_per_km;
  if (pace !== null) {
    const s = Math.round(Math.abs(pace));
    cards.push({
      key: "pace",
      label: "pace",
      value: pace <= 0 ? `−${s}s` : `+${s}s`,
      sub: pace <= 0 ? "faster /km" : "slower /km",
      positive: pace < 0,
    });
  }
  const hr = comparison.avg_hr_delta;
  if (hr !== null) {
    const b = Math.round(Math.abs(hr));
    cards.push({
      key: "hr",
      label: "avg hr",
      value: hr <= 0 ? `−${b}` : `+${b}`,
      sub: hr <= 0 ? "lower bpm" : "higher bpm",
      positive: hr < 0,
    });
  }
  const temp = comparison.weather_temp_delta_c;
  if (temp !== null) {
    const t = Math.round(Math.abs(temp));
    cards.push({
      key: "temp",
      label: "temp",
      value: temp >= 0 ? `+${t}°C` : `−${t}°C`,
      sub: temp >= 0 ? "warmer" : "cooler",
      positive: false,
    });
  }
  const glucose = comparison.glucose_delta_mg_dl;
  if (glucose !== null) {
    const g = Math.round(Math.abs(glucose));
    cards.push({
      key: "glucose",
      label: "glucose",
      value: glucose >= 0 ? `+${g}` : `−${g}`,
      sub: glucose >= 0 ? "higher mg/dL" : "lower mg/dL",
      positive: false,
    });
  }

  if (cards.length === 0) return null;

  return (
    <div className="grid grid-cols-3 gap-2">
      {cards.map((c) => (
        <div
          key={c.key}
          className="bg-white border-[0.5px] border-line rounded-2xl px-3 py-2.5"
        >
          <p className="text-[10.5px] text-sand">{c.label}</p>
          <p
            className={`mt-0.5 text-base font-medium ${
              c.positive ? "text-leaf-deep" : "text-ink"
            }`}
          >
            {c.value}
          </p>
          <p className="text-[10px] text-sand">{c.sub}</p>
        </div>
      ))}
    </div>
  );
}

/** Deterministic one-liner from the deltas — no LLM involved. */
function interpret(comparison: Comparison, runType: string): string {
  const pace = comparison.pace_delta_seconds_per_km;
  const hr = comparison.avg_hr_delta;
  const temp = comparison.weather_temp_delta_c;

  const faster = pace !== null && pace <= -2;
  const slower = pace !== null && pace >= 2;
  const lowerHr = hr !== null && hr <= -1;
  const higherHr = hr !== null && hr >= 1;
  const warmer = temp !== null && temp >= 2;
  const cooler = temp !== null && temp <= -2;

  const typical = `your typical ${runType} run`;
  const tempClause = warmer
    ? ` — despite ${Math.round(temp!)}°C warmer conditions`
    : cooler
      ? ` — helped perhaps by ${Math.round(Math.abs(temp!))}°C cooler conditions`
      : "";

  if (faster && lowerHr) {
    return `Faster at a lower heart rate than ${typical}${tempClause}. A quietly strong sign.`;
  }
  if (faster && higherHr) {
    return `Faster than ${typical}, but at a higher heart rate — it cost more.`;
  }
  if (slower && lowerHr) {
    return `Slower but at a lower heart rate than ${typical} — an easier effort.`;
  }
  if (slower && higherHr) {
    return `Slower at a higher heart rate than ${typical}${warmer ? ` — the ${Math.round(temp!)}°C warmer conditions likely played a part` : ""}.`;
  }
  if (faster) return `Faster than ${typical}${tempClause}.`;
  if (slower) return `Slower than ${typical}${tempClause}.`;
  return `Right in line with ${typical}.`;
}

function PaceBars({
  run,
  similar,
}: {
  run: Run;
  similar: SimilarRunsResponse;
}) {
  const rows: { key: string; label: string; pace: number; isTarget: boolean }[] =
    [];
  if (run.avg_pace_seconds_per_km) {
    rows.push({
      key: "target",
      label: "this run",
      pace: run.avg_pace_seconds_per_km,
      isTarget: true,
    });
  }
  for (const s of similar.runs) {
    if (s.avg_pace_seconds_per_km) {
      rows.push({
        key: s.run_id,
        label: formatDateShort(s.date),
        pace: s.avg_pace_seconds_per_km,
        isTarget: false,
      });
    }
  }
  if (rows.length === 0) {
    return <p className="text-xs text-sand">No pace data to compare.</p>;
  }

  const paces = rows.map((r) => r.pace);
  const min = Math.min(...paces);
  const max = Math.max(...paces);
  // Longer bar = slower pace; keep every bar visible and differences legible
  const width = (pace: number) =>
    max === min ? 62 : 40 + (55 * (pace - min)) / (max - min);

  return (
    <div className="space-y-1.5">
      {rows.map((r) => (
        <div key={r.key} className="flex items-center gap-2">
          <span
            className={`w-12 shrink-0 text-[10px] ${
              r.isTarget ? "text-leaf font-medium" : "text-sand"
            }`}
          >
            {r.label}
          </span>
          <div
            className={`h-[9px] rounded-[5px] ${
              r.isTarget ? "bg-leaf" : "bg-leaf-soft"
            }`}
            style={{ width: `${width(r.pace)}%` }}
          />
          <span
            className={`text-[10px] ${r.isTarget ? "text-ink" : "text-sand"}`}
          >
            {formatPace(r.pace).replace("/km", "")}
          </span>
        </div>
      ))}
    </div>
  );
}
