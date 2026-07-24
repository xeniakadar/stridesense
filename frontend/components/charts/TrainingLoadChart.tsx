"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { AXIS, LEAF, LINE, TOOLTIP_STYLE } from "@/lib/colors";
import { formatDateShort } from "@/lib/format";
import type { LoadPoint } from "@/lib/types";

// ACWR sweet spot per sports-science convention (matches the backend)
const OPTIMAL_LOW = 0.8;
const OPTIMAL_HIGH = 1.3;

export function TrainingLoadChart({ data }: { data: LoadPoint[] }) {
  const points = data.filter((p) => p.acwr !== null);
  if (points.length === 0) {
    return (
      <div className="text-sm text-sand py-12 text-center">
        Not enough history for a load ratio yet.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={points} margin={{ top: 12, right: 12, bottom: 4, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={LINE} vertical={false} />
        <XAxis
          dataKey="date"
          tickFormatter={formatDateShort}
          minTickGap={28}
          tick={{ fontSize: 11, fill: AXIS }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 11, fill: AXIS }}
          axisLine={false}
          tickLine={false}
          width={34}
          domain={[0, "dataMax + 0.3"]}
        />
        <ReferenceArea
          y1={OPTIMAL_LOW}
          y2={OPTIMAL_HIGH}
          fill={LEAF}
          fillOpacity={0.1}
          strokeOpacity={0}
        />
        <Tooltip
          {...TOOLTIP_STYLE}
          labelFormatter={(label) => formatDateShort(label as string)}
          formatter={(value) => [Number(value).toFixed(2), "ACWR"]}
        />
        <Line
          type="monotone"
          dataKey="acwr"
          stroke={LEAF}
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
