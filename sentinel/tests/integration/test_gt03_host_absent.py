"""GT-03: host ausente ⇒ ``AssetMissing`` (ST-M2-04, BR-U4-15/24).

- ``test_completed_cycle_marks_host_absent``: fixture sin host B +
  ``reconcile=true`` tras el umbral (``missing_cycles=1``) ⇒ ``asset_missing``
  + estado ``absent``.
- ``test_partial_cycle_no_missing``: ciclo ``timeout`` ingiere parciales con
  ``reconcile=false`` ⇒ **jamás** incrementa ``miss_count`` (AC2).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient

from sentinel.core.api.app import create_app
from sentinel.core.config import CoreSettings
from sentinel.discovery.config import DiscoverySettings
from sentinel.discovery.runner import CycleRunnerImpl
from sentinel.discovery.scanner import FixtureScanner

from .test_gt02_new_host import _ARP_TABLE, ApiIngestClient

TOKEN = "test-token"
HOST_A = "192.168.1.10"
HOST_B = "192.168.1.11"

_XML_BOTH = """<?xml version="1.0"?>
<nmaprun>
  <host><status state="up"/>
    <address addr="192.168.1.10" addrtype="ipv4"/>
    <address addr="aa:bb:cc:dd:ee:0a" addrtype="mac"/>
    <ports><port protocol="tcp" portid="22"><state state="open"/>
      <service name="ssh"/></port></ports>
  </host>
  <host><status state="up"/>
    <address addr="192.168.1.11" addrtype="ipv4"/>
    <hostnames><hostname name="lab-host-11"/></hostnames>
    <ports><port protocol="tcp" portid="443"><state state="open"/>
      <service name="https"/></port></ports>
  </host>
</nmaprun>
"""

_XML_ONLY_A = """<?xml version="1.0"?>
<nmaprun>
  <host><status state="up"/>
    <address addr="192.168.1.10" addrtype="ipv4"/>
    <address addr="aa:bb:cc:dd:ee:0a" addrtype="mac"/>
    <ports><port protocol="tcp" portid="22"><state state="open"/>
      <service name="ssh"/></port></ports>
  </host>
