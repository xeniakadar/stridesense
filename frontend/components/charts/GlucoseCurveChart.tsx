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

import { ChartLegend } from "@/components/charts/ChartLegend";
import { api } from "@/lib/api";
import { AXIS, LEAF, LINE, TOOLTIP_STYLE } from "@/lib/colors";
import { formatMinutesShort } from "@/lib/format";
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
  // A label on a point near either end of the x-range collides with the
  // axis or clips at the edge — hang it sideways there instead
  const span = data[data.length - 1].elapsedMinutes - data[0].elapsedMinutes || 1;
  const labelPosition = (
    point: { elapsedMinutes: number },
    vertical: "top" | "bottom"
  ): "left" | "right" | "top" | "bottom" => {
    const t = (point.elapsedMinutes - data[0].elapsedMinutes) / span;
    if (t < 0.12) return "right";
    if (t > 0.88) return "left";
    return vertical;
  };
  // Domain hugs the data (the in-range band clips to the visible window)
  // instead of always spanning 60-150 and wasting vertical space
  const values = data.map((d) => d.glucose);
  const yDomain: [number, number] = [
    Math.floor(Math.min(...values) - 10),
    Math.ceil(Math.max(...values) + 10),
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
            tickFormatter={(m) => formatMinutesShort(Number(m))}
            minTickGap={28}
            tick={{ fontSize: 11, fill: AXIS }}
            axisLine={false}
            tickLine={false}
            domain={["dataMin", "dataMax"]}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fontSize: 11, fill: AXIS }}
            axisLine={false}
            tickLine={false}
            width={40}
            domain={yDomain}
          />
          <ReferenceArea
            y1={RANGE_LOW}
            y2={RANGE_HIGH}
            ifOverflow="hidden"
            fill={LEAF}
            fillOpacity={0.12}
            strokeOpacity={0}
            label={{
              value: `in range ${RANGE_LOW}–${RANGE_HIGH}`,
              position: "insideTopRight",
              fontSize: 10,
              fill: AXIS,
            }}
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
              position: labelPosition(minPoint, "bottom"),
              offset: 10,
              fontSize: 11,
              fill: AXIS,
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
              position: labelPosition(maxPoint, "top"),
              offset: 10,
              fontSize: 11,
              fill: AXIS,
            }}
          />
        </LineChart>
      </ResponsiveContainer>
      <ChartLegend
        items={[
          { label: "Glucose (mg/dL)", color: LEAF },
          {
            label: `In range (${RANGE_LOW}–${RANGE_HIGH} mg/dL)`,
            color: LEAF,
            shape: "band",
          },
        ]}
      />
    </div>
  );
}
