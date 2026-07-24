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

import { ChartLegend } from "@/components/charts/ChartLegend";
import { AXIS, LEAF, LEAF_DARK, LINE, TOOLTIP_STYLE } from "@/lib/colors";
import { formatDateShort } from "@/lib/format";
import type { GlucoseTrendPoint } from "@/lib/types";

export function GlucoseTirChart({ data }: { data: GlucoseTrendPoint[] }) {
  // 7-day rolling average carries the trend; the daily line stays faint
  const smoothed = data.map((point, i) => {
    const window = data.slice(Math.max(0, i - 6), i + 1);
    const avg =
      window.reduce((sum, p) => sum + p.time_in_range_pct, 0) / window.length;
    return { ...point, rolling_avg: Math.round(avg * 10) / 10 };
  });

  return (
    <>
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={smoothed} margin={{ top: 12, right: 12, bottom: 4, left: 0 }}>
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
          unit="%"
          allowDecimals={false}
          tick={{ fontSize: 11, fill: AXIS }}
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
          formatter={(value, name) => [
            `${Math.round(Number(value))}%`,
            name === "rolling_avg" ? "7-day avg" : "Daily",
          ]}
        />
        {/* Daily stays subordinate by weight (hairline vs 2.5), but its
            stroke must clear 3:1 on white — LEAF_SOFT sat at 1.4:1 */}
        <Line
          type="monotone"
          dataKey="time_in_range_pct"
          stroke={LEAF_DARK}
          strokeWidth={1}
          dot={false}
        />
        <Line
          type="monotone"
          dataKey="rolling_avg"
          stroke={LEAF}
          strokeWidth={2.5}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
    <ChartLegend
      items={[
        { label: "7-day avg", color: LEAF },
        { label: "Daily", color: LEAF_DARK, thin: true },
      ]}
    />
    </>
  );
}
