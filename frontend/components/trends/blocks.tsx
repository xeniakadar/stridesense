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
import {
  flagEmoji,
  formatDate,
  formatDistance,
  formatMonthYear,
  formatPace,
} from "@/lib/format";
import type {
  CityStats,
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
  action,
  children,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white border-[0.5px] border-line rounded-2xl p-4">
      <div className="mb-3 flex justify-between items-center gap-2">
        <h2 className="text-[20px] font-medium text-ink leading-snug">{title}</h2>
        {action ?? (subtitle && <p className="text-[13px] text-sand">{subtitle}</p>)}
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
  const [cities, setCities] = useState<CityStats[] | null>(null);
  useEffect(() => {
    api
      .getCities()
      .then((res) => setCities(res.cities))
      .catch(() => setCities([]));
  }, []);

  // Preview: the 3 most recently visited cities
  const recent = (cities ?? [])
    .slice()
    .sort((a, b) => b.last_run_date.localeCompare(a.last_run_date))
    .slice(0, 3);

  return (
    <Link
      href="/trends/cities"
      className="block bg-white border-[0.5px] border-line rounded-2xl px-3.5 py-3"
    >
      <span className="flex justify-between items-center">
        <span>
          <span className="block text-[20px] font-medium text-ink">
            🌍 Cities
          </span>
          <span className="block text-[13px] text-clay mt-0.5">
            everywhere you've run
          </span>
        </span>
        <span className="text-sm text-leaf">→</span>
      </span>
      {recent.length > 0 && (
        <span className="flex flex-wrap gap-1.5 mt-2.5">
          {recent.map((city) => (
            <span
              key={`${city.name}-${city.lat}-${city.lng}`}
              className="text-[11px] bg-leaf-pale/70 text-leaf-deep px-2.5 py-1 rounded-full"
            >
              {flagEmoji(city.country_code)} {city.name} ·{" "}
              {formatMonthYear(city.last_run_date)}
            </span>
          ))}
        </span>
      )}
    </Link>
  );
}

const LOAD_RANGES = [
  { key: "90d", label: "90d", days: 90 },
  { key: "1y", label: "1y", days: 365 },
  { key: "all", label: "all", days: null },
] as const;
type LoadRangeKey = (typeof LOAD_RANGES)[number]["key"];

function TrainingLoadBlock() {
  const [load, setLoad] = useState<LoadPoint[] | null>(null);
  // Default window also hides the chronic-baseline cold-start spike
  const [range, setRange] = useState<LoadRangeKey>("90d");
  useEffect(() => {
    api
      .getTrainingLoad()
      .then(setLoad)
      .catch(() => setLoad([]));
  }, []);

  const days = LOAD_RANGES.find((r) => r.key === range)?.days ?? null;
  const cutoff = days ? new Date(Date.now() - days * 86_400_000) : null;
  const filtered =
    load === null
      ? null
      : cutoff
        ? load.filter((p) => new Date(p.date) >= cutoff)
        : load;

  return (
    <ChartCard
      title="Training load"
      action={
        <span className="flex bg-leaf-pale/50 rounded-full p-[2px]">
          {LOAD_RANGES.map((r) => (
            <button
              key={r.key}
              onClick={() => setRange(r.key)}
              className={`text-[11px] px-2.5 py-0.5 rounded-full ${
                range === r.key
                  ? "bg-white text-leaf-deep font-medium"
                  : "text-clay"
              }`}
            >
              {r.label}
            </button>
          ))}
        </span>
      }
    >
      {filtered ? <TrainingLoadChart data={filtered} /> : <Loading />}
    </ChartCard>
  );
}

function GlucoseTirBlock({ data }: { data: GlucoseTrendPoint[] }) {
  return (
    <ChartCard title="Time in range" subtitle="90 days · 7-day avg">
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
                <span className="text-[15px] text-ink">
                  {RECORD_LABELS[record.kind] ?? record.kind}
                </span>
                <span className="text-right">
                  <span className="block text-[15px] font-medium text-leaf-deep">
                    {recordValue(record)}
                  </span>
                  <span className="block text-[12px] text-sand">
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
