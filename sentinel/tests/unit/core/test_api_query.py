"""Tests de API de consulta (ST-M4-06, filtros + paginación)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from .conftest import sample_batch


def _seed(client: TestClient, auth: dict[str, str], n: int = 3) -> list[str]:
    r = client.post("/api/v1/ingest", json=sample_batch(n), headers=auth)
    assert r.status_code == 202
    page = client.get("/api/v1/assets").json()
    return [a["asset_id"] for a in page["items"]]


def test_assets_pagination_and_status_filter(client: TestClient, auth: dict[str, str]) -> None:
    _seed(client, auth, 3)
    page = client.get("/api/v1/assets", params={"limit": 2, "offset": 0}).json()
    assert page["total"] == 3 and len(page["items"]) == 2 and page["limit"] == 2
    page2 = client.get("/api/v1/assets", params={"limit": 2, "offset": 2}).json()
    assert len(page2["items"]) == 1
    assert client.get("/api/v1/assets", params={"status": "present"}).json()["total"] == 3
    assert client.get("/api/v1/assets", params={"status": "absent"}).json()["total"] == 0
    clamped = client.get("/api/v1/assets", params={"limit": 5000}).json()
    assert clamped["limit"] == 1000


def test_asset_detail_and_404(client: TestClient, auth: dict[str, str]) -> None:
    ids = _seed(client, auth, 1)
    r = client.get(f"/api/v1/assets/{ids[0]}")
    assert r.status_code == 200
    body = r.json()
    assert body["ips"] == ["10.0.0.1"]
    assert body["recent_observations"]
    assert client.get("/api/v1/assets/does-not-exist").status_code == 404
    assert client.get("/api/v1/assets/does-not-exist").json() == {"detail": "not found"}


def test_events_filters_and_pagination(client: TestClient, auth: dict[str, str]) -> None:
    ids = _seed(client, auth, 3)
    page = client.get("/api/v1/events", params={"severity": "info"}).json()
    assert page["total"] == 3
    page = client.get("/api/v1/events", params={"asset_id": ids[0], "limit": 10}).json()
    assert page["total"] == 1
    assert page["items"][0]["asset_id"] == ids[0]
    # from/to con alias
    now = datetime.now(UTC)
    full = client.get(
        "/api/v1/events",
        params={"from": "2000-01-01T00:00:00+00:00", "to": "2100-01-01T00:00:00+00:00"},
    ).json()
    assert full["total"] == 3
    future = client.get(
        "/api/v1/events", params={"from": now.replace(year=now.year + 1).isoformat()}
    ).json()
    assert future["total"] == 0
    assert client.get("/api/v1/events", params={"rule": "nope"}).json()["total"] == 0


def test_alerts_empty_page(client: TestClient) -> None:
    r = client.get("/api/v1/alerts")
    assert r.status_code == 200
    body = r.json()
    assert body == {"items": [], "total": 0, "limit": 100, "offset": 0}
