from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RunGlucoseSample
from app.models.enums import DataSource
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
    assert len(body["runs"]) == 1  # the only other run for this isolated user
    for item in body["runs"]:
        assert 0.0 <= item["score"] <= 1.0
        assert item["run_id"] != target["id"]


async def test_glucose_samples_endpoint_shape_and_order(
    client: AsyncClient, session: AsyncSession, isolated_user
) -> None:
    created = (
        await client.post("/runs", json=_run_payload(date(2026, 6, 5)))
    ).json()
    run_id = created["id"]
    started_at = datetime(2026, 6, 5, 7, 0, tzinfo=UTC)

    # Inserted out of order — the endpoint must sort by elapsed_seconds
    session.add_all(
        [
            RunGlucoseSample(
                run_id=run_id,
                elapsed_seconds=600,
                observed_at=started_at + timedelta(seconds=600),
                glucose_mg_dl=110.0,
                trend="rising",
                source=DataSource.LINX_CGM,
            ),
            RunGlucoseSample(
                run_id=run_id,
                elapsed_seconds=0,
                observed_at=started_at,
                glucose_mg_dl=95.0,
                trend=None,
                source=DataSource.LINX_CGM,
            ),
        ]
    )
    await session.commit()

    res = await client.get(f"/runs/{run_id}/glucose-samples")
    assert res.status_code == 200
    body = res.json()
    assert body == [
        {
            "elapsed_seconds": 0,
            "glucose_mg_dl": 95.0,
            "trend": None,
            "source": "linx_cgm",
        },
        {
            "elapsed_seconds": 600,
            "glucose_mg_dl": 110.0,
            "trend": "rising",
            "source": "linx_cgm",
        },
    ]


async def test_glucose_samples_endpoint_empty(
    client: AsyncClient, isolated_user
) -> None:
    created = (
        await client.post("/runs", json=_run_payload(date(2026, 6, 6)))
    ).json()

    res = await client.get(f"/runs/{created['id']}/glucose-samples")
    assert res.status_code == 200
    assert res.json() == []


async def test_glucose_samples_endpoint_not_found(client: AsyncClient, isolated_user) -> None:
    res = await client.get(f"/runs/{uuid4()}/glucose-samples")
    assert res.status_code == 404


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


async def test_regenerate_insight_replaces_cached_content(
    client: AsyncClient, isolated_user
) -> None:
    created = (
        await client.post("/runs", json=_run_payload(date(2026, 6, 3)))
    ).json()

    with patch(
        "app.api.runs.generate_insight",           # patch where it's LOOKED UP
        new=AsyncMock(return_value="original narration"),
    ):
        first = await client.get(f"/runs/{created['id']}/insight")
        assert first.status_code == 200
        assert first.json()["content"] == "original narration"

    with patch(
        "app.api.runs.generate_insight",
        new=AsyncMock(return_value="fresh narration"),
    ) as mock_generate:
        regenerated = await client.post(f"/runs/{created['id']}/insight/regenerate")
        assert regenerated.status_code == 200
        assert regenerated.json()["content"] == "fresh narration"
        assert mock_generate.await_count == 1

    # The old cached row is gone, not just superseded — GET returns the
    # regenerated content without calling generate_insight again
    with patch(
        "app.api.runs.generate_insight", new=AsyncMock()
    ) as mock_generate_after:
        again = await client.get(f"/runs/{created['id']}/insight")
        assert again.json()["content"] == "fresh narration"
        assert mock_generate_after.await_count == 0


async def test_regenerate_insight_unavailable_returns_503(
    client: AsyncClient, isolated_user
) -> None:
    from app.services.insights import InsightUnavailableError

    created = (
        await client.post("/runs", json=_run_payload(date(2026, 6, 4)))
    ).json()

    with patch(
        "app.api.runs.generate_insight",
        new=AsyncMock(side_effect=InsightUnavailableError("no key")),
    ):
        res = await client.post(f"/runs/{created['id']}/insight/regenerate")
        assert res.status_code == 503


async def test_regenerate_insight_not_found(client: AsyncClient, isolated_user) -> None:
    from uuid import uuid4

    res = await client.post(f"/runs/{uuid4()}/insight/regenerate")
    assert res.status_code == 404
