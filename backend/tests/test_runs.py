from datetime import date
from uuid import uuid4

import pytest
from httpx import AsyncClient


def _valid_payload() -> dict:
    return {
        "date": date.today().isoformat(),
        "run_type": "easy",
        "distance_km": 8.5,
        "duration_seconds": 2700,
        "avg_hr": 148,
        "perceived_effort": 4,
        "notes": "Felt good, easy pace.",
    }


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200


async def test_create_run(client: AsyncClient) -> None:
    response = await client.post("/runs", json=_valid_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["distance_km"] == 8.5
    assert body["avg_pace_seconds_per_km"] == pytest.approx(2700 / 8.5, rel=1e-3)
    assert body["source"] == "manual"
    assert body["run_type_source"] == "user"


async def test_create_run_validates_distance(client: AsyncClient) -> None:
    bad = _valid_payload() | {"distance_km": -5}
    response = await client.post("/runs", json=bad)
    assert response.status_code == 422


async def test_list_runs_returns_array(client: AsyncClient) -> None:
    response = await client.get("/runs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_get_run_not_found(client: AsyncClient) -> None:
    response = await client.get(f"/runs/{uuid4()}")
    assert response.status_code == 404


async def test_update_run(client: AsyncClient) -> None:
    created = (await client.post("/runs", json=_valid_payload())).json()
    response = await client.put(
        f"/runs/{created['id']}",
        json={"perceived_effort": 7, "notes": "Updated."},
    )
    assert response.status_code == 200
    assert response.json()["perceived_effort"] == 7
    assert response.json()["notes"] == "Updated."


async def test_delete_run(client: AsyncClient) -> None:
    created = (await client.post("/runs", json=_valid_payload())).json()
    response = await client.delete(f"/runs/{created['id']}")
    assert response.status_code == 204
    follow_up = await client.get(f"/runs/{created['id']}")
    assert follow_up.status_code == 404
