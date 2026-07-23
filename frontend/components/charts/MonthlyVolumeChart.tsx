"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { LEAF_MID, LINE, SAND, TOOLTIP_STYLE } from "@/lib/colors";
import { formatMonthYear } from "@/lib/format";
import type { MonthlyVolumePoint } from "@/lib/types";

export function MonthlyVolumeChart({ data }: { data: MonthlyVolumePoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 12, right: 12, bottom: 4, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={LINE} vertical={false} />
        <XAxis
          dataKey="month"
          tickFormatter={formatMonthYear}
          tick={{ fontSize: 10, fill: SAND }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          unit=" km"
          tick={{ fontSize: 11, fill: SAND }}
          axisLine={false}
          tickLine={false}
          width={52}
        />
        <Tooltip
          {...TOOLTIP_STYLE}
          labelFormatter={(label) => formatMonthYear(label as string)}
          formatter={(value) => [`${Number(value).toFixed(1)} km`, "Distance"]}
        />
        <Bar dataKey="distance_km" fill={LEAF_MID} radius={[5, 5, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
