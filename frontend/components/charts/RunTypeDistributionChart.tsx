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

import { AXIS, LEAF_MID, LINE, TOOLTIP_STYLE } from "@/lib/colors";
import { RUN_TYPE_LABELS } from "@/lib/format";
import type { RunTypeDistributionItem } from "@/lib/types";

export function RunTypeDistributionChart({
  data,
}: {
  data: RunTypeDistributionItem[];
}) {
  if (data.length === 0) {
    return (
      <div className="text-sm text-sand py-12 text-center">
        No runs in the last 30 days yet.
      </div>
    );
  }

  const display = data.map((d) => ({
    ...d,
    label: RUN_TYPE_LABELS[d.run_type] ?? d.run_type,
  }));

  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart
        data={display}
        layout="vertical"
        margin={{ top: 12, right: 12, bottom: 12, left: 16 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke={LINE} horizontal={false} />
        <XAxis
          type="number"
          tick={{ fontSize: 11, fill: AXIS }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          type="category"
          dataKey="label"
          tick={{ fontSize: 11, fill: AXIS }}
          axisLine={false}
          tickLine={false}
          width={80}
        />
        <Tooltip
          {...TOOLTIP_STYLE}
          formatter={(value, _key, props) => {
            const count = Number(value);
            const dist =
              (props.payload as RunTypeDistributionItem)?.total_distance_km ??
              0;
            return [`${count} runs · ${dist.toFixed(1)} km`, "Total"];
          }}
        />
        <Bar dataKey="count" fill={LEAF_MID} radius={[0, 5, 5, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
