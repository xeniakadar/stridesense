"use client";

import { useEffect, useState } from "react";

import { PaceTrendChart } from "@/components/charts/PaceTrendChart";
import { RunTypeDistributionChart } from "@/components/charts/RunTypeDistributionChart";
import { WeeklyMileageChart } from "@/components/charts/WeeklyMileageChart";
import { api } from "@/lib/api";
import type {
  PaceTrendPoint,
  RunTypeDistributionItem,
  WeeklyMileagePoint,
} from "@/lib/types";

export default function DashboardPage() {
  const [mileage, setMileage] = useState<WeeklyMileagePoint[] | null>(null);
  const [pace, setPace] = useState<PaceTrendPoint[] | null>(null);
  const [distribution, setDistribution] = useState<
    RunTypeDistributionItem[] | null
  >(null);

  useEffect(() => {
    api
      .weeklyMileage()
      .then(setMileage)
      .catch(() => setMileage([]));
    api
      .paceTrend()
      .then(setPace)
      .catch(() => setPace([]));
    api
      .runTypeDistribution()
      .then(setDistribution)
      .catch(() => setDistribution([]));
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-medium">Dashboard</h1>

      <ChartCard
        title="Weekly mileage"
        subtitle="Total km per week, last 12 weeks"
      >
        {mileage ? <WeeklyMileageChart data={mileage} /> : <Loading />}
      </ChartCard>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard
          title="Easy-run pace trend"
          subtitle="Average pace on easy runs, last 90 days"
        >
          {pace ? <PaceTrendChart data={pace} /> : <Loading />}
        </ChartCard>

        <ChartCard title="Run type distribution" subtitle="Last 30 days">
          {distribution ? (
            <RunTypeDistributionChart data={distribution} />
          ) : (
            <Loading />
          )}
        </ChartCard>
      </div>
    </div>
  );
}

function ChartCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white border border-gray-200 rounded p-5">
      <div className="mb-4">
        <h2 className="text-base font-medium">{title}</h2>
        <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>
      </div>
      {children}
    </div>
  );
}

function Loading() {
  return (
    <div className="h-[240px] flex items-center justify-center text-sm text-gray-400">
      Loading…
    </div>
  );
}
