import { format, parseISO } from "date-fns";

export function formatPace(secondsPerKm: number | null | undefined): string {
  if (secondsPerKm == null || !isFinite(secondsPerKm) || secondsPerKm <= 0) {
    return "—";
  }
  // Round the total first so e.g. 419.6s renders 7:00, not 6:60
  const total = Math.round(secondsPerKm);
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}/km`;
}

export function formatDuration(seconds: number | null | undefined): string {
  if (!seconds) return "—";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, "0")}:${secs
      .toString()
      .padStart(2, "0")}`;
  }
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
}

export function formatDistance(km: number | null | undefined): string {
  if (km === null || km === undefined) return "—";
  return `${km.toFixed(1)} km`;
}

// For aggregates (weekly/city/monthly totals) — whole km read faster
export function formatKmTotal(km: number | null | undefined): string {
  if (km === null || km === undefined) return "—";
  return `${Math.round(km)} km`;
}

// Compact duration for axis ticks: "39m", "1:05h" — never raw decimals
export function formatMinutesShort(totalMinutes: number): string {
  const m = Math.round(totalMinutes);
  if (m < 60) return `${m}m`;
  return `${Math.floor(m / 60)}:${(m % 60).toString().padStart(2, "0")}h`;
}

export function formatDate(iso: string): string {
  return format(parseISO(iso), "MMM d, yyyy");
}

export function formatDateShort(iso: string): string {
  return format(parseISO(iso), "MMM d");
}

// For axes whose points can be years apart (e.g. comparable runs)
export function formatMonthYear(iso: string): string {
  return format(parseISO(iso), "MMM ''yy");
}

export function formatGlucose(mgDl: number | null | undefined): string {
  if (mgDl === null || mgDl === undefined) return "—";
  return `${Math.round(mgDl)} mg/dL`;
}

export function formatTimeInRange(pct: number | null | undefined): string {
  if (pct === null || pct === undefined) return "—";
  return `${Math.round(pct)}%`;
}

// ISO 3166-1 alpha-2 → flag emoji via regional-indicator codepoints
export function flagEmoji(countryCode: string | null): string {
  if (!countryCode || countryCode.length !== 2) return "📍";
  return String.fromCodePoint(
    ...[...countryCode.toUpperCase()].map(
      (c) => 0x1f1e6 + c.charCodeAt(0) - 65
    )
  );
}

// Same latitude buckets the backend uses in run_to_text (app/services/ask.py)
export function cityFromLat(lat: number | null | undefined): string | null {
  if (lat == null) return null;
  if (lat >= 47 && lat < 48) return "Budapest";
  if (lat >= 40 && lat < 41) return "NYC";
  if (lat >= 38 && lat < 39) return "Lisbon";
  if (lat >= 41 && lat < 42) return "Chicago";
  return null;
}

export const RUN_TYPE_LABELS: Record<string, string> = {
  easy: "Easy",
  long: "Long",
  interval: "Interval",
  tempo: "Tempo",
  recovery: "Recovery",
  race: "Race",
  other: "Other",
};
