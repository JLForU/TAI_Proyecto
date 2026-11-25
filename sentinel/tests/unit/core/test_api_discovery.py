"""Tests de API de discovery (P2, BR-U2-30..33: 202/409/404/503)."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from sentinel.core.api.app import create_app
from sentinel.core.config import CoreSettings
from sentinel.core.discovery.trigger import DiscoveryTimeoutError

from .conftest import TOKEN


class OkRunner:
    def run(self, hosts: list[str], timeout_seconds: int) -> int:
        return len(hosts)


class TimeoutRunner:
    def run(self, hosts: list[str], timeout_seconds: int) -> int:
        raise DiscoveryTimeoutError("timed out")


@contextmanager
def _client(tmp_path, runner=None) -> Iterator[TestClient]:  # type: ignore[no-untyped-def]
    settings = CoreSettings(
        db_path=str(tmp_path / "disc.db"), ingest_token=TOKEN, page_limit=100, missing_cycles=3
    )
    with TestClient(create_app(settings, runner=runner, metrics_port=None)) as client:
        yield client


def test_discovery_503_without_runner(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with _client(tmp_path, runner=None) as client:
        r = client.post("/api/v1/discovery", json={"hosts": ["10.0.0.0/24"]})
        assert r.status_code == 503
        assert r.json() == {"detail": "discovery runner not available"}


def test_discovery_202_then_completed(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with _client(tmp_path, runner=OkRunner()) as client:
        r = client.post("/api/v1/discovery", json={"hosts": ["a", "b"]})
        assert r.status_code == 202
        body = r.json()
        assert body["status"] in {"running", "completed"}
        run_id = body["run_id"]
        # espera a que termine
        for _ in range(100):
            status = client.get(f"/api/v1/discovery/{run_id}").json()
            if status["status"] in {"completed", "timeout", "failed"}:
                break
            threading.Event().wait(0.05)
        assert status["status"] == "completed"
        assert status["hosts_seen"] == 2


def test_discovery_404_unknown_run(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with _client(tmp_path, runner=OkRunner()) as client:
        r = client.get("/api/v1/discovery/no-such-run")
        assert r.status_code == 404 and r.json() == {"detail": "not found"}


def test_discovery_409_when_already_running(tmp_path) -> None:  # type: ignore[no-untyped-def]
    gate = threading.Event()

    class SlowRunner:
        def run(self, hosts: list[str], timeout_seconds: int) -> int:
            gate.wait(timeout=5)
            return len(hosts)

    with _client(tmp_path, runner=SlowRunner()) as client:
        first = client.post("/api/v1/discovery", json={"hosts": ["a"]})
        assert first.status_code == 202
        second = client.post("/api/v1/discovery", json={"hosts": ["b"]})
        assert second.status_code == 409
        assert second.json() == {"detail": "discovery already running"}
        gate.set()


def test_discovery_422_empty_hosts(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with _client(tmp_path, runner=OkRunner()) as client:
        r = client.post("/api/v1/discovery", json={"hosts": []})
        assert r.status_code == 422


def test_discovery_timeout_state(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with _client(tmp_path, runner=TimeoutRunner()) as client:
        r = client.post("/api/v1/discovery", json={"hosts": ["a"]})
        run_id = r.json()["run_id"]
        for _ in range(100):
            status = client.get(f"/api/v1/discovery/{run_id}").json()
            if status["status"] != "running":
                break
            threading.Event().wait(0.05)
        assert status["status"] == "timeout"


@pytest.mark.parametrize("hosts", [["10.0.0.0/24"], ["192.168.1.1"]])
def test_discovery_accepts_scope_forms(tmp_path, hosts: list[str]) -> None:  # type: ignore[no-untyped-def]
    with _client(tmp_path, runner=OkRunner()) as client:
        r = client.post("/api/v1/discovery", json={"hosts": hosts})
        assert r.status_code == 202
