"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { PaceTrendChart } from "@/components/charts/PaceTrendChart";
import { RunTypeDistributionChart } from "@/components/charts/RunTypeDistributionChart";
import { api } from "@/lib/api";
import type { PaceTrendPoint, RunTypeDistributionItem } from "@/lib/types";

export default function TrendsPage() {
  const [pace, setPace] = useState<PaceTrendPoint[] | null>(null);
  const [distribution, setDistribution] = useState<
    RunTypeDistributionItem[] | null
  >(null);

  useEffect(() => {
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
    <div className="space-y-3">
      <h1 className="text-xl font-medium text-ink px-1">Trends</h1>

      <Link
        href="/trends/cities"
        className="flex justify-between items-center bg-white border-[0.5px] border-line rounded-2xl px-3.5 py-3"
      >
        <span>
          <span className="block text-[13.5px] font-medium text-ink">
            🌍 Cities
          </span>
          <span className="block text-[11.5px] text-clay mt-0.5">
            everywhere you've run
          </span>
        </span>
        <span className="text-sm text-leaf">→</span>
      </Link>

      <ChartCard title="Easy-run pace trend" subtitle="last 90 days">
        {pace ? <PaceTrendChart data={pace} /> : <Loading />}
      </ChartCard>

      <ChartCard title="Run types" subtitle="last 30 days">
        {distribution ? (
          <RunTypeDistributionChart data={distribution} />
        ) : (
          <Loading />
        )}
      </ChartCard>
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
    <div className="bg-white border-[0.5px] border-line rounded-2xl p-4">
      <div className="mb-3 flex justify-between items-baseline">
        <h2 className="text-[13px] font-medium text-ink">{title}</h2>
        <p className="text-[11px] text-sand">{subtitle}</p>
      </div>
      {children}
    </div>
  );
}

function Loading() {
  return (
    <div className="h-[200px] flex items-center justify-center text-sm text-sand">
      Loading…
    </div>
  );
}
