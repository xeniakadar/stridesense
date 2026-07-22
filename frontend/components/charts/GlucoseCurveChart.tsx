"use client";

import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { api } from "@/lib/api";
import { LEAF, LINE, SAND, TOOLTIP_STYLE } from "@/lib/colors";
import type { GlucoseSample } from "@/lib/types";

// Standard non-diabetic in-range band (mg/dL) — same bounds the backend
// uses for glucose_time_in_range_pct.
const RANGE_LOW = 70;
const RANGE_HIGH = 140;

function formatElapsed(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = Math.round(totalSeconds % 60);
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function GlucoseCurveChart({ runId }: { runId: string }) {
  const [samples, setSamples] = useState<GlucoseSample[] | null>(null);

  useEffect(() => {
    api
      .getGlucoseSamples(runId)
      .then(setSamples)
      .catch(() => setSamples([]));
  }, [runId]);

  // Hidden entirely until samples exist — no loading flash, no empty chart
  if (!samples || samples.length === 0) return null;

  const data = samples.map((s) => ({
    elapsedMinutes: s.elapsed_seconds / 60,
    elapsedSeconds: s.elapsed_seconds,
    glucose: s.glucose_mg_dl,
  }));

  const minPoint = data.reduce((a, b) => (b.glucose < a.glucose ? b : a));
  const maxPoint = data.reduce((a, b) => (b.glucose > a.glucose ? b : a));
  const values = data.map((d) => d.glucose);
  const yDomain: [number, number] = [
    Math.min(RANGE_LOW, ...values) - 10,
    Math.max(RANGE_HIGH, ...values) + 10,
  ];

  return (
    <div className="mb-4">
      <ResponsiveContainer width="100%" height={240}>
        <LineChart
          data={data}
          margin={{ top: 12, right: 12, bottom: 12, left: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke={LINE} vertical={false} />
          <XAxis
            dataKey="elapsedMinutes"
            type="number"
            unit=" min"
            tick={{ fontSize: 11, fill: SAND }}
            axisLine={false}
            tickLine={false}
            domain={["dataMin", "dataMax"]}
          />
          <YAxis
            tick={{ fontSize: 11, fill: SAND }}
            axisLine={false}
            tickLine={false}
            width={40}
            domain={yDomain}
          />
          <ReferenceArea
            y1={RANGE_LOW}
            y2={RANGE_HIGH}
            fill={LEAF}
            fillOpacity={0.12}
            strokeOpacity={0}
          />
          <Tooltip
            {...TOOLTIP_STYLE}
            labelFormatter={(label) => formatElapsed(Number(label) * 60)}
            formatter={(value) => [`${Math.round(Number(value))} mg/dL`, "Glucose"]}
          />
          <Line
            type="monotone"
            dataKey="glucose"
            stroke={LEAF}
            strokeWidth={2}
            dot={false}
          />
          <ReferenceDot
            x={minPoint.elapsedMinutes}
            y={minPoint.glucose}
            r={5}
            fill="#fff"
            stroke={LEAF}
            strokeWidth={2}
            label={{
              value: `min ${Math.round(minPoint.glucose)}`,
              position: "bottom",
              fontSize: 11,
              fill: SAND,
            }}
          />
          <ReferenceDot
            x={maxPoint.elapsedMinutes}
            y={maxPoint.glucose}
            r={5}
            fill="#fff"
            stroke={LEAF}
            strokeWidth={2}
            label={{
              value: `max ${Math.round(maxPoint.glucose)}`,
              position: "top",
              fontSize: 11,
              fill: SAND,
            }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
