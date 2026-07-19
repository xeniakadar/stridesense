import type {
  ImportJob,
  JobAccepted,
  Run,
  RunCreate,
  RunUpdate,
  WeeklyMileagePoint,
  PaceTrendPoint,
  RunTypeDistributionItem,
  LoadPoint,
  SimilarRun,
} from "@/lib/types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // FormData bodies must NOT get a JSON Content-Type — the browser sets
  // the multipart boundary itself
  const headers: HeadersInit =
    init?.body instanceof FormData
      ? { ...(init?.headers ?? {}) }
      : { "Content-Type": "application/json", ...(init?.headers ?? {}) };
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore body parse error
    }
    throw new ApiError(res.status, detail);
  }

  // 204 No Content
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  listRuns: () => request<Run[]>("/runs"),
  getRun: (id: string) => request<Run>(`/runs/${id}`),
  createRun: (data: RunCreate) =>
    request<Run>("/runs", { method: "POST", body: JSON.stringify(data) }),
  updateRun: (id: string, data: RunUpdate) =>
    request<Run>(`/runs/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteRun: (id: string) => request<void>(`/runs/${id}`, { method: "DELETE" }),

  // Analytics
  weeklyMileage: () =>
    request<WeeklyMileagePoint[]>("/analytics/weekly-mileage"),

  paceTrend: () => request<PaceTrendPoint[]>("/analytics/pace-trend"),

  runTypeDistribution: () =>
    request<RunTypeDistributionItem[]>("/analytics/run-type-distribution"),

  getSimilarRuns: (id: string) => request<SimilarRun[]>(`/runs/${id}/similar`),

  getTrainingLoad: () => request<LoadPoint[]>(`/analytics/training-load`),

  getInsight: (id: string) =>
    request<{
      id: string;
      run_id: string;
      content: string;
      model: string;
      created_at: string;
    }>(`/runs/${id}/insight`),

  // Integrations
  listImportJobs: () => request<ImportJob[]>("/integrations/jobs"),

  syncOura: () => request<JobAccepted>("/integrations/oura/sync", { method: "POST" }),

  backfillWeather: () =>
    request<JobAccepted>("/integrations/weather/backfill", { method: "POST" }),

  uploadAppleHealth: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<JobAccepted>("/integrations/apple-health/upload", {
      method: "POST",
      body: form,
    });
  },
};
