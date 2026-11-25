"""Worker del ciclo (U4, BR-U4-13..17/23/25/33): fases, fusión, reconcile."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from sentinel.discovery.client import to_observations
from sentinel.discovery.config import DiscoverySettings
from sentinel.discovery.domain import HostFinding, merge_findings, resolve_targets
from sentinel.discovery.scanner import FixtureScanner, ScannerError
from sentinel.discovery.worker import run_cycle
from sentinel.foundation.errors import ScopeError
from sentinel.foundation.models import PortInfo

FIXTURES = Path(__file__).parent / "fixtures"


class RecordingClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def post_ingest(self, items, *, reconcile: bool):  # type: ignore[no-untyped-def]
        self.calls.append({"items": items, "reconcile": reconcile})
        return {"accepted": len(items)}


def _settings(**overrides) -> DiscoverySettings:
    base = {"hosts": "192.168.1.10,192.168.1.11"}
    base.update(overrides)
    return DiscoverySettings(**base)  # type: ignore[arg-type]


def _fixture_scanner() -> FixtureScanner:
    return FixtureScanner(
        nmap_xml=FIXTURES / "nmap_sample.xml", arp_table=FIXTURES / "arp_sample.txt"
    )


def test_merge_observation() -> None:
    port_tcp = PortInfo(port=22, state="open", confidence="probable")
    port_nmap = PortInfo(
        port=22, state="open", service="ssh", version="9.0", confidence="confirmed"
    )
    merged = merge_findings(
        [
            HostFinding(ip="10.0.0.1", mac="aa:bb:cc:dd:ee:01", method="arp"),
            HostFinding(ip="10.0.0.1", method="icmp"),
            HostFinding(ip="10.0.0.1", ports=[port_tcp], method="tcp"),
            HostFinding(ip="10.0.0.1", ports=[port_nmap], hostname="h1", method="nmap"),
            HostFinding(ip="10.0.0.2", method="icmp"),
        ]
    )
    assert [f.ip for f in merged] == ["10.0.0.1", "10.0.0.2"]
    first = merged[0]
    assert first.method == "nmap"
    assert first.mac == "aa:bb:cc:dd:ee:01"
    assert first.hostname == "h1"
    assert len(first.ports) == 1
    assert first.ports[0].service == "ssh"
    assert merged[1].method == "icmp"


def test_hosts_seen() -> None:
    client = RecordingClient()
    result = run_cycle(_settings(), _fixture_scanner(), client, 10)
    assert result.status == "completed"
    assert result.hosts_seen == 2
    assert result.hosts_targeted == 2
    assert len(result.findings) == 2


def test_hosts_seen_zero_when_no_findings() -> None:
    class EmptyScanner:
        def arp_neighbors(self) -> dict[str, str]:
            return {}

        def ping(self, host: str) -> bool:
            return False

        def tcp_open(self, host: str, port: int) -> bool:
            return False

        def nmap_scan(self, targets, ports, extra_args="", timeout=None):  # type: ignore[no-untyped-def]
            return []

    client = RecordingClient()
    result = run_cycle(_settings(), EmptyScanner(), client, 5)
    assert result.status == "completed"
    assert result.hosts_seen == 0
    assert len(client.calls) == 1
    assert client.calls[0]["reconcile"] is True


def test_reconcile_flag_completed() -> None:
    client = RecordingClient()
    run_cycle(_settings(), _fixture_scanner(), client, 10)
    assert client.calls[0]["reconcile"] is True


def test_timeout_partial() -> None:
    """Deadline excedido ⇒ parciales ingeridos con reconcile=false (BR-U4-15)."""

    class SlowArpScanner(FixtureScanner):
        def arp_neighbors(self) -> dict[str, str]:
            time.sleep(1.2)
            return super().arp_neighbors()

    client = RecordingClient()
    result = run_cycle(_settings(), SlowArpScanner(), client, 1)
    assert result.status == "timeout"
    assert result.partial is True
    assert result.error == "timeout"
    assert len(client.calls) == 1
    assert client.calls[0]["reconcile"] is False


def test_deadline_between_phases() -> None:
    """Fase que cruza el deadline corta el ciclo sin iniciar la siguiente."""

    class SlowArpThenTrack(FixtureScanner):
        def __init__(self) -> None:
            super().__init__()
            self.icmp_called = False
            self.nmap_called = False

        def arp_neighbors(self) -> dict[str, str]:
            time.sleep(1.2)
            return {}

        def ping(self, host: str) -> bool:
            self.icmp_called = True
            return False

        def nmap_scan(self, targets, ports, extra_args="", timeout=None):  # type: ignore[no-untyped-def]
            self.nmap_called = True
            return []

    scanner = SlowArpThenTrack()
    client = RecordingClient()
    result = run_cycle(_settings(), scanner, client, 1)
    assert result.status == "timeout"
    assert scanner.icmp_called is False
    assert scanner.nmap_called is False


def test_sensor_id_default() -> None:
    client = RecordingClient()
    run_cycle(_settings(), _fixture_scanner(), client, 10)
    items = client.calls[0]["items"]
    assert items
    assert all(item.sensor_id == "sensor-0" for item in items)


def test_no_os_detection() -> None:
    client = RecordingClient()
    run_cycle(_settings(), _fixture_scanner(), client, 10)
    for item in client.calls[0]["items"]:
        assert item.os_name is None
        assert item.os_provenance == "unknown"
        assert item.source == "discovery"


def test_scope_violation_before_probes() -> None:
    client = RecordingClient()
    with pytest.raises(ScopeError, match="fuera de alcance"):
        run_cycle(_settings(), _fixture_scanner(), client, 10, hosts=["10.9.9.9"])
    assert client.calls == []


def test_scope_violation_logs_event(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    with caplog.at_level(logging.WARNING), pytest.raises(ScopeError):
        run_cycle(_settings(), _fixture_scanner(), RecordingClient(), 10, hosts=["8.8.8.8"])
    assert any(record.event == "scope_violation" for record in caplog.records)


def test_standalone_failure_log() -> None:
    """Fallo de escáner ⇒ excepción propagada y SIN lote (BR-U4-25/30)."""

    class BrokenScanner(FixtureScanner):
        def nmap_scan(self, targets, ports, extra_args="", timeout=None):  # type: ignore[no-untyped-def]
            raise ScannerError("nmap exploded")

    client = RecordingClient()
    with pytest.raises(ScannerError, match="nmap exploded"):
        run_cycle(_settings(), BrokenScanner(), client, 10)
    assert client.calls == []


def test_single_post_per_cycle() -> None:
    client = RecordingClient()
    run_cycle(_settings(), _fixture_scanner(), client, 10)
    assert len(client.calls) == 1


def test_cap_targets() -> None:
    hosts = [f"10.0.{i // 256}.{i % 256}" for i in range(1500)]  # > 1000 únicos
    resolved = resolve_targets(hosts, mode="explicit_hosts")
    assert len(resolved) == 1000


def test_resolve_targets_cidr_expansion() -> None:
    resolved = resolve_targets((), mode="cidr", cidrs=("192.168.1.0/30",))
    assert resolved == ["192.168.1.1", "192.168.1.2"]


def test_to_observations_boundary() -> None:
    findings = [
        HostFinding(
            ip="10.0.0.1",
            mac="aa:bb:cc:dd:ee:01",
            method="arp",
            ports=[PortInfo(port=22, state="open", confidence="probable")],
        )
    ]
    observed = datetime(2026, 11, 16, 12, 0, 0, tzinfo=UTC)
    items = to_observations(findings, observed)
    assert len(items) == 1
    item = items[0]
    assert str(item.ip) == "10.0.0.1"
    assert item.method == "arp"
    assert item.observed_at == observed
    dumped = item.model_dump(mode="json")
    assert dumped["source"] == "discovery"
    assert dumped["sensor_id"] == "sensor-0"
