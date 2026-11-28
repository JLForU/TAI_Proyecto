"""Tests de ``POST /api/v1/admin/reset`` (auth Bearer + limpieza del escenario)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import sample_batch


def test_reset_requires_ingest_token(client: TestClient) -> None:
    assert client.post("/api/v1/admin/reset").status_code == 401
    assert (
        client.post("/api/v1/admin/reset", headers={"Authorization": "Bearer wrong"}).status_code
        == 401
    )


def test_reset_clears_scenario(client: TestClient, auth: dict[str, str]) -> None:
    assert client.post("/api/v1/ingest", json=sample_batch(1), headers=auth).status_code == 202

    r = client.post("/api/v1/admin/reset", headers=auth)

    assert r.status_code == 200
    body = r.json()
    assert body["deleted"]["assets"] == 1
    assert body["deleted"]["observations"] >= 1
    assert body["total"] == sum(body["deleted"].values())
    assert client.get("/api/v1/assets").json()["total"] == 0
    assert client.get("/api/v1/health").json()["counts"] == {
        "assets": 0,
        "events": 0,
        "alerts": 0,
    }
