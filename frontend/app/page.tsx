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
  optimal: { title: "Easy run or rest", km: "6–8 km" },
  building: { title: "Easy run or rest", km: "6–8 km" },
  detraining: { title: "Easy run or rest", km: "6–8 km" },
  caution: { title: "Short & easy", km: "3–5 km" },
  danger: { title: "Recovery day", km: "Rest or short jog" },
};

// One-clause plain-language reason per zone, appended to the load line
const ZONE_REASONS: Record<string, string> = {
  optimal: "nothing pushing you either way",
  building: "load is ramping, with room to grow",
  detraining: "load has been light lately",
  caution: "load is running a bit high",
  danger: "load is well above your normal",
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
      <div className="gradient-overview -mx-4 -mt-2 rounded-b-3xl px-5 pt-[calc(1.25rem+env(safe-area-inset-top))] pb-5">
        {/* Stacked hero (option A): greeting sits level with the nav-bar
            actions; the metric carries its meta inline; one full-width
            strip unifies the recommendation with the load status */}
        {/* Greeting + demo badge share one flex row (the NavBar overlay
            skips the badge on home). pr clears the overlaid gear/plus;
            the greeting truncates first — the badge never shrinks. */}
        <div className="flex items-center gap-2 min-w-0 pr-20">
          <p className="truncate text-[13px] text-clay-hero">Hi Xenia</p>
          {demoMode && (
            <Chip
              tone="custom"
              className="shrink-0 bg-amber-50 text-amber-800 border border-amber-200"
            >
              Demo
            </Chip>
          )}
        </div>
        <p className="mt-3 text-5xl font-medium text-ink leading-none">
          {thisWeek ? formatKmTotal(thisWeek.distance_km) : "— km"}{" "}
          <span className="text-sm font-normal text-clay-hero">
            this week
            {runsThisWeek !== null
              ? ` · ${runsThisWeek} run${runsThisWeek === 1 ? "" : "s"}`
              : ""}
          </span>
        </p>
        {rec && load?.acwr != null && (
          <div className="mt-3.5 bg-white/65 border-[0.5px] border-white/90 rounded-2xl px-3.5 py-3">
            <div className="flex justify-between items-baseline gap-3">
              <p className="text-[14px] font-medium text-ink">
                Today: {rec.title.toLowerCase()}
              </p>
              <span className="text-[12px] text-clay-hero shrink-0">
                {rec.km}
              </span>
            </div>
            <button
              type="button"
              onClick={() => setShowAcwrInfo((s) => !s)}
              aria-expanded={showAcwrInfo}
              className="tap-target mt-1.5 flex items-center gap-1.5 text-[11.5px] text-leaf-deep text-left"
            >
              <span className="w-[6px] h-[6px] rounded-full bg-leaf shrink-0" />
              <span>
                Load {load.zone} (ACWR {load.acwr.toFixed(1)})
                {ZONE_REASONS[load.zone] ? ` — ${ZONE_REASONS[load.zone]}` : ""}
              </span>
              <Info
                size={11}
                strokeWidth={1.75}
                className="text-leaf-deep/70 shrink-0"
              />
            </button>
            {showAcwrInfo && <AcwrExplainerPanel className="mt-2" />}
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
