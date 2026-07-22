"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { LEAF, LEAF_MID, LINE, SAND, TOOLTIP_STYLE } from "@/lib/colors";
import { formatDateShort } from "@/lib/format";
import type { WeeklyMileagePoint } from "@/lib/types";

export function WeeklyMileageChart({ data }: { data: WeeklyMileagePoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart
        data={data}
        margin={{ top: 12, right: 12, bottom: 12, left: 0 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke={LINE} vertical={false} />
        <XAxis
          dataKey="week_start"
          tickFormatter={formatDateShort}
          tick={{ fontSize: 11, fill: SAND }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          unit=" km"
          tick={{ fontSize: 11, fill: SAND }}
          axisLine={false}
          tickLine={false}
          width={60}
        />
        <Tooltip
          {...TOOLTIP_STYLE}
          labelFormatter={(label) => formatDateShort(label as string)}
          formatter={(value) => [`${Number(value).toFixed(1)} km`, "Distance"]}
        />
        <Bar dataKey="distance_km" radius={[5, 5, 0, 0]}>
          {data.map((point, i) => (
            <Cell
              key={point.week_start}
              fill={i === data.length - 1 ? LEAF : LEAF_MID}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
