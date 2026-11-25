"""Fixtures de GUI: app real + ``httpx.MockTransport`` para el loopback (P7).

El ``create_app`` recibe ``http_client`` (inyección Q6=NFR=A): las vistas
llaman a la API U2 por un transporte simulado; la app real (routers,
handlers, templates) queda en el medio.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from sentinel.core.api.app import create_app
from sentinel.core.config import CoreSettings

TOKEN = "test-token"

Handler = Callable[[httpx.Request], httpx.Response]


def ok(payload: Any, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload)


def page(items: list[Any], *, total: int | None = None, limit: int = 100, offset: int = 0) -> dict:
    return {
        "items": items,
        "total": len(items) if total is None else total,
        "limit": limit,
        "offset": offset,
    }


def asset_summary(
    asset_id: str = "a-1",
    *,
    hostname: str | None = "host1",
    status: str = "present",
    ip: str = "10.0.0.1",
    mac: str | None = "aa:bb:cc:dd:ee:ff",
) -> dict:
    return {
        "asset_id": asset_id,
        "mac": mac,
        "ips": [ip],
        "hostname": hostname,
        "status": status,
        "first_seen": "2026-01-01T00:00:00+00:00",
        "last_seen": "2026-01-02T00:00:00+00:00",
    }


def asset_detail(summary: dict | None = None, **overrides: Any) -> dict:
    base = dict(asset_summary() if summary is None else summary)
    detail = {
        **base,
        "os_name": "Linux",
        "os_provenance": "observed",
        "recent_observations": [],
        "recent_events": [],
    }
    detail.update(overrides)
    return detail


def observation(
    *,
    source: str = "discovery",
    kind: str = "arp",
    observed_at: str = "2026-01-01T00:00:00+00:00",
    payload: dict | None = None,
) -> dict:
    return {
        "dedup_key": f"{source}:{observed_at}",
        "source": source,
        "kind": kind,
        "sensor_id": None,
        "observed_at": observed_at,
        "payload": payload if payload is not None else {},
    }


def event(
    event_id: str = "e-1",
    *,
    type_: str = "port_service_changed",
    asset_id: str | None = "a-1",
    severity: str = "info",
    occurred_at: str = "2026-01-01T10:00:00+00:00",
    details: dict | None = None,
) -> dict:
    return {
        "event_id": event_id,
        "type": type_,
        "asset_id": asset_id,
        "severity": severity,
        "rule": None,
        "occurred_at": occurred_at,
        "details": details or {},
    }


def alert(
    alert_id: str = "al-1",
    *,
    state: str = "firing",
    fired_at: str = "2026-01-01T09:00:00+00:00",
    resolved_at: str | None = None,
    asset_id: str | None = "a-1",
) -> dict:
    return {
        "alert_id": alert_id,
        "condition_id": "c-1",
        "rule": "port_open",
        "metric_key": "port/22",
        "asset_id": asset_id,
        "state": state,
        "measured_value": 1.0,
        "threshold": 0.5,
        "fired_at": fired_at,
        "resolved_at": resolved_at,
    }


def health(
    *,
    status: str = "up",
    heartbeats: dict[str, str] | None = None,
    counts: dict[str, int] | None = None,
) -> dict:
    return {
        "status": status,
        "uptime_seconds": 12.5,
        "db_connected": True,
        "last_ingest_at": "2026-01-02T00:00:00+00:00",
        "sensor_heartbeats": heartbeats or {},
        "counts": counts if counts is not None else {"assets": 1, "events": 2, "alerts": 1},
        "last_discovery_run": None,
    }


@pytest.fixture()
def make_gui(tmp_path: Path) -> Iterator[Any]:
    """Crea ``TestClient`` con el loopback MockTransport ``handler``."""
    clients: list[TestClient] = []

    def _make(handler: Handler) -> TestClient:
        settings = CoreSettings(
            db_path=str(tmp_path / "gui.db"),
            ingest_token=TOKEN,
            page_limit=100,
            missing_cycles=3,
        )
        http_client = httpx.Client(transport=httpx.MockTransport(handler))
        app = create_app(settings, metrics_port=None, http_client=http_client)
        tc = TestClient(app, raise_server_exceptions=False)
        tc.__enter__()
        clients.append(tc)
        return tc

    yield _make

    for tc in clients:
        tc.__exit__(None, None, None)
