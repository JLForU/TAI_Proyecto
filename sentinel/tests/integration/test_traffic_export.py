"""ST-M3-03 (D-U5-04): ventana emitida por U5 ⇒ consultable en Core + idempotente.

``run_window`` completo (fuente → agregación → ``IngestClient``) contra la app
real de U2 montada en ``TestClient`` (puente ``MockTransport``, sin red —
MNT-02). Verifica BR-U5-23 (1 POST/ventana), BR-U5-27 (reenvío ⇒
``deduplicated``) y que la ventana queda persistida/consultable.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from sentinel.core.api.app import create_app
from sentinel.core.config import CoreSettings
from sentinel.traffic.client import IngestClient
from sentinel.traffic.config import TrafficSettings
from sentinel.traffic.source import FixtureSource
from sentinel.traffic.worker import run_window

TOKEN = "test-token"
NOW = datetime(2026, 11, 19, 12, 0, 2, tzinfo=UTC)
FIXTURES = Path(__file__).parent.parent / "unit" / "traffic" / "fixtures"


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


def _bridge(app_client: TestClient, responses: list[dict]) -> httpx.MockTransport:
    """Enruta el ``IngestClient`` hacia el ``TestClient`` de U2 (sin sockets)."""

    def handler(request: httpx.Request) -> httpx.Response:
        headers = {k: v for k, v in request.headers.items() if k != "host"}
        response = app_client.request(
            request.method,
            request.url.path,
            content=request.content,
            headers=headers,
        )
        body = response.json()
        responses.append(body)
        return httpx.Response(response.status_code, json=body)

    return httpx.MockTransport(handler)


def _run_window(app_client: TestClient, responses: list[dict]):
    client = IngestClient(
        base_url="http://sentinel-core:8080",
        token=TOKEN,
        transport=_bridge(app_client, responses),
    )
    settings = TrafficSettings(window_seconds=5, interface="eth0", sensor_id="sensor-0")
    source = FixtureSource(FIXTURES / "window_sample.json")
    return run_window(settings, source, client, FakeClock(NOW))


def test_traffic_window_queryable(tmp_path: Path) -> None:
    settings = CoreSettings(
        db_path=str(tmp_path / "traffic-export.db"),
        ingest_token=TOKEN,
        page_limit=100,
        missing_cycles=3,
    )
    responses: list[dict] = []
    with TestClient(create_app(settings, metrics_port=None), raise_server_exceptions=False) as app:
        result = _run_window(app, responses)
        assert result.status == "emitted"
        assert result.traffic >= 1
        assert result.arp >= 1
        assert len(responses) == 1  # BR-U5-23: 1 POST por ventana
        assert responses[0]["accepted"] == result.items

        # ventana consultable en la BD del Core (observaciones source=traffic)
        with app.app.state.db.read() as conn:
            rows = list(
                conn.execute(
                    "SELECT payload FROM observations WHERE source='traffic' ORDER BY observed_at"
                )
            )
            arp_rows = list(conn.execute("SELECT payload FROM observations WHERE source='arp'"))
        assert rows, "la ventana de tráfico debe quedar persistida"
        assert arp_rows, "los mensajes ARP de la ventana deben quedar persistidos"
        payloads = [json.loads(r["payload"]) for r in rows]
        # U2 serializa UTC con sufijo Z (la ventana emitida por U5 es 12:00:00)
        assert any(p["window_start"].startswith("2026-11-19T12:00:00") for p in payloads)
        assert all(p["sensor_id"] == "sensor-0" for p in payloads)


def test_window_resend_is_idempotent(tmp_path: Path) -> None:
    """ST-M3-03 AC2 / BR-U5-27: reenvío del mismo lote ⇒ deduplicated, sin filas nuevas."""
    settings = CoreSettings(
        db_path=str(tmp_path / "traffic-idem.db"),
        ingest_token=TOKEN,
        page_limit=100,
        missing_cycles=3,
    )
    responses: list[dict] = []
    with TestClient(create_app(settings, metrics_port=None), raise_server_exceptions=False) as app:
        first = _run_window(app, responses)
        assert first.status == "emitted"
        with app.app.state.db.read() as conn:
            before = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]

        # misma ventana, mismo contenido ⇒ misma identidad (dedup UUIDv5 de U2)
        second = _run_window(app, responses)
        assert second.status == "emitted"
        assert second.items == first.items
        assert responses[1]["accepted"] == 0
        assert responses[1]["deduplicated"] == first.items
        with app.app.state.db.read() as conn:
            after = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
        assert after == before  # sin filas nuevas
