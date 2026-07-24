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

import { ChartLegend } from "@/components/charts/ChartLegend";
import { AXIS, LEAF, LEAF_MID, LINE, TOOLTIP_STYLE } from "@/lib/colors";
import { formatDateShort } from "@/lib/format";
import type { WeeklyMileagePoint } from "@/lib/types";

const WEEK_MS = 7 * 86_400_000;

export function WeeklyMileageChart({ data }: { data: WeeklyMileagePoint[] }) {
  // The in-progress week is found from the data's own week boundary —
  // never "the last bar", which would mislabel historical views
  const now = Date.now();
  const currentWeekStart = data.find((p) => {
    const start = new Date(p.week_start).getTime();
    return start <= now && now < start + WEEK_MS;
  })?.week_start;

  return (
    <>
    <ResponsiveContainer width="100%" height={240}>
      <BarChart
        data={data}
        margin={{ top: 12, right: 12, bottom: 12, left: 0 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke={LINE} vertical={false} />
        <XAxis
          dataKey="week_start"
          tickFormatter={formatDateShort}
          minTickGap={28}
          tick={{ fontSize: 11, fill: AXIS }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          unit=" km"
          allowDecimals={false}
          tick={{ fontSize: 11, fill: AXIS }}
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
          {data.map((point) => {
            // In-progress week: faded fill + dashed outline, so a partial
            // total doesn't read as a decline
            const inProgress = point.week_start === currentWeekStart;
            return (
              <Cell
                key={point.week_start}
                fill={inProgress ? LEAF : LEAF_MID}
                fillOpacity={inProgress ? 0.35 : 1}
                stroke={inProgress ? LEAF : undefined}
                strokeDasharray={inProgress ? "4 3" : undefined}
              />
            );
          })}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
    <ChartLegend
      items={[
        ...(currentWeekStart
          ? [
              {
                label: "This week (in progress)",
                color: LEAF,
                shape: "band" as const,
              },
            ]
          : []),
        { label: "Completed weeks", color: LEAF_MID, shape: "square" as const },
      ]}
    />
    </>
  );
}
