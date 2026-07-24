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

// Mirrors KNOWN_CITIES + CLUSTER_RADIUS_DEG in the backend
// (app/services/cities.py) — keep the two lists in sync
const KNOWN_CITIES: [string, number, number][] = [
  ["Phuket", 7.89, 98.4],
  ["Hanoi", 21.03, 105.85],
  ["Budapest", 47.51, 19.05],
  ["Lisbon", 38.72, -9.14],
  ["New York", 40.78, -73.97],
  ["Chicago", 41.88, -87.62],
  ["San Francisco", 37.77, -122.42],
];
const CITY_RADIUS_DEG = 0.15;

export function cityFromCoords(
  lat: number | null | undefined,
  lng: number | null | undefined
): string | null {
  if (lat == null || lng == null) return null;
  for (const [name, cityLat, cityLng] of KNOWN_CITIES) {
    if (Math.hypot(lat - cityLat, lng - cityLng) <= CITY_RADIUS_DEG) {
      return name;
    }
  }
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
