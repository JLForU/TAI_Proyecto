"""Planes de consulta: EXPLAIN ⇒ USING INDEX (NFR-U2-PERF-03, P8)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from sentinel.core.db.database import Database
from sentinel.core.db.repos.assets import AssetRepository
from sentinel.core.db.repos.events import EventRepository
from sentinel.core.db.repos.observations import ObservationRepository

NOW = datetime(2026, 11, 11, 10, 0, 0, tzinfo=UTC)


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    database = Database(str(tmp_path / "plans.db"))
    database.startup_checks()
    yield database
    database.close()


def _plan(conn, sql: str, params: list) -> str:  # type: ignore[no-untyped-def]
    rows = conn.execute(f"EXPLAIN QUERY PLAN {sql}", params).fetchall()
    return " | ".join(str(r["detail"]) for r in rows)


def _seed(db: Database) -> str:
    with db.write() as conn:
        asset_id = AssetRepository().create(
            conn,
            ip="10.0.0.1",
            mac="aa:bb:cc:dd:ee:ff",
            hostname="h",
            os_name=None,
            os_provenance="unknown",
            source="discovery",
            sensor_id="s0",
            now=NOW.isoformat(),
        )
        events = EventRepository()
        for i in range(20):
            events.save_ignore(
                conn,
                {
                    "event_id": f"00000000-0000-0000-0000-{i:012d}",
                    "type": "asset_first_seen",
                    "asset_id": asset_id,
                    "severity": "info",
                    "rule": None,
                    "occurred_at": (NOW + timedelta(seconds=i)).isoformat(),
                    "details": {},
                },
            )
        ObservationRepository().insert_ignore(
            conn,
            {
                "dedup_key": "00000000-0000-0000-0000-ffffffffffff",
                "asset_id": asset_id,
                "source": "discovery",
                "kind": "arp",
                "sensor_id": "s0",
                "observed_at": NOW.isoformat(),
                "received_at": NOW.isoformat(),
                "payload": {},
            },
        )
    return asset_id


def test_events_range_uses_index(db: Database) -> None:
    _seed(db)
    with db.read() as conn:
        detail = _plan(
            conn,
            "SELECT * FROM events WHERE occurred_at >= ? AND occurred_at <= ?"
            " ORDER BY occurred_at DESC, event_id LIMIT ? OFFSET ?",
            [NOW.isoformat(), NOW.isoformat(), 10, 0],
        )
    assert "USING INDEX" in detail
    assert "idx_events_time" in detail


def test_events_by_asset_uses_index(db: Database) -> None:
    asset_id = _seed(db)
    with db.read() as conn:
        detail = _plan(
            conn,
            "SELECT * FROM events WHERE asset_id = ? ORDER BY occurred_at DESC LIMIT ?",
            [asset_id, 10],
        )
    assert "USING INDEX" in detail
    assert "idx_events_asset" in detail


def test_events_by_rule_uses_index(db: Database) -> None:
    _seed(db)
    with db.read() as conn:
        detail = _plan(conn, "SELECT * FROM events WHERE rule = ?", ["threshold"])
    assert "USING INDEX" in detail
    assert "idx_events_rule" in detail


def test_assets_by_status_uses_index(db: Database) -> None:
    _seed(db)
    with db.read() as conn:
        detail = _plan(
            conn,
            "SELECT * FROM assets WHERE status = ? ORDER BY last_seen DESC LIMIT ? OFFSET ?",
            ["present", 10, 0],
        )
    assert "USING INDEX" in detail


def test_observations_by_asset_time_uses_index(db: Database) -> None:
    asset_id = _seed(db)
    with db.read() as conn:
        detail = _plan(
            conn,
            "SELECT * FROM observations WHERE asset_id = ?"
            " AND observed_at >= ? AND observed_at <= ? ORDER BY observed_at DESC LIMIT ?",
            [asset_id, NOW.isoformat(), NOW.isoformat(), 10],
        )
    assert "USING INDEX" in detail
    assert "idx_obs_asset_time" in detail


def test_alerts_by_state_uses_index(db: Database) -> None:
    _seed(db)
    with db.read() as conn:
        detail = _plan(
            conn,
            "SELECT * FROM alerts WHERE state = ? ORDER BY fired_at DESC LIMIT ? OFFSET ?",
            ["firing", 10, 0],
        )
    assert "USING INDEX" in detail
