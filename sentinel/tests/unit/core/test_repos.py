"""Tests de los repositorios de U2 (BR-U2-06/07/11/21..24/33)."""

from __future__ import annotations

from pathlib import Path

import pytest

from sentinel.core.db.database import Database
from sentinel.core.db.repos.alerts import AlertRepository
from sentinel.core.db.repos.assets import AssetRepository
from sentinel.core.db.repos.discovery_runs import DiscoveryRunRepository
from sentinel.core.db.repos.events import EventRepository
from sentinel.core.db.repos.observations import ObservationRepository


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    database = Database(str(tmp_path / "repos.db"))
    database.startup_checks()
    yield database
    database.close()


def _create_asset(db: Database, ip: str = "10.0.0.1", mac: str | None = "aa:bb:cc:dd:ee:ff") -> str:
    assets = AssetRepository()
    with db.write() as conn:
        return assets.create(
            conn,
            ip=ip,
            mac=mac,
            hostname="h1",
            os_name=None,
            os_provenance="unknown",
            source="discovery",
            sensor_id="s0",
        )


def test_asset_create_and_find_by_ip(db: Database) -> None:
    asset_id = _create_asset(db)
    assets = AssetRepository()
    with db.read() as conn:
        assert assets.find_asset_id_by_ip(conn, "10.0.0.1") == asset_id
        assert assets.find_asset_id_by_ip(conn, "10.0.0.99") is None
        assert assets.get(conn, asset_id) is not None
        assert assets.get(conn, "missing") is None


def test_asset_touch_detects_mac_change(db: Database) -> None:
    asset_id = _create_asset(db)
    assets = AssetRepository()
    with db.write() as conn:
        changed = assets.touch(
            conn,
            asset_id=asset_id,
            ip="10.0.0.1",
            mac="11:22:33:44:55:66",
            hostname=None,
            os_name=None,
        )
    assert changed is True
    with db.read() as conn:
        row = assets.get(conn, asset_id)
        assert row is not None and row["mac"] == "11:22:33:44:55:66"


def test_asset_list_filters_and_pagination(db: Database) -> None:
    for i in range(5):
        _create_asset(db, ip=f"10.0.0.{i}")
    assets = AssetRepository()
    with db.write() as conn:
        row = assets.get_by_ip(conn, "10.0.0.0")
        assert row is not None
        assets.mark_absent(conn, row["asset_id"])
    with db.read() as conn:
        rows, total = assets.list(conn, status="absent", limit=10, offset=0)
        assert total == 1 and len(rows) == 1
        rows, total = assets.list(conn, limit=2, offset=0)
        assert total == 5 and len(rows) == 2


def test_observation_insert_ignore_dedup(db: Database) -> None:
    asset_id = _create_asset(db)
    obs = ObservationRepository()
    payload = {
        "dedup_key": "k1",
        "asset_id": asset_id,
        "source": "discovery",
        "kind": "tcp",
        "sensor_id": "s0",
        "observed_at": "2026-01-01T00:00:00+00:00",
        "received_at": "2026-01-01T00:00:01+00:00",
        "payload": {"port": 80},
    }
    with db.write() as conn:
        assert obs.insert_ignore(conn, payload) is True
        assert obs.insert_ignore(conn, payload) is False
    with db.read() as conn:
        assert obs.count(conn) == 1
        rows = obs.list_by_asset(conn, asset_id)
        assert len(rows) == 1


def test_event_save_ignore_and_filters_pagination(db: Database) -> None:
    events = EventRepository()
    base = {
        "type": "asset_first_seen",
        "asset_id": None,
        "severity": "info",
        "rule": None,
        "details": {},
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    with db.write() as conn:
        for i in range(3):
            assert events.save_ignore(
                conn,
                {**base, "event_id": f"e{i}", "occurred_at": f"2026-01-0{i + 1}T00:00:00+00:00"},
            )
        assert (
            events.save_ignore(
                conn, {**base, "event_id": "e0", "occurred_at": "2026-01-01T00:00:00+00:00"}
            )
            is False
        )
    with db.read() as conn:
        rows, total = events.list(conn, limit=2, offset=0)
        assert total == 3 and len(rows) == 2
        rows, total = events.list(conn, date_from="2026-01-02Z", date_to="2026-01-03Z")
        assert total == 2
        _, total = events.list(conn, asset_id="nope")
        assert total == 0


def test_alerts_upsert_and_list(db: Database) -> None:
    alerts = AlertRepository()
    alert = {
        "alert_id": "a1",
        "condition_id": "c1",
        "rule": "R-01",
        "metric_key": "m",
        "asset_id": None,
        "state": "firing",
        "measured_value": 10.0,
        "threshold": 5.0,
        "fired_at": "2026-01-01T00:00:00+00:00",
        "resolved_at": None,
        "evidence": {},
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    with db.write() as conn:
        alerts.upsert(conn, alert)
        alerts.upsert(
            conn, {**alert, "state": "resolved", "resolved_at": "2026-01-01T01:00:00+00:00"}
        )
    with db.read() as conn:
        rows, total = alerts.list(conn, state="resolved")
        assert total == 1 and rows[0]["state"] == "resolved"


def test_discovery_runs_lifecycle(db: Database) -> None:
    runs = DiscoveryRunRepository()
    with db.write() as conn:
        run_id = runs.create(conn, hosts=["10.0.0.1"])
        assert runs.any_running(conn) is True
    with db.write() as conn:
        runs.finish(conn, run_id, status="completed", hosts_seen=1)
        assert runs.any_running(conn) is False
    with db.read() as conn:
        row = runs.get(conn, run_id)
        assert row is not None and row["status"] == "completed" and row["hosts_seen"] == 1
        assert runs.latest(conn) is not None
        assert runs.get(conn, "nope") is None
