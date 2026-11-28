"""Tests del ResetService: limpieza total y bloqueo con discovery en curso."""

from __future__ import annotations

from pathlib import Path

import pytest

from sentinel.core.db.database import Database
from sentinel.core.errors import ConflictError
from sentinel.core.reset.service import RESET_TABLES, ResetService


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    database = Database(str(tmp_path / "reset.db"))
    database.startup_checks()
    yield database
    database.close()


def _seed(db: Database, *, run_status: str = "completed") -> None:
    with db.write() as conn:
        conn.execute(
            "INSERT INTO assets (asset_id, status, first_seen, last_seen, source)"
            " VALUES ('a-1', 'present', '2026-01-01', '2026-01-02', 'discovery')"
        )
        conn.execute(
            "INSERT INTO asset_ips (ip, asset_id, first_seen, last_seen)"
            " VALUES ('10.0.0.1', 'a-1', '2026-01-01', '2026-01-02')"
        )
        conn.execute(
            "INSERT INTO observations (dedup_key, asset_id, source, kind, observed_at,"
            " received_at, payload) VALUES ('k-1', 'a-1', 'discovery', 'arp',"
            " '2026-01-01', '2026-01-01', '{}')"
        )
        conn.execute(
            "INSERT INTO events (event_id, type, asset_id, occurred_at, details, created_at)"
            " VALUES ('e-1', 'new_host', 'a-1', '2026-01-01', '{}', '2026-01-01')"
        )
        conn.execute(
            "INSERT INTO alerts (alert_id, condition_id, rule, state, fired_at, updated_at)"
            " VALUES ('al-1', 'c-1', 'R-01', 'firing', '2026-01-01', '2026-01-01')"
        )
        conn.execute(
            "INSERT INTO baselines (metric_key, interval_seconds, samples, updated_at)"
            " VALUES ('bytes_per_second/eth0/tcp', 5, '[]', '2026-01-01')"
        )
        conn.execute(
            "INSERT INTO discovery_runs (run_id, status, \"trigger\", hosts_targeted, started_at)"
            " VALUES ('r-1', ?, 'manual_api', '[]', '2026-01-01')",
            (run_status,),
        )


def _count(db: Database, table: str) -> int:
    with db.read() as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def test_reset_clears_all_derived_tables(db: Database) -> None:
    _seed(db)

    result = ResetService(db).reset()

    assert result.deleted == {table: 1 for table in RESET_TABLES}
    assert result.total == len(RESET_TABLES)
    for table in RESET_TABLES:
        assert _count(db, table) == 0


def test_reset_blocks_when_discovery_running_and_keeps_data(db: Database) -> None:
    _seed(db, run_status="running")

    with pytest.raises(ConflictError):
        ResetService(db).reset()

    assert _count(db, "assets") == 1
    assert _count(db, "discovery_runs") == 1
