"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { DailyOverview } from "@/components/DailyOverview";
import { WeeklyMileageChart } from "@/components/charts/WeeklyMileageChart";
import { api } from "@/lib/api";
import { cityFromLat, formatDate, RUN_TYPE_LABELS } from "@/lib/format";
import type { LoadPoint, Run, WeeklyMileagePoint } from "@/lib/types";

export default function DashboardPage() {
  const [mileage, setMileage] = useState<WeeklyMileagePoint[] | null>(null);
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [load, setLoad] = useState<LoadPoint | null>(null);

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

  return (
    <div className="space-y-3">
      {/* Hero — the screen's single gradient surface */}
      <div className="hero-gradient rounded-3xl px-5 pt-6 pb-5">
        <p className="text-[13px] text-clay-hero">Hi Xenia</p>
        <p className="mt-2 text-4xl font-medium text-ink leading-tight">
          {thisWeek ? `${thisWeek.distance_km.toFixed(1)} km` : "— km"}
        </p>
        <p className="mt-0.5 mb-3 text-xs text-clay-hero">
          this week
          {runsThisWeek !== null
            ? ` · ${runsThisWeek} run${runsThisWeek === 1 ? "" : "s"}`
            : ""}
        </p>
        {load?.acwr != null && (
          <span className="inline-flex items-center gap-1.5 bg-white/55 px-2.5 py-1 rounded-full">
            <span className="w-[7px] h-[7px] rounded-full bg-leaf" />
            <span className="text-xs text-leaf-deep">
              Load {load.zone} · ACWR {load.acwr.toFixed(1)}
            </span>
          </span>
        )}
      </div>

      <div className="bg-white border-[0.5px] border-line rounded-2xl p-4">
        <div className="mb-3 flex justify-between items-baseline">
          <h2 className="text-[13px] font-medium text-ink">Weekly distance</h2>
          <p className="text-[11px] text-sand">last 12 weeks</p>
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
                  <span className="block text-[13px] text-ink">
                    {formatDate(run.date)} · {run.distance_km} km
                  </span>
                  <span className="block text-[11px] text-sand mt-0.5">
                    {RUN_TYPE_LABELS[run.run_type]}
                    {cityFromLat(run.start_lat)
                      ? ` · ${cityFromLat(run.start_lat)}`
                      : ""}
                  </span>
                </span>
                <span className="text-[10.5px] bg-leaf-pale text-leaf-deep px-2 py-0.5 rounded-full">
                  {run.source}
                </span>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
