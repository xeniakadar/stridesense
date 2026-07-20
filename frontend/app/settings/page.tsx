"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api, API_URL, ApiError } from "@/lib/api";
import type { ImportJob, ImportJobStatus } from "@/lib/types";

const STATUS_STYLES: Record<ImportJobStatus, string> = {
  pending: "bg-gray-100 text-gray-600",
  running: "bg-amber-50 text-amber-700 animate-pulse",
  completed: "bg-green-50 text-green-700",
  partial: "bg-yellow-50 text-yellow-700",
  failed: "bg-red-50 text-red-700",
};

const SOURCE_LABELS: Record<string, string> = {
  oura: "Oura",
  apple_health: "Apple Health",
  open_meteo: "Weather",
  garmin: "Garmin",
  linx_cgm: "Linx CGM",
};

function JobStatusBadge({ status }: { status: ImportJobStatus }) {
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${STATUS_STYLES[status]}`}
    >
      {status}
    </span>
  );
}

export default function SettingsPage() {
  const [jobs, setJobs] = useState<ImportJob[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const refreshJobs = useCallback(() => {
    api
      .listImportJobs()
      .then((next) => {
        setJobs(next);
        setError(null);
      })
      .catch((e: ApiError) => setError(e.message));
  }, []);

  useEffect(() => {
    refreshJobs();
    // Landing back from the OAuth redirect: ?connected=oura
    const params = new URLSearchParams(window.location.search);
    const connected = params.get("connected");
    if (connected) {
      setNotice(`${SOURCE_LABELS[connected] ?? connected} connected.`);
      // Strip the param so a later refresh doesn't re-show a stale banner
      params.delete("connected");
      const query = params.toString();
      window.history.replaceState(
        {},
        "",
        window.location.pathname + (query ? `?${query}` : "")
      );
    }
  }, [refreshJobs]);

  const hasActiveJob =
    jobs?.some((j) => j.status === "running" || j.status === "pending") ?? false;

  useEffect(() => {
    if (!hasActiveJob) return;
    const id = setInterval(refreshJobs, 3000);
    return () => clearInterval(id);
  }, [hasActiveJob, refreshJobs]);

  const trigger = async (
    action: () => Promise<{ job_id: string }>,
    label: string
  ): Promise<boolean> => {
    setNotice(null);
    setError(null);
    try {
      await action();
      setNotice(`${label} started.`);
      refreshJobs();
      return true;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
      return false;
    }
  };

  // Guards Sync now / Backfill weather against double-submit; upload has
  // its own `uploading` state since it also disables the file picker.
  const triggerGuarded = async (
    key: string,
    action: () => Promise<{ job_id: string }>,
    label: string
  ) => {
    if (busyAction) return;
    setBusyAction(key);
    await trigger(action, label);
    setBusyAction(null);
  };

  const uploadExport = async () => {
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      setError("Choose your Apple Health export.zip first.");
      return;
    }
    setUploading(true);
    const ok = await trigger(() => api.uploadAppleHealth(file), "Apple Health import");
    setUploading(false);
    // Only clear the picked file once the upload actually succeeded —
    // clearing it after a failure forced re-picking the file to retry.
    if (ok && fileInputRef.current) fileInputRef.current.value = "";
  };

  return (
    <div>
      <h1 className="text-2xl font-medium mb-6">Settings</h1>

      {notice && (
        <div className="p-4 mb-4 bg-green-50 border border-green-200 rounded text-sm text-green-900">
          {notice}
        </div>
      )}
      {error && (
        <div className="p-4 mb-4 bg-red-50 border border-red-200 rounded text-sm text-red-900">
          {error}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 mb-8">
        <div className="bg-white border border-gray-200 rounded p-5">
          <h2 className="font-medium mb-1">Oura</h2>
          <p className="text-sm text-gray-600 mb-4">
            Sleep, readiness, and recovery via OAuth.
          </p>
          <div className="flex gap-3">
            {/* Plain link: the OAuth dance is redirects, not fetch */}
            <a
              href={`${API_URL}/integrations/oura/authorize`}
              className="bg-gray-900 text-white px-3 py-1.5 rounded text-sm hover:bg-gray-700"
            >
              Connect
            </a>
            <button
              onClick={() => triggerGuarded("oura-sync", api.syncOura, "Oura sync")}
              disabled={busyAction === "oura-sync"}
              className="border border-gray-300 px-3 py-1.5 rounded text-sm hover:bg-gray-50 disabled:opacity-50"
            >
              {busyAction === "oura-sync" ? "Syncing…" : "Sync now"}
            </button>
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded p-5">
          <h2 className="font-medium mb-1">Apple Health</h2>
          <p className="text-sm text-gray-600 mb-4">
            Runs and glucose from your export.zip (Settings → Health → Export
            All Health Data).
          </p>
          <div className="flex gap-3 items-center">
            <input
              ref={fileInputRef}
              type="file"
              accept=".zip"
              className="text-sm text-gray-600 file:mr-3 file:border file:border-gray-300 file:rounded file:px-3 file:py-1.5 file:text-sm file:bg-white file:hover:bg-gray-50"
            />
            <button
              onClick={uploadExport}
              disabled={uploading}
              className="bg-gray-900 text-white px-3 py-1.5 rounded text-sm hover:bg-gray-700 disabled:opacity-50"
            >
              {uploading ? "Uploading…" : "Upload"}
            </button>
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded p-5">
          <h2 className="font-medium mb-1">Weather</h2>
          <p className="text-sm text-gray-600 mb-4">
            Backfill Open-Meteo conditions for runs that are missing weather.
          </p>
          <button
            onClick={() =>
              triggerGuarded("weather-backfill", api.backfillWeather, "Weather backfill")
            }
            disabled={busyAction === "weather-backfill"}
            className="border border-gray-300 px-3 py-1.5 rounded text-sm hover:bg-gray-50 disabled:opacity-50"
          >
            {busyAction === "weather-backfill" ? "Backfilling…" : "Backfill weather"}
          </button>
        </div>
      </div>

      <h2 className="font-medium mb-3">Import jobs</h2>
      {jobs === null ? (
        <div className="text-gray-500">Loading jobs…</div>
      ) : jobs.length === 0 ? (
        <div className="text-sm text-gray-500">No imports yet.</div>
      ) : (
        <div className="bg-white border border-gray-200 rounded overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-600 text-left">
              <tr>
                <th className="px-4 py-3 font-medium">Source</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium text-right">Imported</th>
                <th className="px-4 py-3 font-medium">Started</th>
                <th className="px-4 py-3 font-medium">Error</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id} className="border-t border-gray-100">
                  <td className="px-4 py-3">
                    {SOURCE_LABELS[job.source] ?? job.source}
                  </td>
                  <td className="px-4 py-3">
                    <JobStatusBadge status={job.status} />
                  </td>
                  <td className="px-4 py-3 text-right">
                    {job.items_imported}
                    {job.items_total !== null && job.items_total !== job.items_imported
                      ? ` / ${job.items_total}`
                      : ""}
                  </td>
                  <td className="px-4 py-3 text-gray-600">
                    {job.started_at
                      ? new Date(job.started_at).toLocaleString()
                      : "—"}
                  </td>
                  <td
                    className="px-4 py-3 text-red-700 max-w-xs truncate"
                    title={job.error_message ?? undefined}
                  >
                    {job.error_message ?? ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
