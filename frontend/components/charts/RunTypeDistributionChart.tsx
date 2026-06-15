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

import { RUN_TYPE_LABELS } from "@/lib/format";
import type { RunTypeDistributionItem } from "@/lib/types";

export function RunTypeDistributionChart({
  data,
}: {
  data: RunTypeDistributionItem[];
}) {
  if (data.length === 0) {
    return (
      <div className="text-sm text-gray-500 py-12 text-center">
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
        <CartesianGrid strokeDasharray="3 3" stroke="#eee" horizontal={false} />
        <XAxis
          type="number"
          tick={{ fontSize: 12, fill: "#666" }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          type="category"
          dataKey="label"
          tick={{ fontSize: 12, fill: "#666" }}
          axisLine={false}
          tickLine={false}
          width={80}
        />
        <Tooltip
          formatter={(value: number, _key, props) => {
            const dist = props.payload.total_distance_km;
            return [`${value} runs · ${dist.toFixed(1)} km`, "Total"];
          }}
        />
        <Bar dataKey="count" fill="#111827" radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
