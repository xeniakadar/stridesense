"use client";

import { Info } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { AcwrExplainerPanel } from "@/components/AcwrInfo";
import { DailyOverview } from "@/components/DailyOverview";
import { useDemoMode } from "@/components/DemoProvider";
import { Chip } from "@/components/ui";
import { WeeklyMileageChart } from "@/components/charts/WeeklyMileageChart";
import { api } from "@/lib/api";
import { CARD_TITLES } from "@/lib/cards";
import {
  cityFromCoords,
  formatDate,
  formatDistance,
  formatKmTotal,
  RUN_TYPE_LABELS,
} from "@/lib/format";
import type { LoadPoint, Run, WeeklyMileagePoint } from "@/lib/types";

// Deterministic per-zone suggestion (same permissive, non-prescriptive
// voice as the daily brief) — no LLM involved
const TODAY_RECS: Record<string, { title: string; km: string }> = {
  optimal: { title: "Easy run", km: "6–8 km" },
  building: { title: "Easy run", km: "6–8 km" },
  detraining: { title: "Easy run", km: "6–8 km" },
  caution: { title: "Short & easy", km: "3–5 km" },
  danger: { title: "Recovery day", km: "Rest or short jog" },
};

export default function DashboardPage() {
  const demoMode = useDemoMode();
  const [mileage, setMileage] = useState<WeeklyMileagePoint[] | null>(null);
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [load, setLoad] = useState<LoadPoint | null>(null);
  const [showAcwrInfo, setShowAcwrInfo] = useState(false);

  useEffect(() => {
    api
      .weeklyMileage()
      .then(setMileage)
      .catch(() => setMileage([]));
    api
      .listRuns()
      .then(setRuns)
      .catch(() => setRuns([]));
    api
      .getTrainingLoad()
      .then((points) => setLoad(points.at(-1) ?? null))
      .catch(() => setLoad(null));
  }, []);

  const thisWeek = mileage?.at(-1);
  const weekStart = thisWeek ? new Date(thisWeek.week_start) : null;
  const runsThisWeek =
    runs && weekStart
      ? runs.filter((r) => new Date(r.date) >= weekStart).length
      : null;
  const recent = runs?.slice(0, 3) ?? [];
  const rec = load?.zone ? TODAY_RECS[load.zone] : null;

  return (
    <div className="space-y-3">
      {/* Hero — the screen's single gradient surface. Full-bleed: escapes
          the column padding to the screen edges and reaches up behind the
          transparent top bar. */}
      <div className="gradient-overview -mx-4 -mt-2 rounded-b-3xl px-5 pt-16 pb-6">
        {/* True two-column row: metric left, compact Today panel right,
            vertically centred beside it. flex-wrap lets the panel drop
            just below the metric on very narrow screens. */}
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
          <div>
            <p className="text-[13px] text-clay-hero">Hi Xenia</p>
            <p className="mt-2 text-5xl font-medium text-ink leading-tight">
              {thisWeek ? formatKmTotal(thisWeek.distance_km) : "— km"}
            </p>
            <p className="mt-0.5 text-xs text-clay-hero">
              this week
              {runsThisWeek !== null
                ? ` · ${runsThisWeek} run${runsThisWeek === 1 ? "" : "s"}`
                : ""}
            </p>
          </div>
          {rec && (
            // Compact and secondary: subtle translucent panel, no border
            <div className="w-[180px] bg-white/35 rounded-2xl px-3.5 py-2.5">
              <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-clay-hero/90">
                Today
              </p>
              <p className="mt-0.5 text-[15px] font-medium text-ink">
                {rec.title}
              </p>
              <p className="text-[12px] text-clay-hero">{rec.km}</p>
            </div>
          )}
        </div>
        {load?.acwr != null && (
          <div className="mt-3">
            <button
              type="button"
              onClick={() => setShowAcwrInfo((s) => !s)}
              aria-expanded={showAcwrInfo}
              className="tap-target inline-flex items-center gap-1.5 bg-white/55 px-2.5 py-1 rounded-full"
            >
              <span className="w-[7px] h-[7px] rounded-full bg-leaf" />
              <span className="text-xs text-leaf-deep">
                Load {load.zone} · ACWR {load.acwr.toFixed(1)}
              </span>
              <Info size={12} strokeWidth={1.75} className="text-leaf-deep/70" />
            </button>
            {showAcwrInfo && <AcwrExplainerPanel className="mt-2 max-w-sm" />}
          </div>
        )}
      </div>

      <div className="bg-white border-[0.5px] border-line rounded-2xl p-4">
        <div className="mb-3 flex justify-between items-baseline">
          <h2 className="text-[20px] font-medium text-ink leading-snug">
            {CARD_TITLES["weekly-mileage"]}
          </h2>
          <p className="text-[13px] text-sand">last 12 weeks</p>
        </div>
        {mileage ? (
          <WeeklyMileageChart data={mileage} />
        ) : (
          <div className="h-[200px] flex items-center justify-center text-sm text-sand">
            Loading…
          </div>
        )}
      </div>

      <DailyOverview />

      {recent.length > 0 && (
        <section>
          <p className="text-[13px] font-medium text-ink mb-2 mt-1 px-1">
            Recent
          </p>
          <div className="space-y-1.5">
            {recent.map((run) => (
              <Link
                key={run.id}
                href={`/runs/${run.id}`}
                className="flex justify-between items-center bg-white border-[0.5px] border-line rounded-2xl px-3.5 py-2.5"
              >
                <span>
                  <span className="block text-[15px] text-ink">
                    {formatDate(run.date)} · {formatDistance(run.distance_km)}
                  </span>
                  <span className="block text-[13px] text-sand mt-0.5">
                    {RUN_TYPE_LABELS[run.run_type]}
                    {cityFromCoords(run.start_lat, run.start_lng)
                      ? ` · ${cityFromCoords(run.start_lat, run.start_lng)}`
                      : ""}
                  </span>
                </span>
                {!demoMode && <Chip tone="green">{run.source}</Chip>}
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
