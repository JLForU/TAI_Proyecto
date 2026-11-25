"""ST-M4-04 AC1: discovery y tráfico correlacionados por IP (discovery_and_traffic).

Ubicación: ``tests/unit/`` — la verificación del AC es
``pytest tests/unit/test_correlation.py -k discovery_and_traffic``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from sentinel.core.api.app import create_app
from sentinel.core.config import CoreSettings


def test_discovery_and_traffic(tmp_path) -> None:  # type: ignore[no-untyped-def]
    settings = CoreSettings(
        db_path=str(tmp_path / "corr.db"), ingest_token="t", page_limit=100, missing_cycles=3
    )
    now = datetime.now(UTC)
    app = create_app(settings, metrics_port=None)
    with TestClient(app, raise_server_exceptions=False) as client:
        auth = {"Authorization": "Bearer t"}
        # 1) descubrimiento crea el activo para 10.0.0.7
        r = client.post(
            "/api/v1/ingest",
            json={
                "items": [
                    {
                        "source": "discovery",
                        "observed_at": now.isoformat(),
                        "ip": "10.0.0.7",
                        "mac": "aa:bb:cc:dd:ee:07",
                        "hostname": "host7",
                        "method": "arp",
                    }
                ]
            },
            headers=auth,
        )
        assert r.status_code == 202

        # 2) observación de tráfico del mismo host (par src=10.0.0.7)
        r = client.post(
            "/api/v1/ingest",
            json={
                "items": [
                    {
                        "source": "traffic",
                        "observed_at": (now + timedelta(seconds=5)).isoformat(),
                        "window_start": now.isoformat(),
                        "window_end": (now + timedelta(seconds=5)).isoformat(),
                        "interface": "eth0",
                        "protocol": "tcp",
                        "packet_length_bytes": 128,
                        "bytes_per_second": 64.0,
                        "packets": 4,
                        "flows": 1,
                        "pairs": [{"src_ip": "10.0.0.7", "dst_ip": "10.0.0.9"}],
                    }
                ]
            },
            headers=auth,
        )
        assert r.status_code == 202
        assert r.json()["accepted"] == 1

        # 3) el detalle del activo muestra ambas fuentes correlacionadas
        asset = client.get("/api/v1/assets").json()["items"][0]
        detail = client.get(f"/api/v1/assets/{asset['asset_id']}").json()
        sources = {o["source"] for o in detail["recent_observations"]}
        assert sources == {"discovery", "traffic"}
        # ambas apuntan al mismo activo por IP
        traffic = next(o for o in detail["recent_observations"] if o["source"] == "traffic")
        assert traffic["payload"]["pairs"][0]["src_ip"] == "10.0.0.7"
        discovery = next(o for o in detail["recent_observations"] if o["source"] == "discovery")
        assert discovery["payload"]["ip"] == "10.0.0.7"
        # la IP sigue resolviendo al mismo asset_id
        assert detail["ips"] == ["10.0.0.7"]
