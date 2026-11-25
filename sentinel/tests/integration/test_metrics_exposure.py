"""ST-M6-04 / BR-U7-11/12: contadores post-commit visibles en ``/metrics``.

``TestClient`` + BD temporal + puerto efímero: un lote de tráfico/ARP aceptado
incrementa los contadores una sola vez; un reenvío deduplicado no los duplica.
Los gauges de SQLite (activos/cambios) y la última ventana de tráfico se leen
al scrape.
"""

from __future__ import annotations

import urllib.request
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from sentinel.core.api.app import create_app
from sentinel.core.config import CoreSettings
from sentinel.foundation.metrics_contract import METRIC_FAMILIES

TOKEN = "t"


def _traffic(bps: float, at: datetime, *, flows: int = 7) -> dict:
    return {
        "source": "traffic",
        "observed_at": at.isoformat(),
        "sensor_id": "sensor-0",
        "window_start": (at - timedelta(seconds=10)).isoformat(),
        "window_end": at.isoformat(),
        "interface": "eth0",
        "protocol": "tcp",
        "packet_length_bytes": 1024,
        "bytes_per_second": bps,
        "packets": 10,
        "flows": flows,
    }


def _arp(at: datetime) -> dict:
    return {
        "source": "arp",
        "observed_at": at.isoformat(),
        "sensor_id": "sensor-0",
        "interface": "eth0",
        "opcode": 1,
        "psrc": "10.0.0.1",
        "pdst": "10.0.0.2",
        "hwsrc": "aa:bb:cc:dd:ee:ff",
        "hwdst": "00:00:00:00:00:00",
    }


def _discovery(at: datetime) -> dict:
    return {
        "source": "discovery",
        "observed_at": at.isoformat(),
        "sensor_id": "sensor-0",
        "ip": "10.0.0.10",
        "mac": "aa:bb:cc:dd:ee:ff",
        "hostname": "host10",
        "method": "arp",
    }


def _scrape(port: int) -> str:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=5) as resp:
        assert resp.status == 200
        return resp.read().decode()


def _post(client: TestClient, item: dict) -> dict:
    resp = client.post(
        "/api/v1/ingest", json={"items": [item]}, headers={"Authorization": f"Bearer {TOKEN}"}
    )
    assert resp.status_code == 202, resp.text
    return resp.json()


def test_accepted_observations_reach_metrics_once(tmp_path) -> None:  # type: ignore[no-untyped-def]
    settings = CoreSettings(
        db_path=str(tmp_path / "metrics-e2e.db"),
        ingest_token=TOKEN,
        page_limit=100,
        missing_cycles=3,
    )
    app = create_app(settings, metrics_port=0)
    now = datetime.now(UTC).replace(microsecond=0)
    traffic = _traffic(2048.0, now)
    with TestClient(app, raise_server_exceptions=False) as client:
        port = app.state.metrics_server.port
        assert _post(client, _discovery(now))["accepted"] == 1
        assert _post(client, traffic)["accepted"] == 1
        assert _post(client, _arp(now))["accepted"] == 1

        text = _scrape(port)
        assert 'sentinel_flows_total{component="traffic"} 7' in text
        assert 'sentinel_arp_messages_total{component="traffic"} 1' in text
        assert 'sentinel_assets_total{component="core"} 1' in text
        assert 'sentinel_asset_changes_total{component="core"} 1' in text
        assert 'sentinel_bytes_per_second{interface="eth0",protocol="tcp"} 2048' in text
        families = {line.split()[2] for line in text.splitlines() if line.startswith("# TYPE ")}
        assert families == set(METRIC_FAMILIES)

        # Reenvío idéntico ⇒ deduplicado, los contadores no se duplican.
        assert _post(client, traffic)["accepted"] == 0
        text2 = _scrape(port)
        assert 'sentinel_flows_total{component="traffic"} 7' in text2
