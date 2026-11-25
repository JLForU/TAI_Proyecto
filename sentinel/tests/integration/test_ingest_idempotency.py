"""ST-M4-03: identidad estable + idempotencia (uuid_dedup)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from sentinel.core.api.app import create_app
from sentinel.core.config import CoreSettings

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _client(tmp_path):  # type: ignore[no-untyped-def]
    settings = CoreSettings(
        db_path=str(tmp_path / "idem.db"), ingest_token="t", page_limit=100, missing_cycles=3
    )
    return TestClient(create_app(settings, metrics_port=None), raise_server_exceptions=False)


def _batch(mac_case: str = "lower") -> dict:
    # timestamps fijos: el mismo hecho byte a byte en cada envío (idempotencia)
    now = datetime(2026, 11, 11, 10, 0, 0, tzinfo=UTC)
    mac = "aa:bb:cc:dd:ee:ff" if mac_case == "lower" else "AA:BB:CC:DD:EE:FF"
    return {
        "items": [
            {
                "source": "discovery",
                "observed_at": now.isoformat(),
                "ip": "10.0.0.1",
                "mac": mac,
                "hostname": "h1",
                "method": "arp",
            },
            {
                "source": "discovery",
                "observed_at": (now + timedelta(seconds=1)).isoformat(),
                "ip": "10.0.0.2",
                "mac": "aa:bb:cc:dd:ee:02",
                "hostname": "h2",
                "method": "arp",
            },
        ]
    }


def test_uuid_dedup_same_batch_twice(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with _client(tmp_path) as client:
        auth = {"Authorization": "Bearer t"}
        first = client.post("/api/v1/ingest", json=_batch(), headers=auth)
        second = client.post("/api/v1/ingest", json=_batch(), headers=auth)
        assert first.status_code == second.status_code == 202
        assert second.json()["accepted"] == 0
        assert second.json()["events_persisted"] == 0
        # el número de eventos persistidos no cambia en la segunda ingesta
        events_total = client.get("/api/v1/events").json()["total"]
        assert events_total == first.json()["events_persisted"]
        # formato distinto (MAC mayúsculas) ⇒ misma identidad
        third = client.post("/api/v1/ingest", json=_batch(mac_case="upper"), headers=auth)
        assert third.json()["accepted"] == 0
        assert third.json()["deduplicated"] == 2


def test_uuid_dedup_event_ids_are_valid_uuids(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with _client(tmp_path) as client:
        auth = {"Authorization": "Bearer t"}
        client.post("/api/v1/ingest", json=_batch(), headers=auth)
        items = client.get("/api/v1/events").json()["items"]
        assert items, "debe haber eventos persistidos"
        for item in items:
            assert UUID_RE.match(item["event_id"]), item["event_id"]


def _mixed_batch() -> dict:
    """Lote mixto U5: 1 traffic + 1 arp con identidad estable (D-U5-02/03)."""
    now = datetime(2026, 11, 19, 12, 0, 5, tzinfo=UTC)
    return {
        "items": [
            {
                "source": "traffic",
                "observed_at": now.isoformat(),
                "sensor_id": "sensor-0",
                "window_start": datetime(2026, 11, 19, 12, 0, 0, tzinfo=UTC).isoformat(),
                "window_end": now.isoformat(),
                "interface": "eth0",
                "protocol": "tcp",
                "packet_length_bytes": 600,
                "bytes_per_second": 120.0,
                "packets": 2,
                "flows": 1,
                "pairs": [{"src_ip": "10.0.0.1", "dst_ip": "10.0.1.1"}],
            },
            {
                "source": "arp",
                "observed_at": now.isoformat(),
                "sensor_id": "sensor-0",
                "interface": "eth0",
                "opcode": 1,
                "psrc": "10.0.0.1",
                "pdst": "10.0.1.1",
                "hwsrc": "aa:bb:cc:dd:ee:01",
                "hwdst": "ff:ff:ff:ff:ff:ff",
            },
        ]
    }


def test_mixed_traffic_arp_batch_idempotent(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """ST-M3-03 AC2: lote mixto reenviado ⇒ accepted=0, deduplicated=2."""
    with _client(tmp_path) as client:
        auth = {"Authorization": "Bearer t"}
        first = client.post("/api/v1/ingest", json=_mixed_batch(), headers=auth)
        assert first.status_code == 202
        assert first.json()["accepted"] == 2

        second = client.post("/api/v1/ingest", json=_mixed_batch(), headers=auth)
        assert second.status_code == 202
        assert second.json()["accepted"] == 0
        assert second.json()["deduplicated"] == 2

        # sin filas nuevas de traffic ni de arp
        with client.app.state.db.read() as conn:
            traffic_n = conn.execute(
                "SELECT COUNT(*) FROM observations WHERE source='traffic'"
            ).fetchone()[0]
            arp_n = conn.execute("SELECT COUNT(*) FROM observations WHERE source='arp'").fetchone()[
                0
            ]
        assert traffic_n == 1
        assert arp_n == 1