</nmaprun>
"""


class _SlowArpScanner(FixtureScanner):
    """ARP que cruza el deadline (forzar ``timeout`` conservando parciales)."""

    def arp_neighbors(self) -> dict[str, str]:
        time.sleep(1.2)
        return super().arp_neighbors()


def _wait(client: TestClient, run_id: str) -> dict:  # type: ignore[no-untyped-def]
    for _ in range(400):
        body = client.get(f"/api/v1/discovery/{run_id}").json()
        if body["status"] in {"completed", "timeout", "failed"}:
            return body
        threading.Event().wait(0.05)
    raise AssertionError(f"run {run_id} never finished: {body}")


def _discover(client: TestClient, hosts: list[str], **body_extra) -> dict:  # type: ignore[no-untyped-def]
    r = client.post("/api/v1/discovery", json={"hosts": hosts, **body_extra})
    assert r.status_code == 202, r.text
    return _wait(client, r.json()["run_id"])


def _assets(client: TestClient) -> dict[str, dict]:  # type: ignore[no-untyped-def]
    items = client.get("/api/v1/assets").json()["items"]
    return {ip: a for a in items for ip in a["ips"]}


def _event_types(client: TestClient) -> list[str]:  # type: ignore[no-untyped-def]
    body = client.get("/api/v1/events?limit=500").json()
    return [e["type"] for e in body["items"]]


@contextmanager
def _gt_client(tmp_path, monkeypatch) -> Iterator[tuple[TestClient, CycleRunnerImpl]]:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("SENTINEL_DISCOVERY_HOSTS", f"{HOST_A},{HOST_B}")
    xml_both = tmp_path / "both.xml"
    xml_both.write_text(_XML_BOTH, encoding="utf-8")
    arp = tmp_path / "arp.txt"
    arp.write_text(_ARP_TABLE, encoding="utf-8")
    dsettings = DiscoverySettings(
        scope_mode="explicit_hosts",
        hosts=f"{HOST_A},{HOST_B}",
        ports="22,443",
        scanner="fixtures",
    )
    scanner = FixtureScanner(nmap_xml=Path(xml_both), arp_table=Path(arp))
    runner = CycleRunnerImpl(dsettings, scanner=scanner)
    settings = CoreSettings(
        db_path=str(tmp_path / "gt03.db"),
        ingest_token=TOKEN,
        page_limit=100,
        missing_cycles=1,  # N=1: un ciclo sin B ya lo marca absent
    )
    app = create_app(settings, runner=runner, metrics_port=None)
    client = TestClient(app, raise_server_exceptions=False)
    runner._client = ApiIngestClient(client, TOKEN)  # noqa: SLF001 - seam del test
    with client:
        yield client, runner


def _swap_scanner(runner: CycleRunnerImpl, tmp_path: Path, xml_text: str) -> None:  # type: ignore[no-untyped-def]
    xml = tmp_path / "swap.xml"
    xml.write_text(xml_text, encoding="utf-8")
    arp = tmp_path / "arp.txt"
    if not arp.exists():
        arp.write_text(_ARP_TABLE, encoding="utf-8")
    runner._scanner = FixtureScanner(  # noqa: SLF001 - seam del test
        nmap_xml=Path(xml), arp_table=Path(arp)
    )


def test_completed_cycle_marks_host_absent(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    with _gt_client(tmp_path, monkeypatch) as (client, runner):
        # --- ciclo 1: A y B presentes ---------------------------------------
        first = _discover(client, [HOST_A, HOST_B])
        assert first["status"] == "completed"
        assert first["hosts_seen"] == 2
        assets = _assets(client)
        assert set(assets) == {HOST_A, HOST_B}
        assert all(a["status"] == "present" for a in assets.values())
        assert "asset_missing" not in _event_types(client)

        # --- ciclo 2: fixture sin B ⇒ umbral 1 ⇒ absent ---------------------
        _swap_scanner(runner, tmp_path, _XML_ONLY_A)
        second = _discover(client, [HOST_A])
        assert second["status"] == "completed"
        assert second["hosts_seen"] == 1

        types = _event_types(client)
        assert types.count("asset_missing") == 1

        assets = _assets(client)
        assert assets[HOST_A]["status"] == "present"
        assert assets[HOST_B]["status"] == "absent"


def test_partial_cycle_no_missing(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """BR-U4-24 / ST-M2-04 AC2: parciales con ``reconcile=false`` ⇒ sin missing."""
    with _gt_client(tmp_path, monkeypatch) as (client, runner):
        first = _discover(client, [HOST_A, HOST_B])
        assert first["status"] == "completed"
        assert set(_assets(client)) == {HOST_A, HOST_B}

        # --- ciclo 2: deadline vencido ⇒ parciales reconcile=false -----------
        # tabla ARP solo con A ⇒ el parcial NO incluye a B (como en el
        # escenario real de "host retirado") y aun así jamás se marca missing.
        arp_a = tmp_path / "arp_a.txt"
        arp_a.write_text(
            f"{HOST_A} dev eth0 lladdr aa:bb:cc:dd:ee:0a REACHABLE\n", encoding="utf-8"
        )
        runner._scanner = _SlowArpScanner(  # noqa: SLF001 - seam del test
            nmap_xml=tmp_path / "both.xml", arp_table=arp_a
        )
        second = _discover(client, [HOST_A, HOST_B], timeout_seconds=1)
        assert second["status"] == "timeout"

        types = _event_types(client)
        assert "asset_missing" not in types  # jamás marca missing un parcial
        assets = _assets(client)
        assert set(assets) == {HOST_A, HOST_B}
        assert all(a["status"] == "present" for a in assets.values())
