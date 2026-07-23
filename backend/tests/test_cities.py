from datetime import date, timedelta
from uuid import uuid4

from httpx import AsyncClient

from app.models import Run
from app.models.enums import RunType, RunTypeSource
from app.services.cities import cluster_cities


def _run(**overrides) -> Run:
    defaults = dict(
        id=uuid4(),
        date=date(2025, 6, 1),
        run_type=RunType.EASY,
        run_type_source=RunTypeSource.USER,
        distance_km=8.0,
        duration_seconds=2700,
        start_lat=38.72,
        start_lng=-9.14,
    )
    return Run(**defaults | overrides)


# --- clustering + lookup resolution ---


def test_nearby_points_merge_into_one_known_city() -> None:
    runs = [
        _run(start_lat=38.72, start_lng=-9.14),
        _run(date=date(2025, 6, 2), start_lat=38.73, start_lng=-9.15),
        _run(date=date(2025, 6, 3), start_lat=38.71, start_lng=-9.10),
    ]
    cities, unlocated = cluster_cities(runs)
    assert unlocated == 0
    assert len(cities) == 1
    lisbon = cities[0]
    assert (lisbon.name, lisbon.country_code) == ("Lisbon", "PT")
    assert (lisbon.lat, lisbon.lng) == (38.72, -9.14)  # canonical coords
    assert lisbon.run_count == 3
    assert lisbon.total_km == 24.0


def test_distinct_cities_stay_separate() -> None:
    runs = [
        _run(start_lat=40.78, start_lng=-73.97),  # New York
        _run(start_lat=41.88, start_lng=-87.62),  # Chicago
        _run(start_lat=7.89, start_lng=98.40),  # Phuket
    ]
    cities, _ = cluster_cities(runs)
    assert {c.name for c in cities} == {"New York", "Chicago", "Phuket"}
    assert all(c.run_count == 1 for c in cities)


def test_unknown_cluster_returns_its_own_coords() -> None:
    runs = [_run(start_lat=51.51, start_lng=-0.13)]  # London — not in the table
    cities, _ = cluster_cities(runs)
    assert len(cities) == 1
    unknown = cities[0]
    assert unknown.name == "Unknown"
    assert unknown.country_code is None
    assert (unknown.lat, unknown.lng) == (51.51, -0.13)


def test_unlocated_runs_are_counted_not_clustered() -> None:
    runs = [
        _run(),
        _run(date=date(2025, 6, 2), start_lat=None, start_lng=None),
        _run(date=date(2025, 6, 3), start_lat=None, start_lng=None),
    ]
    cities, unlocated = cluster_cities(runs)
    assert unlocated == 2
    assert len(cities) == 1
    assert cities[0].run_count == 1


def test_stats_dates_temps_and_race_flag() -> None:
    runs = [
        _run(date=date(2025, 2, 1), weather_temp_start_c=12.0),
        _run(date=date(2025, 8, 1), weather_temp_start_c=24.5),
        _run(date=date(2025, 5, 11), run_type=RunType.RACE),  # no temp on this one
    ]
    cities, _ = cluster_cities(runs)
    lisbon = cities[0]
    assert lisbon.first_run_date == date(2025, 2, 1)
    assert lisbon.last_run_date == date(2025, 8, 1)
    assert (lisbon.min_temp_c, lisbon.max_temp_c) == (12.0, 24.5)
    assert lisbon.has_race is True


def test_temps_none_when_no_weather() -> None:
    cities, _ = cluster_cities([_run()])
    assert cities[0].min_temp_c is None
    assert cities[0].max_temp_c is None


def test_sorted_by_run_count_desc() -> None:
    runs = [_run(date=date(2025, 6, 1) + timedelta(days=i)) for i in range(3)] + [
        _run(start_lat=41.88, start_lng=-87.62)
    ]
    cities, _ = cluster_cities(runs)
    assert [c.name for c in cities] == ["Lisbon", "Chicago"]


# --- endpoint shape ---


async def test_cities_endpoint_shape(client: AsyncClient, isolated_user) -> None:
    def payload(d: date, lat: float | None, lng: float | None) -> dict:
        return {
            "date": d.isoformat(),
            "run_type": "easy",
            "distance_km": 10.0,
            "duration_seconds": 3600,
            "start_lat": lat,
            "start_lng": lng,
        }

    await client.post("/runs", json=payload(date(2025, 6, 1), 40.78, -73.97))
    await client.post("/runs", json=payload(date(2025, 6, 3), 40.79, -73.99))
    await client.post("/runs", json=payload(date(2025, 6, 5), None, None))

    res = await client.get("/analytics/cities")
    assert res.status_code == 200
    body = res.json()

    assert set(body) == {"cities", "unlocated_count"}
    assert body["unlocated_count"] == 1
    assert len(body["cities"]) == 1
    nyc = body["cities"][0]
    assert nyc == {
        "name": "New York",
        "country_code": "US",
        "lat": 40.78,
        "lng": -73.97,
        "run_count": 2,
        "total_km": 20.0,
        "first_run_date": "2025-06-01",
        "last_run_date": "2025-06-03",
        "min_temp_c": None,
        "max_temp_c": None,
        "has_race": False,
    }
