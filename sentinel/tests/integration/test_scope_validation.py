"""Integración de scope U4 (SEC-01, BR-U4-06..09, ST-M1-02).

- API pre-run: con config de scope en el proceso ⇒ **400** ``scope_violation``
  **antes de crear el run** (BR-U4-08); sin env ⇒ sin validación (D-U4-04,
  compatibilidad U2).
- Worker: fuera de alcance ⇒ ``ScopeError`` antes de cualquier paquete
  (BR-U4-07, log ``scope_violation`` + run ``failed`` in-process).
- Modos ``explicit_hosts``/``cidr`` (BR-U4-06) y allowlist de puertos
  (BR-U4-09): solo ``scope.ports`` recibe probes.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from sentinel.core.api.app import create_app
from sentinel.core.config import CoreSettings
from sentinel.discovery.config import DiscoverySettings
from sentinel.discovery.runner import CycleRunnerImpl
from sentinel.discovery.scanner import FixtureScanner
from sentinel.discovery.worker import run_cycle
from sentinel.foundation.errors import ScopeError

TOKEN = "test-token"


class OkRunner:
    def run(self, hosts: list[str], timeout_seconds: int) -> int:
        return len(hosts)


class RecordingIngest:
    """Fake ``IngestClient``: registra cada ``post_ingest`` sin red."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def post_ingest(self, items, *, reconcile: bool):  # type: ignore[no-untyped-def]
        self.calls.append({"items": list(items), "reconcile": reconcile})
        return {"accepted": len(items)}

    def close(self) -> None:
        pass


