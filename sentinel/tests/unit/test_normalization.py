"""ST-M4-04 AC2: MAC en formato canónico único (mac_canonical).

Ubicación: ``tests/unit/`` — la verificación del AC es
``pytest tests/unit/test_normalization.py -k mac_canonical``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from sentinel.core.api.app import create_app
from sentinel.core.config import CoreSettings

VARIANTS = [
    "AA:BB:CC:DD:EE:FF",
    "aa:bb:cc:dd:ee:ff",
    "Aa:Bb:Cc:Dd:Ee:Ff",
]


def test_mac_canonical(tmp_path) -> None:  # type: ignore[no-untyped-def]
    settings = CoreSettings(
        db_path=str(tmp_path / "mac.db"), ingest_token="t", page_limit=100, missing_cycles=3
    )
    now = datetime.now(UTC).isoformat()
    app = create_app(settings, metrics_port=None)
    with TestClient(app, raise_server_exceptions=False) as client:
        auth = {"Authorization": "Bearer t"}
        for i, mac in enumerate(VARIANTS):
            r = client.post(
                "/api/v1/ingest",
                json={
                    "items": [
                        {
                            "source": "discovery",
                            "observed_at": now,
                            "ip": f"10.0.1.{i}",
                            "mac": mac,
                            "hostname": f"h{i}",
                            "method": "arp",
                        }
                    ]
                },
                headers=auth,
            )
            assert r.status_code == 202

        assets = client.get("/api/v1/assets").json()["items"]
        assert len(assets) == 3
        for asset in assets:
            assert asset["mac"] is not None
            assert asset["mac"] == asset["mac"].lower()
            assert asset["mac"] == "aa:bb:cc:dd:ee:ff"

        # el payload de la observación también guarda la MAC canónica
        detail = client.get(f"/api/v1/assets/{assets[0]['asset_id']}").json()
        for obs in detail["recent_observations"]:
            assert obs["payload"]["mac"] == "aa:bb:cc:dd:ee:ff"
