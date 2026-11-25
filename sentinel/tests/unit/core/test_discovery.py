"""Tests de DiscoveryTrigger (ST-M4-05, BR-U2-30..33, P2, Q9 FD)."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from sentinel.core.db.database import Database
from sentinel.core.discovery.trigger import DiscoveryTimeoutError, DiscoveryTrigger
from sentinel.core.errors import ConflictError, RunnerUnavailableError


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    database = Database(str(tmp_path / "disc.db"))
    database.startup_checks()
    yield database
    database.close()


class OkRunner:
    def run(self, hosts: list[str], timeout_seconds: int) -> int:
        return len(hosts)


class TimeoutRunner:
    def run(self, hosts: list[str], timeout_seconds: int) -> int:
        raise DiscoveryTimeoutError("timed out")


class FailRunner:
    def run(self, hosts: list[str], timeout_seconds: int) -> int:
        raise RuntimeError("scanner exploded")


def test_unavailable_without_runner(db: Database) -> None:
    with pytest.raises(RunnerUnavailableError) as exc:
        DiscoveryTrigger(db).trigger(["10.0.0.0/24"], 5)
    assert exc.value.code == "runner_unavailable"


def test_completed_run_persists_result(db: Database) -> None:
    trigger = DiscoveryTrigger(db, runner=OkRunner())
    status = trigger.trigger(["10.0.0.0/24", "10.0.1.0/24"], 5, wait=True)
    assert status.status == "completed" and status.hosts_seen == 2
    with db.read() as conn:
        row = conn.execute("SELECT status FROM discovery_runs").fetchone()
        assert row["status"] == "completed"


def test_timeout_and_failed_states(db: Database) -> None:
    t1 = DiscoveryTrigger(db, runner=TimeoutRunner())
    s1 = t1.trigger(["a"], 1, wait=True)
    assert s1.status == "timeout" and s1.error
    t2 = DiscoveryTrigger(db, runner=FailRunner())
    s2 = t2.trigger(["a"], 1, wait=True)
    assert s2.status == "failed" and "scanner" in (s2.error or "")
    with db.read() as conn:
        statuses = [
            r["status"] for r in conn.execute("SELECT status FROM discovery_runs ORDER BY rowid")
        ]
    assert statuses == ["timeout", "failed"]


def test_conflict_while_running(db: Database) -> None:
    gate = threading.Event()

    class SlowRunner:
        def run(self, hosts: list[str], timeout_seconds: int) -> int:
            gate.wait(timeout=5)
            return len(hosts)

    trigger = DiscoveryTrigger(db, runner=SlowRunner())
    first = trigger.trigger(["a"], 5)
    assert first.status == "running"
    with pytest.raises(ConflictError) as exc:
        trigger.trigger(["b"], 5)
    assert exc.value.code == "conflict"
    gate.set()
    deadline = threading.Event()
    for _ in range(100):
        with db.read() as conn:
            row = conn.execute(
                "SELECT status FROM discovery_runs WHERE run_id = ?", (first.run_id,)
            ).fetchone()
        if row["status"] == "completed":
            break
        deadline.wait(0.05)
    else:  # pragma: no cover
        pytest.fail("run never completed")
