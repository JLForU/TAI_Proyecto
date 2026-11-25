"""Integración GUI ↔ Core real (AVAIL-02, ST-M10-01/02/06).

La app es una sola: el loopback del GUI se resuelve con un transporte
httpx que reenvía las llamadas al mismo ``TestClient`` (API U2 real con
SQLite temporal). No hay mock de respuestas: se siembra vía ``/ingest``.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from sentinel.core.api.app import create_app
from sentinel.core.config import CoreSettings

TOKEN = "test-token"


class LoopbackTransport(httpx.BaseTransport):
    """Reenvía cada request httpx al ``TestClient`` (API real, mismo proceso)."""

    def __init__(self, tc: TestClient) -> None:
        self._tc = tc

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        headers = {
            k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")
        }
        resp = self._tc.request(
            request.method,
            request.url.path,
            params=request.url.params,
            content=request.content,
            headers=headers,
        )
        return httpx.Response(
            resp.status_code,
            headers=resp.headers,
            content=resp.content,
            request=request,
        )


def _seed_batch(n: int = 2) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "items": [
            {
                "source": "discovery",
                "observed_at": now.isoformat(),
                "ip": f"192.168.1.{i}",
                "mac": f"aa:bb:cc:dd:ee:0{i}",
                "hostname": f"host{i}",
                "method": "arp",
            }
            for i in range(1, n + 1)
        ]
    }


@pytest.fixture()
def gui_app(tmp_path) -> Iterator[tuple[TestClient, TestClient]]:  # type: ignore[no-untyped-def]
    settings = CoreSettings(
        db_path=str(tmp_path / "integration.db"),
        ingest_token=TOKEN,
        page_limit=100,
        missing_cycles=3,
    )
    app = create_app(settings, metrics_port=None)
    with TestClient(app, raise_server_exceptions=False) as tc:
        # Loopback del GUI → misma app (API U2 real) vía transporte a TestClient.
        app.state.gui_config = (
            "http://127.0.0.1:8080",
            httpx.Client(transport=LoopbackTransport(tc)),
        )
        yield tc, tc


def test_inventory_detail_and_report_end_to_end(gui_app: Any) -> None:
    tc, _ = gui_app
    auth = {"Authorization": f"Bearer {TOKEN}"}
    r = tc.post("/api/v1/ingest", json=_seed_batch(2), headers=auth)
    assert r.status_code == 202

    # ST-M10-01: inventario con datos reales
    page = tc.get("/ui/assets")
    assert page.status_code == 200
    assert "host1" in page.text and "host2" in page.text

    # ST-M10-02: detalle real con observaciones
    asset_id = tc.get("/api/v1/assets").json()["items"][0]["asset_id"]
    detail = tc.get(f"/ui/assets/{asset_id}")
    assert detail.status_code == 200
    assert "Observaciones" in detail.text
    assert "discovery" in detail.text

    # ST-M10-06: reporte real (5 secciones + attachment + determinismo)
    params = {"from": "2000-01-01", "to": "2100-01-01", "format": "md"}
    tc.app.state.report_clock = lambda: datetime(2026, 1, 2, tzinfo=UTC)
    tc.app.state.report_service = None
    rep1 = tc.get("/ui/report", params=params)
    assert rep1.status_code == 200
    assert "attachment" in rep1.headers["content-disposition"]
    heads = [ln for ln in rep1.text.splitlines() if ln.startswith("## ")]
    assert len(heads) == 5
    tc.app.state.report_service = None
    rep2 = tc.get("/api/v1/report", params=params)
    assert rep2.status_code == 200
    assert rep1.content == rep2.content


def test_asset_404_from_real_api_renders_gui_page(gui_app: Any) -> None:
    tc, _ = gui_app
    r = tc.get("/ui/assets/does-not-exist")
    assert r.status_code == 404
    assert "No encontrado" in r.text


def test_health_view_real_counts(gui_app: Any) -> None:
    tc, _ = gui_app
    auth = {"Authorization": f"Bearer {TOKEN}"}
    tc.post("/api/v1/ingest", json=_seed_batch(3), headers=auth)
    r = tc.get("/ui/health")
    assert r.status_code == 200
    assert "3" in r.text  # conteo real de activos


def test_gui_serves_shell_when_api_down_avail02(tmp_path: Any) -> None:
    """AVAIL-02: API caída ⇒ vistas con 502, shell (discovery) sigue 200."""

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    settings = CoreSettings(
        db_path=str(tmp_path / "down.db"), ingest_token=TOKEN, page_limit=100, missing_cycles=3
    )
    app = create_app(
        settings,
        metrics_port=None,
        http_client=httpx.Client(transport=httpx.MockTransport(down)),
    )
    with TestClient(app, raise_server_exceptions=False) as tc:
        assert tc.get("/ui/discovery").status_code == 200
        r = tc.get("/ui/assets")
        assert r.status_code == 502
        assert "Core API no disponible" in r.text
        assert "Traceback" not in r.text
