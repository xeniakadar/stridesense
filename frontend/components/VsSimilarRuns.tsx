"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ChartLegend } from "@/components/charts/ChartLegend";
import { api } from "@/lib/api";
import {
  AXIS,
  LEAF_BRIGHT,
  LEAF_MID,
  LEAF_SOFT,
  LINE,
  TOOLTIP_STYLE,
} from "@/lib/colors";
import {
  formatDate,
  formatDateShort,
  formatMonthYear,
  formatPace,
} from "@/lib/format";
import type { Comparison, Run, SimilarRunsResponse } from "@/lib/types";

/** The former /runs/[id]/compare screen, folded into the detail page:
 * header + honest pool line, pace-over-time scatter, delta cards, the
 * deterministic verdict, and a compact linked list of the comparables. */
export function VsSimilarRuns({ run }: { run: Run }) {
  const [similar, setSimilar] = useState<SimilarRunsResponse | null>(null);

  useEffect(() => {
    api
      .getSimilarRuns(run.id)
      .then(setSimilar)
      .catch(() => setSimilar(null));
  }, [run.id]);

  if (!similar || similar.runs.length === 0) return null;

  const n = similar.runs.length;
  const comparison = similar.comparison;

  return (
    <section id="vs-similar-runs" className="scroll-mt-20">
      <div className="px-1 mb-2 mt-1">
        <p className="text-[13px] font-medium text-ink">Similar runs</p>
        <p className="text-[11.5px] text-sand">
          compared with your {n} closest{" "}
          {similar.type_fallback ? "" : `${run.run_type} `}runs
          {similar.type_fallback
            ? ` — not enough ${run.run_type} runs, so all types are included`
            : similar.pool_size < 8
              ? ` — small sample (${similar.pool_size} candidates)`
              : ""}
        </p>
      </div>

      <div className="space-y-3">
        <div className="bg-white border-[0.5px] border-line rounded-2xl p-4">
          <p className="text-[13px] font-medium text-ink mb-2.5">
            Pace over time, this run highlighted
          </p>
          <PaceLineChart run={run} similar={similar} />
        </div>

        {comparison && <DeltaCards comparison={comparison} />}

        {comparison && (
          <div className="glass-ai rounded-2xl p-3.5">
            <p className="text-[11.5px] leading-relaxed text-leaf-deep">
              {interpret(comparison, run.run_type)}
            </p>
          </div>
        )}

        <div className="space-y-1.5">
          {similar.runs.map((s) => (
            <Link
              key={s.run_id}
              href={`/runs/${s.run_id}`}
              className="flex justify-between items-center bg-white border-[0.5px] border-line rounded-2xl px-3.5 py-2.5"
            >
              {/* Fields the endpoint doesn't have (e.g. HR) just don't
                  render — no dashes, no placeholders */}
              <span className="text-[13.5px] text-ink">
                {formatDateShort(s.date)}
                {s.avg_pace_seconds_per_km
                  ? ` · ${formatPace(s.avg_pace_seconds_per_km)}`
                  : ""}
                {s.weather_temp_start_c !== null
                  ? ` · ${Math.round(s.weather_temp_start_c)}°C`
                  : ""}
              </span>
              <span className="text-[11px] text-sand shrink-0 ml-3">
                {Math.round(s.score * 100)}%
              </span>
            </Link>
          ))}
        </div>
      </div>
    </section>
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
      label: "Pace",
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
      label: "Avg HR",
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
      label: "Temp",
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
      label: "Glucose",
      value: glucose >= 0 ? `+${g}` : `−${g}`,
      sub: glucose >= 0 ? "higher mg/dL" : "lower mg/dL",
      positive: false,
    });
  }

  if (cards.length === 0) return null;

  return (
    // 2×2 on narrow screens (no orphan row), one row when there's room
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
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

/** Per-point dot renderer that makes the compared run unmissable: filled,
 * larger, and labeled — the comparables stay small open circles. */
function RunDot(props: {
  firstTs: number;
  lastTs: number;
  cx?: number;
  cy?: number;
  payload?: { isTarget?: boolean; ts?: number };
}) {
  const { firstTs, lastTs, cx, cy, payload } = props;
  if (cx == null || cy == null) return null;
  if (!payload?.isTarget) {
    return (
      <circle
        cx={cx}
        cy={cy}
        r={3.5}
        fill="#fff"
        stroke={LEAF_MID}
        strokeWidth={1.5}
      />
    );
  }
  // A centered label clips when the point sits near either x-edge (the
  // target is usually the newest run, hard against the right margin) —
  // hang it sideways there instead
  const t = ((payload.ts ?? firstTs) - firstTs) / (lastTs - firstTs || 1);
  const label =
    t > 0.85
      ? { x: cx - 10, y: cy + 3.5, anchor: "end" as const }
      : t < 0.15
        ? { x: cx + 10, y: cy + 3.5, anchor: "start" as const }
        : cy > 26
          ? { x: cx, y: cy - 11, anchor: "middle" as const }
          : { x: cx, y: cy + 18, anchor: "middle" as const };
  return (
    <g>
      <circle cx={cx} cy={cy} r={6} fill={LEAF_BRIGHT} stroke="#fff" strokeWidth={2} />
      <text
        x={label.x}
        y={label.y}
        textAnchor={label.anchor}
        fontSize={10}
        fontWeight={500}
        fill={AXIS}
      >
        This run
      </text>
    </g>
  );
}

/** Pace by date across the comparables and this run — one connected line
 * (it's all the same runner over time), with this run's point emphasized.
 * Y axis is reversed so faster sits higher. */
function PaceLineChart({
  run,
  similar,
}: {
  run: Run;
  similar: SimilarRunsResponse;
}) {
  const rows: { ts: number; pace: number; isTarget: boolean }[] = [];
  if (run.avg_pace_seconds_per_km) {
    rows.push({
      ts: new Date(run.date).getTime(),
      pace: run.avg_pace_seconds_per_km,
      isTarget: true,
    });
  }
  for (const s of similar.runs) {
    if (s.avg_pace_seconds_per_km) {
      rows.push({
        ts: new Date(s.date).getTime(),
        pace: s.avg_pace_seconds_per_km,
        isTarget: false,
      });
    }
  }
  if (rows.length === 0) {
    return <p className="text-xs text-sand">No pace data to compare.</p>;
  }
  rows.sort((a, b) => a.ts - b.ts);

  // Dots are the runs; the line is only the pattern through them — a
  // least-squares fit by date, not a point-to-point connection
  const data: { ts: number; pace: number; trend?: number }[] = rows;
  if (rows.length >= 2) {
    const n = rows.length;
    const meanTs = rows.reduce((sum, r) => sum + r.ts, 0) / n;
    const meanPace = rows.reduce((sum, r) => sum + r.pace, 0) / n;
    const denom = rows.reduce((sum, r) => sum + (r.ts - meanTs) ** 2, 0);
    const slope =
      denom === 0
        ? 0
        : rows.reduce(
            (sum, r) => sum + (r.ts - meanTs) * (r.pace - meanPace),
            0
          ) / denom;
    for (const row of data) {
      row.trend = meanPace + slope * (row.ts - meanTs);
    }
  }

  return (
    <>
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={data} margin={{ top: 18, right: 14, bottom: 4, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={LINE} vertical={false} />
        <XAxis
          dataKey="ts"
          type="number"
          scale="time"
          domain={["dataMin", "dataMax"]}
          tickFormatter={(ts: number) =>
            formatMonthYear(new Date(ts).toISOString())
          }
          tick={{ fontSize: 11, fill: AXIS }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tickFormatter={(v: number) => formatPace(v).replace("/km", "")}
          tick={{ fontSize: 11, fill: AXIS }}
          axisLine={false}
          tickLine={false}
          width={44}
          reversed
          domain={["dataMin - 10", "dataMax + 10"]}
        />
        <Tooltip
          {...TOOLTIP_STYLE}
          labelFormatter={(ts) =>
            formatDate(new Date(Number(ts)).toISOString())
          }
          formatter={(value) => [formatPace(Number(value)), "Pace"]}
        />
        <Line
          dataKey="trend"
          stroke={LEAF_SOFT}
          strokeWidth={2}
          strokeDasharray="6 4"
          dot={false}
          activeDot={false}
          tooltipType="none"
        />
        <Line
          dataKey="pace"
          stroke="none"
          dot={<RunDot firstTs={data[0].ts} lastTs={data[data.length - 1].ts} />}
          activeDot={{ r: 5, fill: LEAF_MID, stroke: "#fff", strokeWidth: 2 }}
        />
      </LineChart>
    </ResponsiveContainer>
    <ChartLegend
      items={[
        { label: "This run", color: LEAF_BRIGHT, shape: "dot" },
        { label: "Comparable runs", color: LEAF_MID, shape: "dot" },
        { label: "Trend", color: LEAF_SOFT, dashed: true },
      ]}
    />
    </>
  );
}
