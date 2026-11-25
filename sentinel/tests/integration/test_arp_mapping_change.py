"""BR-U5-20/21 (ST-M3-04/06): tracking IP↔MAC delegado en U2.

U5 solo exporta ``ArpObservation`` crudas; ``InventoryService`` de U2 detecta
el cambio de ``hwsrc`` ⇒ evento ``arp_mapping_changed`` (sin atribución de
ataque) y ``create_if_missing=False`` ⇒ un ARP con IP desconocida **no crea**
activo.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from sentinel.core.api.app import create_app
from sentinel.core.config import CoreSettings

TOKEN = "test-token"
NOW = datetime(2026, 11, 19, 12, 0, 0, tzinfo=UTC)


@contextmanager
def _client(tmp_path) -> Iterator[TestClient]:  # type: ignore[no-untyped-def]
    settings = CoreSettings(
        db_path=str(tmp_path / "arp-map.db"),
        ingest_token=TOKEN,
        page_limit=100,
        missing_cycles=3,
    )
    with TestClient(
        create_app(settings, metrics_port=None), raise_server_exceptions=False
    ) as client:
        yield client


def _auth() -> dict:
    return {"Authorization": f"Bearer {TOKEN}"}


def _discovery_item(mac: str) -> dict:
    return {
        "source": "discovery",
        "observed_at": NOW.isoformat(),
        "ip": "10.0.0.5",
        "mac": mac,
        "hostname": "lab-host-5",
        "method": "arp",
    }


def _arp_item(hwsrc: str, *, observed_at: datetime | None = None) -> dict:
    return {
        "source": "arp",
        "observed_at": (observed_at or NOW).isoformat(),
        "interface": "eth0",
        "opcode": 1,
        "psrc": "10.0.0.5",
        "pdst": "10.0.0.99",
        "hwsrc": hwsrc,
        "hwdst": "ff:ff:ff:ff:ff:ff",
    }


def _event_types(client: TestClient) -> list[str]:
    body = client.get("/api/v1/events?limit=500").json()
    return [e["type"] for e in body["items"]]


def test_event(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """2 ingests con MAC distinta ⇒ fila ``arp_mapping_changed`` en events."""
    with _client(tmp_path) as client:
        # el activo nace desde discovery con MAC A (frontera U2)
        first = client.post(
            "/api/v1/ingest",
            json={"items": [_discovery_item("aa:bb:cc:dd:ee:01")]},
            headers=_auth(),
        )
        assert first.status_code == 202

        # el sensor exporta ARP con MAC B para la misma IP
        second = client.post(
            "/api/v1/ingest",
            json={
                "items": [_arp_item("aa:bb:cc:dd:ee:02", observed_at=NOW + timedelta(seconds=5))]
            },
            headers=_auth(),
        )
        assert second.status_code == 202
        assert second.json()["accepted"] == 1

        types = _event_types(client)
        assert "arp_mapping_changed" in types

        events = client.get("/api/v1/events?limit=500").json()["items"]
        changed = next(e for e in events if e["type"] == "arp_mapping_changed")
        assert changed["asset_id"] is not None
        assert changed["details"]["ip"] == "10.0.0.5"
        assert changed["details"]["mac"] == "aa:bb:cc:dd:ee:02"
        # sin atribución de ataque en el contenido del evento (ST-M3-06)
        assert "spoof" not in str(changed["details"]).lower()


def test_no_asset_created(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """ARP con IP aún desconocida ⇒ no crea activo (create_if_missing=False)."""
    with _client(tmp_path) as client:
        response = client.post(
            "/api/v1/ingest",
            json={
                "items": [_arp_item("aa:bb:cc:dd:ee:77", observed_at=NOW + timedelta(seconds=9))]
            },
            headers=_auth(),
        )
        assert response.status_code == 202
        assert response.json()["accepted"] == 1

        assets = client.get("/api/v1/assets").json()
        assert assets["total"] == 0
        assert _event_types(client) == []  # sin activos ⇒ sin eventos de inventario
