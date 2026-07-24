"use client";

import { ArrowLeft } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { flagEmoji } from "@/lib/format";
import type { CitiesResponse, CityStats } from "@/lib/types";

// Leaflet touches window at import time — client-only, no SSR
const CityMap = dynamic(
  () => import("@/components/CityMap").then((m) => m.CityMap),
  {
    ssr: false,
    loading: () => (
      <div className="h-full flex items-center justify-center text-sm text-sand">
        Loading map…
      </div>
    ),
  }
);

function viewRunsHref(city: CityStats): string {
  return `/runs?city=${encodeURIComponent(city.name)}&lat=${city.lat}&lng=${city.lng}`;
}

export default function CitiesPage() {
  const [data, setData] = useState<CitiesResponse | null>(null);
  const [error, setError] = useState(false);
  const [view, setView] = useState<"list" | "map">("list");

  useEffect(() => {
    api
      .getCities()
      .then(setData)
      .catch(() => setError(true));
  }, []);

  if (error) {
    return <p className="text-sm text-red-700">Couldn't load cities.</p>;
  }
  if (!data) {
    return <p className="text-sm text-sand">Loading…</p>;
  }

  const countries = new Set(
    data.cities.map((c) => c.country_code).filter(Boolean)
  ).size;

  return (
    <div className="space-y-3">
      {/* Header — the screen's single gradient surface */}
      <div className="hero-gradient rounded-3xl px-5 pt-4 pb-4">
        <div className="flex items-center justify-between">
          <Link href="/trends" aria-label="Back to trends" className="text-clay-hero">
            <ArrowLeft size={18} strokeWidth={1.75} />
          </Link>
          <p className="text-[13px] font-medium text-ink">Cities</p>
          <span className="w-[18px]" />
        </div>
        <p className="mt-2.5 text-2xl font-medium text-ink leading-none">
          {data.cities.length} {data.cities.length === 1 ? "city" : "cities"} ·{" "}
          {countries} {countries === 1 ? "country" : "countries"}
        </p>
        <div className="inline-flex mt-3 bg-white/55 rounded-full p-[3px]">
          {(["list", "map"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`text-[11.5px] px-4 py-1 rounded-full capitalize ${
                view === v ? "bg-white text-leaf-deep font-medium" : "text-clay-hero"
              }`}
            >
              {v}
            </button>
          ))}
        </div>
      </div>

      {view === "list" ? (
        <div className="space-y-1.5">
          {data.cities.map((city) => (
            <div
              key={`${city.name}-${city.lat}-${city.lng}`}
              className="bg-white border-[0.5px] border-line rounded-2xl px-3.5 py-3"
            >
              <div className="flex justify-between items-center">
                <p className="text-[13.5px] font-medium text-ink">
                  {flagEmoji(city.country_code)} {city.name}
                </p>
                {city.has_race && (
                  <span className="text-[10.5px] font-medium text-ember">
                    race
                  </span>
                )}
              </div>
              <p className="mt-0.5 text-[11.5px] text-clay">
                {city.run_count} run{city.run_count === 1 ? "" : "s"} ·{" "}
                {city.total_km} km
              </p>
              <Link
                href={viewRunsHref(city)}
                className="inline-block mt-1 text-[11px] font-medium text-leaf hover:underline"
              >
                View runs →
              </Link>
            </div>
          ))}
          {data.unlocated_count > 0 && (
            <p className="text-[11px] text-sand px-1 pt-1">
              {data.unlocated_count} run
              {data.unlocated_count === 1 ? "" : "s"} without location
            </p>
          )}
        </div>
      ) : (
        <div className="h-[calc(100dvh-19rem)] min-h-[320px] rounded-2xl overflow-hidden border-[0.5px] border-line">
          <CityMap cities={data.cities} />
        </div>
      )}
    </div>
  );
}
