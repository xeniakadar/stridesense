from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from app.services.training_load import _zone


def _run_payload(run_date: date, **overrides) -> dict:
    return {
        "date": run_date.isoformat(),
        "run_type": "easy",
        "distance_km": 8.0,
        "duration_seconds": 2700,
        "perceived_effort": 4,
    } | overrides


def test_acwr_zone_classification() -> None:
    assert _zone(1.0) == "optimal"
    assert _zone(1.4) == "caution"
    assert _zone(1.6) == "danger"
    assert _zone(0.5) == "detraining"
    assert _zone(None) == "building"


async def test_similar_runs_endpoint_shape(client: AsyncClient, isolated_user) -> None:
    today = date.today()
    target = (
        await client.post("/runs", json=_run_payload(today, distance_km=8.0))
    ).json()
    await client.post(
        "/runs", json=_run_payload(today - timedelta(days=2), distance_km=8.2)
    )

    res = await client.get(f"/runs/{target['id']}/similar")
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body, list)
    assert len(body) == 1  # the only other run for this isolated user
    for item in body:
        assert 0.0 <= item["score"] <= 1.0
        assert item["run_id"] != target["id"]


async def test_training_load_endpoint(client: AsyncClient, isolated_user) -> None:
    await client.post("/runs", json=_run_payload(date.today()))

    res = await client.get("/analytics/training-load")
    assert res.status_code == 200
    points = res.json()
    assert len(points) > 0
    for point in points:
        assert point["zone"] in {"detraining", "optimal", "caution", "danger", "building"}


async def test_insight_endpoint_generates_and_caches(
    client: AsyncClient, isolated_user
) -> None:
    fake_text = "This easy run sat comfortably in your optimal training zone."
    created = (
        await client.post("/runs", json=_run_payload(date(2026, 6, 1)))
    ).json()

    with patch(
        "app.api.runs.generate_insight",           # patch where it's LOOKED UP
        new=AsyncMock(return_value=fake_text),
    ) as mock_generate:
        first = await client.get(f"/runs/{created['id']}/insight")
        assert first.status_code == 200
        assert first.json()["content"] == fake_text
        assert mock_generate.await_count == 1

        second = await client.get(f"/runs/{created['id']}/insight")
        assert second.status_code == 200
        assert second.json()["content"] == fake_text
        assert mock_generate.await_count == 1     # cached — NOT called again


async def test_insight_unavailable_returns_503(
    client: AsyncClient, isolated_user
) -> None:
    from app.services.insights import InsightUnavailableError

    created = (
        await client.post(
            "/runs",
            json=_run_payload(date(2026, 6, 2), distance_km=6.0, duration_seconds=2100),
        )
    ).json()

    with patch(
        "app.api.runs.generate_insight",
        new=AsyncMock(side_effect=InsightUnavailableError("no key")),
    ):
        res = await client.get(f"/runs/{created['id']}/insight")
        assert res.status_code == 503
