"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import {
  formatDate,
  formatDistance,
  formatDuration,
  formatPace,
  RUN_TYPE_LABELS,
} from "@/lib/format";
import type { DataSource, Run } from "@/lib/types";

const SOURCE_BADGES: Record<string, { label: string; classes: string }> = {
  manual: { label: "manual", classes: "bg-line/70 text-clay" },
  apple_health: { label: "apple", classes: "bg-rose-50 text-rose-700" },
  garmin: { label: "garmin", classes: "bg-leaf-pale text-leaf-deep" },
  strava: { label: "strava", classes: "bg-orange-50 text-orange-700" },
};

function SourceBadge({ source }: { source: DataSource }) {
  const badge = SOURCE_BADGES[source] ?? {
    label: source,
    classes: "bg-line/70 text-clay",
  };
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded-full text-[10.5px] font-medium ${badge.classes}`}
    >
      {badge.label}
    </span>
  );
}

export default function RunsPage() {
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listRuns()
      .then(setRuns)
      .catch((e: ApiError) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-2xl text-sm text-red-900">
        Couldn't load runs: {error}
      </div>
    );
  }

  if (runs === null) {
    return <div className="text-sand text-sm">Loading runs…</div>;
  }

  if (runs.length === 0) {
    return (
      <div className="text-center py-16">
        <p className="text-clay mb-4">No runs yet.</p>
        <Link
          href="/runs/new"
          className="inline-block bg-ink text-cream px-4 py-2 rounded-full text-sm hover:bg-clay"
        >
          Log your first run
        </Link>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-baseline justify-between mb-3 px-1">
        <h1 className="text-xl font-medium text-ink">Runs</h1>
        <span className="text-xs text-sand">{runs.length} total</span>
      </div>

      <div className="space-y-1.5">
        {runs.map((run) => (
          <Link
            key={run.id}
            href={`/runs/${run.id}`}
            className="flex justify-between items-center bg-white border-[0.5px] border-line rounded-2xl px-3.5 py-2.5"
          >
            <span>
              <span className="block text-[13px] text-ink">
                {formatDate(run.date)} · {formatDistance(run.distance_km)}
              </span>
              <span className="block text-[11px] text-sand mt-0.5">
                {RUN_TYPE_LABELS[run.run_type]} ·{" "}
                {formatPace(run.avg_pace_seconds_per_km)} ·{" "}
                {formatDuration(run.duration_seconds)}
                {run.avg_hr ? ` · ${run.avg_hr} bpm` : ""}
              </span>
            </span>
            <span className="flex items-center gap-1.5 shrink-0 ml-3">
              {run.glucose_at_start_mg_dl !== null && (
                <span title="Glucose data attached">🩸</span>
              )}
              <SourceBadge source={run.source} />
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
