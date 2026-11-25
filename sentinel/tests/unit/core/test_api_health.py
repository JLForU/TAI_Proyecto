"""Tests de API de salud (ST-M4-08, Q11)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import sample_batch


def test_health_up(client: TestClient, auth: dict[str, str]) -> None:
    client.post("/api/v1/ingest", json=sample_batch(1), headers=auth)
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "up"
    assert body["db_connected"] is True
    assert body["counts"] == {"assets": 1, "events": 1, "alerts": 0}
    assert body["last_ingest_at"] is not None
    assert "sensor-0" in body["sensor_heartbeats"]
    assert body["uptime_seconds"] >= 0


def test_health_no_auth_needed(client: TestClient) -> None:
    assert client.get("/api/v1/health").status_code == 200
