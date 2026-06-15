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

import { formatDateShort } from "@/lib/format";
import type { WeeklyMileagePoint } from "@/lib/types";

export function WeeklyMileageChart({ data }: { data: WeeklyMileagePoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart
        data={data}
        margin={{ top: 12, right: 12, bottom: 12, left: 0 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#eee" vertical={false} />
        <XAxis
          dataKey="week_start"
          tickFormatter={formatDateShort}
          tick={{ fontSize: 12, fill: "#666" }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          unit=" km"
          tick={{ fontSize: 12, fill: "#666" }}
          axisLine={false}
          tickLine={false}
          width={60}
        />
        <Tooltip
          labelFormatter={(label) => formatDateShort(label as string)}
          formatter={(value) => [`${Number(value).toFixed(1)} km`, "Distance"]}
        />
        <Bar dataKey="distance_km" fill="#111827" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
