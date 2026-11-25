"""Tests de ``core.db.database`` (P1–P4, BR-U2-18/19/20, REL-01/02)."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from sentinel.core.db.database import Database, DbIntegrityError


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    database = Database(str(tmp_path / "test.db"))
    database.startup_checks()
    yield database
    database.close()


def test_schema_idempotent(db: Database) -> None:
    db.startup_checks()
    with db.read() as conn:
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
    assert {
        "assets",
        "asset_ips",
        "observations",
        "events",
        "alerts",
        "baselines",
        "discovery_runs",
    } <= tables


def test_write_lock_serializes_concurrent_writers(db: Database) -> None:
    errors: list[BaseException] = []

    def writer(i: int) -> None:
        try:
            with db.write() as conn:
                conn.execute(
                    "INSERT INTO baselines (metric_key, interval_seconds, samples, mean,"
                    " variance, established, updated_at) VALUES (?, 5, '[]', 0, 0, 0, 't')",
                    (f"m{i}",),
                )
        except BaseException as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    with db.read() as conn:
        assert conn.execute("SELECT COUNT(*) FROM baselines").fetchone()[0] == 20


def test_rollback_on_error(db: Database) -> None:
    with pytest.raises(RuntimeError), db.write() as conn:
        conn.execute(
            "INSERT INTO baselines (metric_key, interval_seconds, samples, mean,"
            " variance, established, updated_at) VALUES ('k', 5, '[]', 0, 0, 0, 't')"
        )
        raise RuntimeError("boom")
    with db.read() as conn:
        assert conn.execute("SELECT COUNT(*) FROM baselines").fetchone()[0] == 0


def test_stale_running_runs_marked_failed(db: Database) -> None:
    with db.write() as conn:
        conn.execute(
            'INSERT INTO discovery_runs (run_id, status, "trigger", hosts_targeted,'
            " started_at) VALUES ('r1', 'running', 'manual_api', '[]', '2026-01-01T00:00:00+00:00')"
        )
    db.startup_checks()
    with db.read() as conn:
        row = conn.execute("SELECT status, error FROM discovery_runs WHERE run_id='r1'").fetchone()
    assert row["status"] == "failed"
    assert row["error"] == "core restarted"


def test_integrity_check_fails_without_touching_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.db"
    payload = b"not a database at all" * 10
    bad.write_bytes(payload)
    with pytest.raises(DbIntegrityError):
        Database(str(bad)).startup_checks()
    assert bad.read_bytes() == payload


def test_close_runs_wal_checkpoint(db: Database) -> None:
    with db.write() as conn:
        conn.execute(
            "INSERT INTO baselines (metric_key, interval_seconds, samples, mean,"
            " variance, established, updated_at) VALUES ('k', 5, '[]', 0, 0, 0, 't')"
        )
    db.close()
    # Reabrir: los datos persisten (AVAIL-02 a nivel de archivo)
    db2 = Database(db.path)
    db2.startup_checks()
    with db2.read() as conn:
        assert conn.execute("SELECT COUNT(*) FROM baselines").fetchone()[0] == 1
    db2.close()
