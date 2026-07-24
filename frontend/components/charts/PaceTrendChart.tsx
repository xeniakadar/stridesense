"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { AXIS, LEAF, LINE, TOOLTIP_STYLE } from "@/lib/colors";
import { formatDateShort, formatPace } from "@/lib/format";
import type { PaceTrendPoint } from "@/lib/types";

export function PaceTrendChart({ data }: { data: PaceTrendPoint[] }) {
  if (data.length === 0) {
    return (
      <div className="text-sm text-sand py-12 text-center">
        No easy runs in the last 90 days yet.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart
        data={data}
        margin={{ top: 12, right: 12, bottom: 12, left: 0 }}
      >
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
          tickFormatter={(v: number) => formatPace(v)}
          tick={{ fontSize: 11, fill: AXIS }}
          axisLine={false}
          tickLine={false}
          width={70}
          reversed
          domain={["dataMin - 10", "dataMax + 10"]}
        />
        <Tooltip
          {...TOOLTIP_STYLE}
          labelFormatter={(label) => formatDateShort(label as string)}
          formatter={(value) => [formatPace(Number(value)), "Pace"]}
        />
        <Line
          type="monotone"
          dataKey="pace_seconds_per_km"
          stroke={LEAF}
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
