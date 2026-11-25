"""Integración de fallos de ciclo U4 (ST-M1-06/ST-M2-06, BR-U4-25/28).

- ``metrics_increment``: run ``failed``/``timeout`` ⇒ ``CycleCounter`` +
  log ``discovery_cycle_failed`` (run_id, causa); ``completed`` solo
  incrementa ``cycles_total`` (BR-U4-28).
- ``no_asset_missing``: ciclo ``failed`` ⇒ **sin lote** ⇒ sin reconciliación
  ⇒ jamás ``asset_missing`` (BR-U4-25).
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from sentinel.core.api.app import create_app
from sentinel.core.config import CoreSettings
from sentinel.core.discovery.trigger import DiscoveryTimeoutError
from sentinel.discovery.config import DiscoverySettings
from sentinel.discovery.runner import CycleRunnerImpl
from sentinel.discovery.scanner import FixtureScanner, ScannerError

TOKEN = "test-token"


class OkRunner:
    def run(self, hosts: list[str], timeout_seconds: int) -> int:
        return len(hosts)


class FailingRunner:
    def run(self, hosts: list[str], timeout_seconds: int) -> int:
        raise RuntimeError("runner exploded")


class TimeoutRunner:
    def run(self, hosts: list[str], timeout_seconds: int) -> int:
        raise DiscoveryTimeoutError("cycle exceeded deadline")


class BrokenScanner(FixtureScanner):
    """Escáner que falla en la fase ARP (antes de cualquier ingesta)."""

    def arp_neighbors(self) -> dict[str, str]:
        raise ScannerError("arp exploded")


class RecordingIngest:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def post_ingest(self, items, *, reconcile: bool):  # type: ignore[no-untyped-def]
        self.calls.append({"items": list(items), "reconcile": reconcile})
        return {"accepted": len(items)}

    def close(self) -> None:
        pass


@contextmanager
def _client(tmp_path, runner=None, *, missing_cycles: int = 3) -> Iterator[TestClient]:  # type: ignore[no-untyped-def]
    settings = CoreSettings(
        db_path=str(tmp_path / "failure.db"),
        ingest_token=TOKEN,
        page_limit=100,
        missing_cycles=missing_cycles,
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


def _ingest_hosts(client: TestClient, ips: list[str]) -> None:  # type: ignore[no-untyped-def]
    now = datetime.now(UTC).isoformat()
    batch = {
        "items": [
            {"source": "discovery", "observed_at": now, "ip": ip, "method": "arp"} for ip in ips
        ],
        "reconcile": True,
    }
    r = client.post("/api/v1/ingest", json=batch, headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 202, r.text


def _events(client: TestClient) -> list[dict]:  # type: ignore[no-untyped-def]
    body = client.get("/api/v1/events?limit=500").json()
    return list(body["items"])


# --- BR-U4-28: counter + log de fallo ---------------------------------------


def test_metrics_increment_failed(tmp_path, caplog: pytest.LogCaptureFixture) -> None:  # type: ignore[no-untyped-def]
    with _client(tmp_path, runner=FailingRunner()) as client:
        with caplog.at_level(logging.INFO):
            r = client.post("/api/v1/discovery", json={"hosts": ["10.0.0.1"]})
            body = _wait(client, r.json()["run_id"])
        assert body["status"] == "failed"
        assert body["error"] == "runner exploded"
        counter = client.app.state.cycle_counter
        assert counter.snapshot() == {"failed": 1}
        assert counter.failed_total() == 1
        failed_logs = [
            rec for rec in caplog.records if getattr(rec, "event", None) == "discovery_cycle_failed"
        ]
        assert len(failed_logs) == 1
        assert failed_logs[0].run_id == body["run_id"]
        assert "runner exploded" in str(failed_logs[0].cause)


def test_metrics_increment_timeout(tmp_path, caplog: pytest.LogCaptureFixture) -> None:  # type: ignore[no-untyped-def]
    with _client(tmp_path, runner=TimeoutRunner()) as client:
        with caplog.at_level(logging.INFO):
            r = client.post("/api/v1/discovery", json={"hosts": ["10.0.0.1"]})
            body = _wait(client, r.json()["run_id"])
        assert body["status"] == "timeout"
        counter = client.app.state.cycle_counter
        assert counter.snapshot() == {"timeout": 1}
        assert counter.failed_total() == 1
        failed_logs = [
            rec for rec in caplog.records if getattr(rec, "event", None) == "discovery_cycle_failed"
        ]
        assert len(failed_logs) == 1
        assert failed_logs[0].cause == "timeout"


def test_metrics_increment_completed(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with _client(tmp_path, runner=OkRunner()) as client:
        r = client.post("/api/v1/discovery", json={"hosts": ["10.0.0.1", "10.0.0.2"]})
        body = _wait(client, r.json()["run_id"])
        assert body["status"] == "completed"
        counter = client.app.state.cycle_counter
        assert counter.snapshot() == {"completed": 1}
        assert counter.failed_total() == 0


# --- BR-U4-25: ciclo failed ⇒ sin lote ⇒ sin AssetMissing ------------------


def test_no_asset_missing_on_failed_cycle(tmp_path) -> None:  # type: ignore[no-untyped-def]
    dsettings = DiscoverySettings(
        scope_mode="explicit_hosts", hosts="10.0.0.1,10.0.0.2", ports="22"
    )
    ingest = RecordingIngest()
    runner = CycleRunnerImpl(dsettings, scanner=BrokenScanner(), client=ingest)
    with _client(tmp_path, runner=runner, missing_cycles=1) as client:
        _ingest_hosts(client, ["10.0.0.1", "10.0.0.2"])
        before = _events(client)
        assert not any(e["type"] == "asset_missing" for e in before)

        r = client.post("/api/v1/discovery", json={"hosts": ["10.0.0.1", "10.0.0.2"]})
        body = _wait(client, r.json()["run_id"])
        assert body["status"] == "failed"
        # BR-U4-25: el ciclo fallido jamás envía lote
        assert ingest.calls == []

        after = _events(client)
        assert not any(e["type"] == "asset_missing" for e in after)
        assets = client.get("/api/v1/assets").json()
        assert assets["total"] == 2
        assert all(a["status"] == "present" for a in assets["items"])
