"use client";

import "leaflet/dist/leaflet.css";

import { latLngBounds } from "leaflet";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  CircleMarker,
  MapContainer,
  TileLayer,
  useMap,
  useMapEvents,
} from "react-leaflet";

import { LEAF, LEAF_MID, LEAF_SOFT } from "@/lib/colors";
import { flagEmoji, formatMonthYear } from "@/lib/format";
import type { CityStats } from "@/lib/types";

// Only ever rendered via next/dynamic with ssr:false — leaflet needs window.

function markerColor(runCount: number): string {
  if (runCount >= 100) return LEAF;
  if (runCount >= 25) return LEAF_MID;
  return LEAF_SOFT;
}

function markerRadius(runCount: number): number {
  return Math.min(16, 5 + 2 * Math.sqrt(runCount));
}

function FitToCities({ cities }: { cities: CityStats[] }) {
  const map = useMap();
  useEffect(() => {
    if (cities.length === 0) return;
    map.fitBounds(latLngBounds(cities.map((c) => [c.lat, c.lng])), {
      padding: [30, 30],
      maxZoom: 6,
    });
  }, [map, cities]);
  return null;
}

function DismissOnMapTap({ onDismiss }: { onDismiss: () => void }) {
  useMapEvents({ click: () => onDismiss() });
  return null;
}

export function CityMap({ cities }: { cities: CityStats[] }) {
  const [selected, setSelected] = useState<CityStats | null>(null);
  const touchStartY = useRef<number | null>(null);

  return (
    <div className="relative h-full w-full">
      <MapContainer
        center={[30, 0]}
        zoom={2}
        scrollWheelZoom
        className="h-full w-full"
        attributionControl
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        />
        <FitToCities cities={cities} />
        <DismissOnMapTap onDismiss={() => setSelected(null)} />
        {cities.map((city) => (
          <CircleMarker
            key={`${city.name}-${city.lat}-${city.lng}`}
            center={[city.lat, city.lng]}
            radius={markerRadius(city.run_count)}
            pathOptions={{
              fillColor: markerColor(city.run_count),
              fillOpacity: 0.9,
              color: "#FDFBF7",
              weight: 2,
              // else the tap bubbles to the map and instantly dismisses
              // the sheet it just opened
              bubblingMouseEvents: false,
            }}
            eventHandlers={{ click: () => setSelected(city) }}
          />
        ))}
      </MapContainer>

      {selected && (
        <div
          className="absolute inset-x-2.5 bottom-2.5 z-[1000] bg-white border-[0.5px] border-line rounded-t-2xl rounded-b-xl px-4 pt-2.5 pb-3 shadow-[0_-4px_16px_rgba(74,46,28,0.12)]"
          onTouchStart={(e) => {
            touchStartY.current = e.touches[0].clientY;
          }}
          onTouchEnd={(e) => {
            const start = touchStartY.current;
            touchStartY.current = null;
            if (start !== null && e.changedTouches[0].clientY - start > 40) {
              setSelected(null);
            }
          }}
        >
          <div className="w-9 h-1 rounded-full bg-line mx-auto mb-2" />
          <div className="flex justify-between items-center">
            <p className="text-sm font-medium text-ink">
              {flagEmoji(selected.country_code)} {selected.name}
            </p>
            {selected.has_race && (
              <span className="text-[10.5px] font-medium text-ember">race</span>
            )}
          </div>
          <p className="mt-1 text-[11.5px] text-clay">
            {selected.run_count} run{selected.run_count === 1 ? "" : "s"} ·{" "}
            {selected.total_km} km · {dateRange(selected)}
            {selected.min_temp_c !== null && selected.max_temp_c !== null
              ? ` · ${Math.round(selected.min_temp_c)}–${Math.round(selected.max_temp_c)}°C`
              : ""}
          </p>
          <Link
            href={viewRunsHref(selected)}
            className="inline-block mt-1.5 text-[11px] font-medium text-leaf hover:underline"
          >
            View runs →
          </Link>
        </div>
      )}
    </div>
  );
}

function dateRange(city: CityStats): string {
  const first = formatMonthYear(city.first_run_date);
  const last = formatMonthYear(city.last_run_date);
  return first === last ? first : `${first} – ${last}`;
}

export function viewRunsHref(city: CityStats): string {
  return `/runs?city=${encodeURIComponent(city.name)}&lat=${city.lat}&lng=${city.lng}`;
}
