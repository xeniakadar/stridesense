from datetime import date, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GlucoseDailyRecord
from app.models.enums import DataSource


def _run_payload(run_date: date, distance_km: float, duration_seconds: int) -> dict:
    return {
        "date": run_date.isoformat(),
        "run_type": "easy",
        "distance_km": distance_km,
        "duration_seconds": duration_seconds,
    }


# --- records ---


async def test_records_distance_tolerance_and_pace_ranking(
    client: AsyncClient, isolated_user
) -> None:
    today = date.today()
    # 4.7 km is outside the 4.8-5.5 "5K" band even at absurd pace
    await client.post("/runs", json=_run_payload(today - timedelta(days=1), 4.7, 1000))
    # In-band: 5.0 km @ 300 s/km beats 5.4 km @ 350 s/km
    in_band = (
        await client.post(
            "/runs", json=_run_payload(today - timedelta(days=2), 5.0, 1500)
        )
    ).json()
    await client.post("/runs", json=_run_payload(today - timedelta(days=3), 5.4, 1890))

    res = await client.get("/analytics/records")
    assert res.status_code == 200
    by_kind = {r["kind"]: r for r in res.json()}

    fastest_5k = by_kind["fastest_5k"]
    assert fastest_5k["run_id"] == in_band["id"]
    assert fastest_5k["avg_pace_seconds_per_km"] == 300.0
    # No 10K/half candidates -> those kinds are absent entirely
    assert "fastest_10k" not in by_kind
    assert "fastest_half" not in by_kind


async def test_records_longest_run_and_biggest_week(
    client: AsyncClient, isolated_user
) -> None:
    # Two mondays apart: week A totals 30 km, week B has the single 21 km longest
    week_a_monday = date(2026, 6, 1)  # a Monday
    week_b_monday = date(2026, 6, 8)
    await client.post("/runs", json=_run_payload(week_a_monday, 15.0, 5400))
    await client.post(
        "/runs", json=_run_payload(week_a_monday + timedelta(days=2), 15.0, 5400)
    )
    longest = (
        await client.post("/runs", json=_run_payload(week_b_monday, 21.0, 7560))
    ).json()

    res = await client.get("/analytics/records")
    by_kind = {r["kind"]: r for r in res.json()}

    assert by_kind["longest_run"]["run_id"] == longest["id"]
    assert by_kind["longest_run"]["distance_km"] == 21.0

    biggest = by_kind["biggest_week"]
    assert biggest["run_id"] is None  # a week is not one run
    assert biggest["date"] == week_a_monday.isoformat()
    assert biggest["distance_km"] == 30.0
    assert biggest["duration_seconds"] is None


async def test_records_empty_history(client: AsyncClient, isolated_user) -> None:
    res = await client.get("/analytics/records")
    assert res.status_code == 200
    assert res.json() == []


# --- monthly volume ---


async def test_monthly_volume_buckets_and_fills_12_months(
    client: AsyncClient, isolated_user
) -> None:
    today = date.today()
    this_month = date(today.year, today.month, 1)
    await client.post("/runs", json=_run_payload(this_month, 10.0, 3600))
    await client.post(
        "/runs", json=_run_payload(min(this_month + timedelta(days=14), today), 5.0, 1800)
    )
    # ~6 months back, and one older than the window (ignored)
    six_back = this_month - timedelta(days=180)
    await client.post("/runs", json=_run_payload(six_back, 8.0, 2880))
    await client.post(
        "/runs", json=_run_payload(this_month - timedelta(days=400), 99.0, 30000)
    )

    res = await client.get("/analytics/monthly-volume")
    assert res.status_code == 200
    points = res.json()

    assert len(points) == 12  # empty months included
    assert points[-1]["month"] == this_month.isoformat()
    assert points[-1]["distance_km"] == 15.0
    by_month = {p["month"]: p["distance_km"] for p in points}
    assert by_month[date(six_back.year, six_back.month, 1).isoformat()] == 8.0
    assert 99.0 not in by_month.values()
    assert sum(p["distance_km"] for p in points) == 23.0


# --- glucose TIR trend ---


async def test_glucose_trend_series_shape(
    client: AsyncClient, session: AsyncSession, isolated_user
) -> None:
    today = date.today()
    session.add_all(
        [
            GlucoseDailyRecord(
                user_id=isolated_user.id,
                date=today - timedelta(days=1),
                source=DataSource.MANUAL,
                time_in_range_pct=91.5,
            ),
            GlucoseDailyRecord(
                user_id=isolated_user.id,
                date=today - timedelta(days=3),
                source=DataSource.MANUAL,
                time_in_range_pct=84.0,
            ),
            # Outside the 90-day window
            GlucoseDailyRecord(
                user_id=isolated_user.id,
                date=today - timedelta(days=120),
                source=DataSource.MANUAL,
                time_in_range_pct=70.0,
            ),
            # No TIR value -> excluded
            GlucoseDailyRecord(
                user_id=isolated_user.id,
                date=today - timedelta(days=2),
                source=DataSource.MANUAL,
                time_in_range_pct=None,
            ),
        ]
    )
    await session.commit()

    res = await client.get("/analytics/glucose-trend")
    assert res.status_code == 200
    assert res.json() == [
        {"date": (today - timedelta(days=3)).isoformat(), "time_in_range_pct": 84.0},
        {"date": (today - timedelta(days=1)).isoformat(), "time_in_range_pct": 91.5},
    ]


async def test_glucose_trend_empty_without_data(
    client: AsyncClient, isolated_user
) -> None:
    res = await client.get("/analytics/glucose-trend")
    assert res.status_code == 200
    assert res.json() == []
