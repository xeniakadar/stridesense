"""Group runs into cities by coordinate cluster.

Runs carry 2-decimal coordinates (city centers in the demo dataset,
snapped exports otherwise). Clustering is a greedy merge: points within
CLUSTER_RADIUS_DEG of a cluster's running-mean center join it. Each
cluster then resolves against a lookup table of known cities; clusters
that resolve to the same city merge, unresolvable ones surface as
"Unknown" with their own coordinates, and runs with no coordinates at
all are only counted.
"""

import math
from dataclasses import dataclass
from datetime import date

from app.models import Run
from app.models.enums import RunType

CLUSTER_RADIUS_DEG = 0.15

# (name, ISO 3166-1 alpha-2 country code, lat, lng)
KNOWN_CITIES: list[tuple[str, str, float, float]] = [
    ("Phuket", "TH", 7.89, 98.40),
    ("Hanoi", "VN", 21.03, 105.85),
    ("Budapest", "HU", 47.51, 19.05),
    ("Lisbon", "PT", 38.72, -9.14),
    ("New York", "US", 40.78, -73.97),
    ("Chicago", "US", 41.88, -87.62),
    ("San Francisco", "US", 37.77, -122.42),
]


@dataclass
class CityStats:
    name: str
    country_code: str | None  # None for unresolved clusters
    lat: float
    lng: float
    run_count: int
    total_km: float
    first_run_date: date
    last_run_date: date
    min_temp_c: float | None  # over weather_temp_start_c where present
    max_temp_c: float | None
    has_race: bool


def _distance_deg(a_lat: float, a_lng: float, b_lat: float, b_lng: float) -> float:
    return math.sqrt((a_lat - b_lat) ** 2 + (a_lng - b_lng) ** 2)


def _resolve(lat: float, lng: float) -> tuple[str, str | None, float, float]:
    """Nearest known city within the cluster radius, else Unknown at the
    cluster's own (rounded) center."""
    best = min(
        KNOWN_CITIES, key=lambda c: _distance_deg(lat, lng, c[2], c[3])
    )
    if _distance_deg(lat, lng, best[2], best[3]) <= CLUSTER_RADIUS_DEG:
        return best[0], best[1], best[2], best[3]
    return "Unknown", None, round(lat, 2), round(lng, 2)


def cluster_cities(runs: list[Run]) -> tuple[list[CityStats], int]:
    """(per-city stats sorted by run count, count of runs without coords)."""
    located = [r for r in runs if r.start_lat is not None and r.start_lng is not None]
    unlocated_count = len(runs) - len(located)

    # Greedy clustering with running-mean centers, in date order so the
    # result doesn't depend on query ordering
    clusters: list[dict] = []  # {lat, lng, runs}
    for run in sorted(located, key=lambda r: (r.date, r.id.hex)):
        for cluster in clusters:
            if (
                _distance_deg(run.start_lat, run.start_lng, cluster["lat"], cluster["lng"])
                <= CLUSTER_RADIUS_DEG
            ):
                members = cluster["runs"]
                members.append(run)
                cluster["lat"] += (run.start_lat - cluster["lat"]) / len(members)
                cluster["lng"] += (run.start_lng - cluster["lng"]) / len(members)
                break
        else:
            clusters.append({"lat": run.start_lat, "lng": run.start_lng, "runs": [run]})

    # Resolve clusters to cities; two clusters can land on the same city
    by_city: dict[tuple[str, float, float], dict] = {}
    for cluster in clusters:
        name, country_code, lat, lng = _resolve(cluster["lat"], cluster["lng"])
        group = by_city.setdefault(
            (name, lat, lng), {"country_code": country_code, "runs": []}
        )
        group["runs"].extend(cluster["runs"])

    cities: list[CityStats] = []
    for (name, lat, lng), group in by_city.items():
        members: list[Run] = group["runs"]
        temps = [
            r.weather_temp_start_c for r in members if r.weather_temp_start_c is not None
        ]
        cities.append(
            CityStats(
                name=name,
                country_code=group["country_code"],
                lat=lat,
                lng=lng,
                run_count=len(members),
                total_km=round(sum(r.distance_km for r in members), 1),
                first_run_date=min(r.date for r in members),
                last_run_date=max(r.date for r in members),
                min_temp_c=round(min(temps), 1) if temps else None,
                max_temp_c=round(max(temps), 1) if temps else None,
                has_race=any(r.run_type == RunType.RACE for r in members),
            )
        )

    cities.sort(key=lambda c: (-c.run_count, c.name))
    return cities, unlocated_count
