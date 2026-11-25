"""GT-02: primer ciclo de discovery ⇒ ``AssetFirstSeen`` + asset visible.

ST-M2-03 / BR-U4-27 (Q12=A): U4 no implementa inventario; el evento lo emite
``InventoryService`` de U2 ante el lote end-to-end
``POST /discovery → run_cycle → POST /ingest → assets/events``.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient

from sentinel.core.api.app import create_app
from sentinel.core.config import CoreSettings
from sentinel.discovery.config import DiscoverySettings
from sentinel.discovery.runner import CycleRunnerImpl
from sentinel.discovery.scanner import FixtureScanner
from sentinel.foundation.errors import IngestionError

TOKEN = "test-token"
HOSTS = ["192.168.1.10", "192.168.1.11", "192.168.1.12"]

_NMAP_XML = """<?xml version="1.0"?>
<nmaprun>
  <host><status state="up"/>
    <address addr="192.168.1.10" addrtype="ipv4"/>
    <address addr="aa:bb:cc:dd:ee:0a" addrtype="mac"/>
    <hostnames><hostname name="lab-host-10"/></hostnames>
    <ports>
      <port protocol="tcp" portid="22"><state state="open"/>
        <service name="ssh" version="OpenSSH 9.0"/></port>
    </ports>
  </host>
  <host><status state="up"/>
    <address addr="192.168.1.11" addrtype="ipv4"/>
    <hostnames><hostname name="lab-host-11"/></hostnames>
    <ports>
      <port protocol="tcp" portid="443"><state state="open"/>
        <service name="https"/></port>
    </ports>
  </host>
  <host><status state="up"/>
    <address addr="192.168.1.12" addrtype="ipv4"/>
    <hostnames><hostname name="lab-host-12"/></hostnames>
    <ports>
      <port protocol="tcp" portid="80"><state state="open"/>
        <service name="http"/></port>
    </ports>
  </host>
</nmaprun>
"""

_ARP_TABLE = """\
192.168.1.10 dev eth0 lladdr aa:bb:cc:dd:ee:0a REACHABLE
192.168.1.11 dev eth0 lladdr aa:bb:cc:dd:ee:0b REACHABLE
"""


class ApiIngestClient:
    """``IngestClient`` en proceso contra el ``TestClient`` (sin red, MNT-02)."""

    def __init__(self, client: TestClient, token: str) -> None:
        self._client = client
        self._token = token

    def post_ingest(self, items, *, reconcile: bool) -> dict:  # type: ignore[no-untyped-def]
        payload = {
            "items": [item.model_dump(mode="json") for item in items],
            "reconcile": reconcile,
        }
        r = self._client.post(
            "/api/v1/ingest",
            json=payload,
            headers={"Authorization": f"Bearer {self._token}"},
        )
        if r.status_code >= 400:
            raise IngestionError(f"ingest rejected: {r.status_code} {r.text[:200]}")
        return dict(r.json())

    def close(self) -> None:
        pass


def _wait(client: TestClient, run_id: str) -> dict:  # type: ignore[no-untyped-def]
    for _ in range(400):
        body = client.get(f"/api/v1/discovery/{run_id}").json()
        if body["status"] in {"completed", "timeout", "failed"}:
            return body
        threading.Event().wait(0.05)
    raise AssertionError(f"run {run_id} never finished: {body}")


def _discover(client: TestClient, hosts: list[str]) -> dict:  # type: ignore[no-untyped-def]
    r = client.post("/api/v1/discovery", json={"hosts": hosts})
    assert r.status_code == 202, r.text
    return _wait(client, r.json()["run_id"])


def _assets(client: TestClient) -> list[dict]:  # type: ignore[no-untyped-def]
    return list(client.get("/api/v1/assets").json()["items"])


def _event_types(client: TestClient) -> list[str]:  # type: ignore[no-untyped-def]
    body = client.get("/api/v1/events?limit=500").json()
    return [e["type"] for e in body["items"]]


@contextmanager
def _gt_client(tmp_path, monkeypatch) -> Iterator[tuple[TestClient, CycleRunnerImpl]]:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("SENTINEL_DISCOVERY_HOSTS", ",".join(HOSTS))
    xml = tmp_path / "nmap.xml"
    xml.write_text(_NMAP_XML, encoding="utf-8")
    arp = tmp_path / "arp.txt"
    arp.write_text(_ARP_TABLE, encoding="utf-8")
    dsettings = DiscoverySettings(
        scope_mode="explicit_hosts",
        hosts=",".join(HOSTS),
        ports="22,443,80",
        scanner="fixtures",
    )
    scanner = FixtureScanner(nmap_xml=Path(xml), arp_table=Path(arp))
    runner = CycleRunnerImpl(dsettings, scanner=scanner)
    settings = CoreSettings(
        db_path=str(tmp_path / "gt02.db"),
        ingest_token=TOKEN,
        page_limit=100,
        missing_cycles=1,
    )
    app = create_app(settings, runner=runner, metrics_port=None)
    client = TestClient(app, raise_server_exceptions=False)
    runner._client = ApiIngestClient(client, TOKEN)  # noqa: SLF001 - seam del test
    with client:
        yield client, runner


def test_gt02_new_host_asset_first_seen(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    with _gt_client(tmp_path, monkeypatch) as (client, _runner):
        # --- ciclo 1: hosts A y B ya se ven por primera vez -----------------
        first = _discover(client, ["192.168.1.10", "192.168.1.11"])
        assert first["status"] == "completed"
        assert first["hosts_seen"] == 2

        assets = _assets(client)
        assert assets and {ip for a in assets for ip in a["ips"]} == {
            "192.168.1.10",
            "192.168.1.11",
        }
        assert all(a["status"] == "present" for a in assets)
        assert all(a["first_seen"] for a in assets)

        types = _event_types(client)
        assert types.count("asset_first_seen") == 2

        # --- ciclo 2: host nuevo C ⇒ AssetFirstSeen de C --------------------
        second = _discover(client, HOSTS)
        assert second["status"] == "completed"
        assert second["hosts_seen"] == 3

        assets = _assets(client)
        by_ip = {ip: a for a in assets for ip in a["ips"]}
        assert set(by_ip) == set(HOSTS)
        new = by_ip["192.168.1.12"]
        assert new["status"] == "present"
        assert new["hostname"] == "lab-host-12"

        types = _event_types(client)
        assert types.count("asset_first_seen") == 3  # C acaba de aparecer
