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

import { LEAF, LINE, SAND, TOOLTIP_STYLE } from "@/lib/colors";
import { formatDateShort } from "@/lib/format";
import type { GlucoseTrendPoint } from "@/lib/types";

export function GlucoseTirChart({ data }: { data: GlucoseTrendPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={data} margin={{ top: 12, right: 12, bottom: 4, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={LINE} vertical={false} />
        <XAxis
          dataKey="date"
          tickFormatter={formatDateShort}
          tick={{ fontSize: 11, fill: SAND }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          unit="%"
          tick={{ fontSize: 11, fill: SAND }}
          axisLine={false}
          tickLine={false}
          width={40}
          domain={[
            (dataMin: number) => Math.max(0, Math.floor(dataMin - 10)),
            100,
          ]}
        />
        <Tooltip
          {...TOOLTIP_STYLE}
          labelFormatter={(label) => formatDateShort(label as string)}
          formatter={(value) => [`${Math.round(Number(value))}%`, "In range"]}
        />
        <Line
          type="monotone"
          dataKey="time_in_range_pct"
          stroke={LEAF}
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