class RecordingScanner(FixtureScanner):
    """FixtureScanner que registra cada probe (allowlist de puertos)."""

    def __init__(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(**kwargs)
        self.ping_calls: list[str] = []
        self.tcp_calls: list[tuple[str, int]] = []
        self.nmap_calls: list[tuple[tuple[str, ...], tuple[int, ...]]] = []

    def ping(self, host: str) -> bool:
        self.ping_calls.append(host)
        return super().ping(host)

    def tcp_open(self, host: str, port: int) -> bool:
        self.tcp_calls.append((host, port))
        return super().tcp_open(host, port)

    def nmap_scan(self, targets, ports, extra_args="", timeout=None):  # type: ignore[no-untyped-def]
        self.nmap_calls.append((tuple(targets), tuple(ports)))
        return super().nmap_scan(targets, ports, extra_args, timeout)


@contextmanager
def _client(tmp_path, runner=None) -> Iterator[TestClient]:  # type: ignore[no-untyped-def]
    settings = CoreSettings(
        db_path=str(tmp_path / "scope.db"),
        ingest_token=TOKEN,
        page_limit=100,
        missing_cycles=3,
    )
    with TestClient(
        create_app(settings, runner=runner, metrics_port=None), raise_server_exceptions=False
    ) as client:
        yield client


def _wait(client: TestClient, run_id: str) -> dict:  # type: ignore[no-untyped-def]
    for _ in range(200):
        body = client.get(f"/api/v1/discovery/{run_id}").json()
        if body["status"] in {"completed", "timeout", "failed"}:
            return body
        threading.Event().wait(0.05)
    raise AssertionError(f"run {run_id} never finished: {body}")


def _runs_count(client: TestClient) -> int:  # type: ignore[no-untyped-def]
    with client.app.state.db.read() as conn:  # type: ignore[attr-defined]
        row = conn.execute("SELECT COUNT(*) FROM discovery_runs").fetchone()
    return int(row[0])


# --- BR-U4-08: 400 pre-run sin crear run ------------------------------------


def test_api_pre_run_400_scope_violation(
    tmp_path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("SENTINEL_DISCOVERY_HOSTS", "10.0.0.1")
    with _client(tmp_path, runner=OkRunner()) as client:
        with caplog.at_level(logging.WARNING):
            r = client.post("/api/v1/discovery", json={"hosts": ["10.9.9.9"]})
        assert r.status_code == 400
        body = r.json()
        assert body["code"] == "scope_violation"
        assert "run_id" not in body
        assert any(getattr(rec, "event", None) == "scope_violation" for rec in caplog.records)
        # BR-U4-08: el run jamás se crea
        assert _runs_count(client) == 0
        # y el endpoint sigue sano para hosts en alcance
        ok = client.post("/api/v1/discovery", json={"hosts": ["10.0.0.1"]})
        assert ok.status_code == 202
        assert _wait(client, ok.json()["run_id"])["status"] == "completed"


def test_api_pre_run_allowlisted_creates_run(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("SENTINEL_DISCOVERY_HOSTS", "10.0.0.1,10.0.0.2")
    with _client(tmp_path, runner=OkRunner()) as client:
        r = client.post("/api/v1/discovery", json={"hosts": ["10.0.0.2"]})
        assert r.status_code == 202
        assert _wait(client, r.json()["run_id"])["status"] == "completed"
        assert _runs_count(client) == 1


def test_no_env_skips_api_validation(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """D-U4-04: sin ``SENTINEL_DISCOVERY_*`` la API no valida (worker garantiza)."""
    with _client(tmp_path, runner=OkRunner()) as client:
        r = client.post("/api/v1/discovery", json={"hosts": ["10.9.9.9", "8.8.8.8"]})
        assert r.status_code == 202
        assert _wait(client, r.json()["run_id"])["status"] == "completed"


# --- BR-U4-06: modos de alcance ---------------------------------------------


def test_mode_explicit(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("SENTINEL_DISCOVERY_SCOPE_MODE", "explicit_hosts")
    monkeypatch.setenv("SENTINEL_DISCOVERY_HOSTS", "10.0.0.1,10.0.0.2")
    with _client(tmp_path, runner=OkRunner()) as client:
        ok = client.post("/api/v1/discovery", json={"hosts": ["10.0.0.2"]})
        assert ok.status_code == 202
        _wait(client, ok.json()["run_id"])
        bad = client.post("/api/v1/discovery", json={"hosts": ["10.0.0.3"]})
        assert bad.status_code == 400
        assert bad.json()["code"] == "scope_violation"


def test_mode_cidr(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("SENTINEL_DISCOVERY_SCOPE_MODE", "cidr")
    monkeypatch.setenv("SENTINEL_DISCOVERY_CIDRS", "10.0.0.0/24")
    with _client(tmp_path, runner=OkRunner()) as client:
        ok = client.post("/api/v1/discovery", json={"hosts": ["10.0.0.55"]})
        assert ok.status_code == 202
        _wait(client, ok.json()["run_id"])
        bad = client.post("/api/v1/discovery", json={"hosts": ["10.9.0.5"]})
        assert bad.status_code == 400
        assert bad.json()["code"] == "scope_violation"


# --- BR-U4-07/31: worker rechaza antes de sondear + logs --------------------


def test_out_of_scope_run_failed_without_packets(
    tmp_path, caplog: pytest.LogCaptureFixture
) -> None:  # type: ignore[no-untyped-def]
    """Sin env (API no valida) ⇒ el worker rechaza: sin probes, run failed."""
    dsettings = DiscoverySettings(scope_mode="explicit_hosts", hosts="10.0.0.1", ports="22")
    scanner = RecordingScanner()
    ingest = RecordingIngest()
    runner = CycleRunnerImpl(dsettings, scanner=scanner, client=ingest)
    with _client(tmp_path, runner=runner) as client:
        with caplog.at_level(logging.INFO):
            r = client.post("/api/v1/discovery", json={"hosts": ["10.9.9.9"]})
            assert r.status_code == 202
            body = _wait(client, r.json()["run_id"])
        assert body["status"] == "failed"
        events = [getattr(rec, "event", None) for rec in caplog.records]
        assert "scope_violation" in events
        assert "discovery_cycle_failed" in events
        failed_log = next(
            rec for rec in caplog.records if getattr(rec, "event", None) == "discovery_cycle_failed"
        )
        assert failed_log.cause == "scope_violation"
        assert failed_log.run_id == body["run_id"]
        # BR-U4-07: ni un solo paquete ni lote
        assert scanner.ping_calls == []
        assert scanner.tcp_calls == []
        assert scanner.nmap_calls == []
        assert ingest.calls == []


def test_worker_scope_violation_before_probes() -> None:  # type: ignore[no-untyped-def]
    dsettings = DiscoverySettings(scope_mode="explicit_hosts", hosts="10.0.0.1", ports="22")
    scanner = RecordingScanner()
    ingest = RecordingIngest()

    with pytest.raises(ScopeError, match="fuera de alcance"):
        run_cycle(dsettings, scanner, ingest, 10, hosts=["10.9.9.9"])
    assert scanner.ping_calls == []
    assert scanner.tcp_calls == []
    assert scanner.nmap_calls == []
    assert ingest.calls == []


# --- BR-U4-09: allowlist de puertos -----------------------------------------


def test_ports_allowlist_only_receives_probes() -> None:  # type: ignore[no-untyped-def]
    dsettings = DiscoverySettings(scope_mode="explicit_hosts", hosts="192.168.1.10", ports="22")
    scanner = RecordingScanner()
    ingest = RecordingIngest()
    result = run_cycle(dsettings, scanner, ingest, 10)
    assert result.status == "completed"
    assert scanner.tcp_calls, "se esperaba al menos un probe TCP"
    assert all(port == 22 for _host, port in scanner.tcp_calls)
    assert scanner.nmap_calls
    _targets, nmap_ports = scanner.nmap_calls[0]
    assert nmap_ports == (22,)
    assert ingest.calls and ingest.calls[0]["reconcile"] is True
