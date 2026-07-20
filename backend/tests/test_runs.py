from datetime import date
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Run
from app.models.enums import RunTypeSource


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


async def test_create_run(client: AsyncClient, isolated_user) -> None:
    response = await client.post("/runs", json=_valid_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["distance_km"] == 8.5
    assert body["avg_pace_seconds_per_km"] == pytest.approx(2700 / 8.5, rel=1e-3)
    assert body["source"] == "manual"
    assert body["run_type_source"] == "user"


async def test_create_run_validates_distance(client: AsyncClient, isolated_user) -> None:
    bad = _valid_payload() | {"distance_km": -5}
    response = await client.post("/runs", json=bad)
    assert response.status_code == 422


async def test_list_runs_returns_array(client: AsyncClient, isolated_user) -> None:
    response = await client.get("/runs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_get_run_not_found(client: AsyncClient, isolated_user) -> None:
    response = await client.get(f"/runs/{uuid4()}")
    assert response.status_code == 404


async def test_update_run(client: AsyncClient, isolated_user) -> None:
    created = (await client.post("/runs", json=_valid_payload())).json()
    response = await client.put(
        f"/runs/{created['id']}",
        json={"perceived_effort": 7, "notes": "Updated."},
    )
    assert response.status_code == 200
    assert response.json()["perceived_effort"] == 7
    assert response.json()["notes"] == "Updated."


async def test_delete_run(client: AsyncClient, isolated_user) -> None:
    created = (await client.post("/runs", json=_valid_payload())).json()
    response = await client.delete(f"/runs/{created['id']}")
    assert response.status_code == 204
    follow_up = await client.get(f"/runs/{created['id']}")
    assert follow_up.status_code == 404


async def test_saving_run_type_marks_it_user_chosen(
    client: AsyncClient, isolated_user
) -> None:
    """A manually saved run_type must permanently opt the run out of
    classify_runs.py — that script only ever touches run_type_source ==
    DEFAULT rows."""
    created = (await client.post("/runs", json=_valid_payload())).json()
    assert created["run_type_source"] == "user"  # already true on create

    response = await client.put(
        f"/runs/{created['id']}", json={"run_type": "tempo"}
    )
    assert response.status_code == 200
    assert response.json()["run_type"] == "tempo"
    assert response.json()["run_type_source"] == "user"


async def test_updating_other_fields_leaves_run_type_source_untouched(
    client: AsyncClient, session: AsyncSession, isolated_user
) -> None:
    """A run classify_runs.py left as DEFAULT (or a prior INFERRED pass)
    must stay that way when the edit form saves fields OTHER than
    run_type — only an explicit run_type in the payload should flip it
    to USER."""
    run = Run(
        user_id=isolated_user.id,
        date=date.today(),
        distance_km=8.5,
        duration_seconds=2700,
        run_type_source=RunTypeSource.DEFAULT,
    )
    session.add(run)
    await session.commit()

    response = await client.put(
        f"/runs/{run.id}", json={"notes": "No run_type in this payload."}
    )
    assert response.status_code == 200
    assert response.json()["run_type_source"] == "default"
