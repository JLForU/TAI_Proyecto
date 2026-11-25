"""Runner bridge U2↔U4 (U4, FD §3.8, BR-U4-15/36): excepciones y seams."""

from __future__ import annotations

from pathlib import Path

import pytest

from sentinel.core.discovery.trigger import DiscoveryTimeoutError
from sentinel.discovery.client import IngestClient
from sentinel.discovery.config import DiscoverySettings
from sentinel.discovery.runner import CycleRunnerImpl
from sentinel.discovery.scanner import FixtureScanner, ScannerError
from sentinel.foundation.errors import ScopeError

FIXTURES = Path(__file__).parent / "fixtures"


class RecordingClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def post_ingest(self, items, *, reconcile: bool):  # type: ignore[no-untyped-def]
        self.calls.append({"n": len(items), "reconcile": reconcile})
        return {"accepted": len(items)}


def _settings() -> DiscoverySettings:
    return DiscoverySettings(hosts="192.168.1.10,192.168.1.11")


def _scanner() -> FixtureScanner:
    return FixtureScanner(
        nmap_xml=FIXTURES / "nmap_sample.xml", arp_table=FIXTURES / "arp_sample.txt"
    )


def test_run_returns_hosts_seen() -> None:
    client = RecordingClient()
    runner = CycleRunnerImpl(_settings(), scanner=_scanner(), client=client)  # type: ignore[arg-type]
    seen = runner.run(["192.168.1.10", "192.168.1.11"], 10)
    assert seen == 2
    assert client.calls[0]["reconcile"] is True


def test_run_timeout_ingests_partials_then_raises() -> None:
    """Parciales ingeridos con reconcile=false ANTES de DiscoveryTimeoutError."""

    class SlowArp(FixtureScanner):
        def arp_neighbors(self) -> dict[str, str]:
            import time

            time.sleep(1.2)
            return super().arp_neighbors()

    client = RecordingClient()
    runner = CycleRunnerImpl(_settings(), scanner=SlowArp(), client=client)  # type: ignore[arg-type]
    with pytest.raises(DiscoveryTimeoutError, match="timeout"):
        runner.run(["192.168.1.10"], 1)
    assert len(client.calls) == 1
    assert client.calls[0]["reconcile"] is False


def test_run_scope_error_propagates() -> None:
    client = RecordingClient()
    runner = CycleRunnerImpl(_settings(), scanner=_scanner(), client=client)  # type: ignore[arg-type]
    with pytest.raises(ScopeError, match="fuera de alcance"):
        runner.run(["10.9.9.9"], 5)
    assert client.calls == []


def test_run_scanner_error_propagates() -> None:
    class Broken(FixtureScanner):
        def nmap_scan(self, targets, ports, extra_args="", timeout=None):  # type: ignore[no-untyped-def]
            raise ScannerError("nmap down")

    client = RecordingClient()
    runner = CycleRunnerImpl(_settings(), scanner=Broken(), client=client)  # type: ignore[arg-type]
    with pytest.raises(ScannerError, match="nmap down"):
        runner.run(["192.168.1.10"], 5)
    assert client.calls == []


def test_run_once_uses_config_allowlist() -> None:
    client = RecordingClient()
    runner = CycleRunnerImpl(
        _settings(),
        scanner=_scanner(),
        client=client,
        timeout_seconds=10,  # type: ignore[arg-type]
    )
    assert runner.run_once() == 2
    assert runner.settings.hosts == "192.168.1.10,192.168.1.11"


def test_default_client_is_ingest_client() -> None:
    runner = CycleRunnerImpl(_settings(), scanner=_scanner())
    assert isinstance(runner._client, IngestClient)  # noqa: SLF001 - seam check
