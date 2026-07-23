"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { GlucoseTirChart } from "@/components/charts/GlucoseTirChart";
import { MonthlyVolumeChart } from "@/components/charts/MonthlyVolumeChart";
import { PaceTrendChart } from "@/components/charts/PaceTrendChart";
import { RunTypeDistributionChart } from "@/components/charts/RunTypeDistributionChart";
import { TrainingLoadChart } from "@/components/charts/TrainingLoadChart";
import { WeeklyMileageChart } from "@/components/charts/WeeklyMileageChart";
import { api } from "@/lib/api";
import { formatDate, formatDistance, formatPace } from "@/lib/format";
import type {
  GlucoseTrendPoint,
  LoadPoint,
  MonthlyVolumePoint,
  PaceTrendPoint,
  RecordItem,
  RunTypeDistributionItem,
  WeeklyMileagePoint,
} from "@/lib/types";

export interface BlockDef {
  id: string;
  title: string;
  component: React.ComponentType;
}

// Curated for a first-time demo visitor
export const DEFAULT_ORDER = [
  "cities",
  "training-load",
  "glucose-tir",
  "pace-trend",
  "monthly-volume",
  "records",
  "run-types",
  "weekly-mileage",
];

/** The registry is built per page load: the glucose block only exists at
 * all when the user has glucose data. */
export function buildRegistry(glucose: GlucoseTrendPoint[]): BlockDef[] {
  const blocks: BlockDef[] = [
    { id: "cities", title: "Cities", component: CitiesBlock },
    { id: "training-load", title: "Training load", component: TrainingLoadBlock },
  ];
  if (glucose.length > 0) {
    blocks.push({
      id: "glucose-tir",
      title: "Glucose · time in range",
      component: function GlucoseTirBound() {
        return <GlucoseTirBlock data={glucose} />;
      },
    });
  }
  blocks.push(
    { id: "pace-trend", title: "Easy-run pace trend", component: PaceTrendBlock },
    { id: "monthly-volume", title: "Monthly volume", component: MonthlyVolumeBlock },
    { id: "records", title: "Records", component: RecordsBlock },
    { id: "run-types", title: "Run types", component: RunTypesBlock },
    { id: "weekly-mileage", title: "Weekly mileage", component: WeeklyMileageBlock }
  );
  return blocks;
}

// --- shared card chrome ---

function ChartCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white border-[0.5px] border-line rounded-2xl p-4">
      <div className="mb-3 flex justify-between items-baseline">
        <h2 className="text-[13px] font-medium text-ink">{title}</h2>
        {subtitle && <p className="text-[11px] text-sand">{subtitle}</p>}
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

// --- blocks ---

function CitiesBlock() {
  return (
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
  );
}

function TrainingLoadBlock() {
  const [load, setLoad] = useState<LoadPoint[] | null>(null);
  useEffect(() => {
    api
      .getTrainingLoad()
      .then(setLoad)
      .catch(() => setLoad([]));
  }, []);
  return (
    <ChartCard title="Training load" subtitle="ACWR · optimal band shaded">
      {load ? <TrainingLoadChart data={load} /> : <Loading />}
    </ChartCard>
  );
}

function GlucoseTirBlock({ data }: { data: GlucoseTrendPoint[] }) {
  return (
    <ChartCard title="Glucose · time in range" subtitle="last 90 days">
      <GlucoseTirChart data={data} />
    </ChartCard>
  );
}

function PaceTrendBlock() {
  const [pace, setPace] = useState<PaceTrendPoint[] | null>(null);
  useEffect(() => {
    api
      .paceTrend()
      .then(setPace)
      .catch(() => setPace([]));
  }, []);
  return (
    <ChartCard title="Easy-run pace trend" subtitle="last 90 days">
      {pace ? <PaceTrendChart data={pace} /> : <Loading />}
    </ChartCard>
  );
}

function MonthlyVolumeBlock() {
  const [volume, setVolume] = useState<MonthlyVolumePoint[] | null>(null);
  useEffect(() => {
    api
      .getMonthlyVolume()
      .then(setVolume)
      .catch(() => setVolume([]));
  }, []);
  return (
    <ChartCard title="Monthly volume" subtitle="last 12 months">
      {volume ? <MonthlyVolumeChart data={volume} /> : <Loading />}
    </ChartCard>
  );
}

const RECORD_LABELS: Record<string, string> = {
  fastest_5k: "Fastest 5K",
  fastest_10k: "Fastest 10K",
  fastest_half: "Fastest half",
  longest_run: "Longest run",
  biggest_week: "Biggest week",
};

function recordValue(record: RecordItem): string {
  if (record.kind === "biggest_week") return `${record.distance_km} km`;
  if (record.kind === "longest_run") return formatDistance(record.distance_km);
  return formatPace(record.avg_pace_seconds_per_km);
}

function RecordsBlock() {
  const [records, setRecords] = useState<RecordItem[] | null>(null);
  useEffect(() => {
    api
      .getRecords()
      .then(setRecords)
      .catch(() => setRecords([]));
  }, []);

  return (
    <ChartCard title="Records" subtitle="all time">
      {records === null ? (
        <Loading />
      ) : records.length === 0 ? (
        <p className="text-sm text-sand py-6 text-center">No runs yet.</p>
      ) : (
        <div className="divide-y divide-line/70">
          {records.map((record) => {
            const row = (
              <div className="flex justify-between items-baseline py-2">
                <span className="text-[13px] text-ink">
                  {RECORD_LABELS[record.kind] ?? record.kind}
                </span>
                <span className="text-right">
                  <span className="block text-[13px] font-medium text-leaf-deep">
                    {recordValue(record)}
                  </span>
                  <span className="block text-[10.5px] text-sand">
                    {record.kind === "biggest_week" ? "week of " : ""}
                    {formatDate(record.date)}
                  </span>
                </span>
              </div>
            );
            return record.run_id ? (
              <Link
                key={record.kind}
                href={`/runs/${record.run_id}`}
                className="block hover:bg-cream/60"
              >
                {row}
              </Link>
            ) : (
              <div key={record.kind}>{row}</div>
            );
          })}
        </div>
      )}
    </ChartCard>
  );
}

function RunTypesBlock() {
  const [distribution, setDistribution] = useState<
    RunTypeDistributionItem[] | null
  >(null);
  useEffect(() => {
    api
      .runTypeDistribution()
      .then(setDistribution)
      .catch(() => setDistribution([]));
  }, []);
  return (
    <ChartCard title="Run types" subtitle="last 30 days">
      {distribution ? (
        <RunTypeDistributionChart data={distribution} />
      ) : (
        <Loading />
      )}
    </ChartCard>
  );
}

function WeeklyMileageBlock() {
  const [mileage, setMileage] = useState<WeeklyMileagePoint[] | null>(null);
  useEffect(() => {
    api
      .weeklyMileage()
      .then(setMileage)
      .catch(() => setMileage([]));
  }, []);
  return (
    <ChartCard title="Weekly mileage" subtitle="last 12 weeks">
      {mileage ? <WeeklyMileageChart data={mileage} /> : <Loading />}
    </ChartCard>
  );
}
