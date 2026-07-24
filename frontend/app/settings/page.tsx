"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api, API_URL, ApiError } from "@/lib/api";
import type { ImportJob, ImportJobStatus } from "@/lib/types";

const STATUS_STYLES: Record<ImportJobStatus, string> = {
  pending: "bg-line/70 text-clay",
  running: "bg-amber-50 text-amber-700 animate-pulse",
  completed: "bg-leaf-pale text-leaf-deep",
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
      className={`inline-block px-2 py-0.5 rounded-full text-[11px] font-medium ${STATUS_STYLES[status]}`}
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
      <h1 className="text-[32px] font-medium text-ink leading-tight mb-5">Settings</h1>

      {notice && (
        <div className="p-4 mb-4 bg-leaf-pale border-[0.5px] border-leaf-soft rounded-2xl text-sm text-leaf-deep">
          {notice}
        </div>
      )}
      {error && (
        <div className="p-4 mb-4 bg-red-50 border border-red-200 rounded-2xl text-sm text-red-900">
          {error}
        </div>
      )}

      <div className="space-y-3 mb-8">
        <div className="bg-white border-[0.5px] border-line rounded-2xl p-4">
          <h2 className="text-[13px] font-medium text-ink mb-1">Oura</h2>
          <p className="text-xs text-sand mb-3.5">
            Sleep, readiness, and recovery via OAuth.
          </p>
          <div className="flex gap-3">
            {/* Plain link: the OAuth dance is redirects, not fetch */}
            <a
              href={`${API_URL}/integrations/oura/authorize`}
              className="bg-ink text-cream px-3.5 py-1.5 rounded-full text-xs hover:bg-clay"
            >
              Connect
            </a>
            <button
              onClick={() => triggerGuarded("oura-sync", api.syncOura, "Oura sync")}
              disabled={busyAction === "oura-sync"}
              className="border-[0.5px] border-line text-clay px-3.5 py-1.5 rounded-full text-xs hover:bg-line/50 disabled:opacity-50"
            >
              {busyAction === "oura-sync" ? "Syncing…" : "Sync now"}
            </button>
          </div>
        </div>

        <div className="bg-white border-[0.5px] border-line rounded-2xl p-4">
          <h2 className="text-[13px] font-medium text-ink mb-1">Apple Health</h2>
          <p className="text-xs text-sand mb-3.5">
            Runs and glucose from your export.zip (Settings → Health → Export
            All Health Data).
          </p>
          <div className="flex gap-3 items-center">
            <input
              ref={fileInputRef}
              type="file"
              accept=".zip"
              className="text-xs text-clay min-w-0 file:mr-3 file:border-[0.5px] file:border-line file:rounded-full file:px-3 file:py-1.5 file:text-xs file:bg-white file:text-clay file:hover:bg-line/50"
            />
            <button
              onClick={uploadExport}
              disabled={uploading}
              className="bg-ink text-cream px-3.5 py-1.5 rounded-full text-xs hover:bg-clay disabled:opacity-50"
            >
              {uploading ? "Uploading…" : "Upload"}
            </button>
          </div>
        </div>

        <div className="bg-white border-[0.5px] border-line rounded-2xl p-4">
          <h2 className="text-[13px] font-medium text-ink mb-1">Weather</h2>
          <p className="text-xs text-sand mb-3.5">
            Backfill Open-Meteo conditions for runs that are missing weather.
          </p>
          <button
            onClick={() =>
              triggerGuarded("weather-backfill", api.backfillWeather, "Weather backfill")
            }
            disabled={busyAction === "weather-backfill"}
            className="border-[0.5px] border-line text-clay px-3.5 py-1.5 rounded-full text-xs hover:bg-line/50 disabled:opacity-50"
          >
            {busyAction === "weather-backfill" ? "Backfilling…" : "Backfill weather"}
          </button>
        </div>
      </div>

      <h2 className="text-[13px] font-medium text-ink mb-2 px-1">Import jobs</h2>
      {jobs === null ? (
        <div className="text-sand text-sm">Loading jobs…</div>
      ) : jobs.length === 0 ? (
        <div className="text-sm text-sand">No imports yet.</div>
      ) : (
        <div className="space-y-1.5">
          {jobs.map((job) => (
            <div
              key={job.id}
              className="bg-white border-[0.5px] border-line rounded-2xl px-3.5 py-2.5"
            >
              <div className="flex justify-between items-center">
                <span className="text-[13px] text-ink">
                  {SOURCE_LABELS[job.source] ?? job.source}
                </span>
                <JobStatusBadge status={job.status} />
              </div>
              <p className="text-[11px] text-sand mt-0.5">
                {job.items_imported}
                {job.items_total !== null && job.items_total !== job.items_imported
                  ? ` / ${job.items_total}`
                  : ""}{" "}
                imported
                {job.started_at
                  ? ` · ${new Date(job.started_at).toLocaleString()}`
                  : ""}
              </p>
              {job.error_message && (
                <p
                  className="text-[11px] text-red-700 mt-0.5 truncate"
                  title={job.error_message}
                >
                  {job.error_message}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
