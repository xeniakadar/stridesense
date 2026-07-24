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

import { ChartLegend } from "@/components/charts/ChartLegend";
import {
  ACWR_OPTIMAL_HIGH as OPTIMAL_HIGH,
  ACWR_OPTIMAL_LOW as OPTIMAL_LOW,
} from "@/lib/acwr";
import { AXIS, LEAF, LINE, TOOLTIP_STYLE } from "@/lib/colors";
import { formatDateShort } from "@/lib/format";
import type { LoadPoint } from "@/lib/types";

export function TrainingLoadChart({ data }: { data: LoadPoint[] }) {
  const points = data.filter((p) => p.acwr !== null);
  if (points.length === 0) {
    return (
      <div className="text-sm text-sand py-12 text-center">
        Not enough history for a load ratio yet.
      </div>
    );
  }

  // Half-unit ticks (0.5 / 1.0 / 1.5 …) instead of recharts' arbitrary
  // auto-ticks like 1.77
  const maxAcwr = Math.max(...points.map((p) => p.acwr as number));
  const ticks: number[] = [];
  for (let t = 0.5; t <= maxAcwr + 0.3; t += 0.5) {
    ticks.push(Number(t.toFixed(1)));
  }

  return (
    <>
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
          ticks={ticks}
          tickFormatter={(v: number) => Number(v).toFixed(1)}
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
          label={{
            value: `optimal zone ${OPTIMAL_LOW}–${OPTIMAL_HIGH}`,
            position: "insideTopRight",
            fontSize: 10,
            fill: AXIS,
          }}
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
    <ChartLegend
      items={[
        { label: "ACWR", color: LEAF },
        {
          label: `Optimal zone (${OPTIMAL_LOW}–${OPTIMAL_HIGH})`,
          color: LEAF,
          shape: "band",
        },
      ]}
    />
    </>
  );
}
