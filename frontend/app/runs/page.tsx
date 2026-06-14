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
import type { Run } from "@/lib/types";

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
      <div className="p-4 bg-red-50 border border-red-200 rounded text-sm text-red-900">
        Couldn't load runs: {error}
      </div>
    );
  }

  if (runs === null) {
    return <div className="text-gray-500">Loading runs…</div>;
  }

  if (runs.length === 0) {
    return (
      <div className="text-center py-16">
        <p className="text-gray-600 mb-4">No runs yet.</p>
        <Link
          href="/runs/new"
          className="inline-block bg-gray-900 text-white px-4 py-2 rounded hover:bg-gray-700"
        >
          Log your first run
        </Link>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-medium">Runs</h1>
        <span className="text-sm text-gray-500">{runs.length} total</span>
      </div>

      <div className="bg-white border border-gray-200 rounded overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600 text-left">
            <tr>
              <th className="px-4 py-3 font-medium">Date</th>
              <th className="px-4 py-3 font-medium">Type</th>
              <th className="px-4 py-3 font-medium text-right">Distance</th>
              <th className="px-4 py-3 font-medium text-right">Duration</th>
              <th className="px-4 py-3 font-medium text-right">Pace</th>
              <th className="px-4 py-3 font-medium text-right">HR</th>
              <th className="px-4 py-3 font-medium text-right">RPE</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr
                key={run.id}
                className="border-t border-gray-100 hover:bg-gray-50 cursor-pointer"
                onClick={() => (window.location.href = `/runs/${run.id}`)}
              >
                <td className="px-4 py-3">{formatDate(run.date)}</td>
                <td className="px-4 py-3 text-gray-600">
                  {RUN_TYPE_LABELS[run.run_type]}
                </td>
                <td className="px-4 py-3 text-right">
                  {formatDistance(run.distance_km)}
                </td>
                <td className="px-4 py-3 text-right">
                  {formatDuration(run.duration_seconds)}
                </td>
                <td className="px-4 py-3 text-right">
                  {formatPace(run.avg_pace_seconds_per_km)}
                </td>
                <td className="px-4 py-3 text-right">{run.avg_hr ?? "—"}</td>
                <td className="px-4 py-3 text-right">
                  {run.perceived_effort ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
