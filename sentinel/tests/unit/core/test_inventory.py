"""Tests de InventoryService (BR-U2-13..17, ST-M4-04)."""

from __future__ import annotations

from pathlib import Path

import pytest

from sentinel.core.db.database import Database
from sentinel.core.db.repos.assets import AssetRepository
from sentinel.core.db.repos.events import EventRepository
from sentinel.core.inventory.service import InventoryService
from sentinel.foundation.events import EventType

NOW = "2026-11-11T10:00:00+00:00"


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    database = Database(str(tmp_path / "inv.db"))
    database.startup_checks()
    yield database
    database.close()


def _svc() -> InventoryService:
    return InventoryService(AssetRepository(), EventRepository())


def test_first_seen_creates_asset_and_event(db: Database) -> None:
    with db.write() as conn:
        asset_id, changes = _svc().observe(
            conn,
            ip="10.0.0.1",
            mac="aa:bb:cc:dd:ee:ff",
            hostname="h",
            os_name=None,
            os_provenance="unknown",
            source="discovery",
            sensor_id="s0",
            now=NOW,
            create_if_missing=True,
        )
    assert asset_id is not None
    assert len(changes) == 1 and changes[0].type == EventType.ASSET_FIRST_SEEN
    with db.read() as conn:
        row = AssetRepository().get(conn, asset_id)
        assert row is not None and row["status"] == "present" and row["miss_count"] == 0


def test_second_observation_touches_without_event(db: Database) -> None:
    with db.write() as conn:
        asset_id, _ = _svc().observe(
            conn,
            ip="10.0.0.1",
            mac="aa:bb:cc:dd:ee:ff",
            hostname=None,
            os_name=None,
            os_provenance="unknown",
            source="discovery",
            sensor_id="s0",
            now=NOW,
            create_if_missing=True,
        )
        _, changes = _svc().observe(
            conn,
            ip="10.0.0.1",
            mac="aa:bb:cc:dd:ee:ff",
            hostname=None,
            os_name=None,
            os_provenance="unknown",
            source="discovery",
            sensor_id="s0",
            now="2026-11-11T10:05:00+00:00",
            create_if_missing=True,
        )
    assert changes == []
    with db.read() as conn:
        row = AssetRepository().get(conn, asset_id)
        assert row is not None and row["last_seen"] == "2026-11-11T10:05:00+00:00"


def test_mac_change_emits_arp_mapping_changed(db: Database) -> None:
    with db.write() as conn:
        svc = _svc()
        asset_id, _ = svc.observe(
            conn,
            ip="10.0.0.1",
            mac="aa:bb:cc:dd:ee:ff",
            hostname=None,
            os_name=None,
            os_provenance="unknown",
            source="discovery",
            sensor_id="s0",
            now=NOW,
            create_if_missing=True,
        )
        _, changes = svc.observe(
            conn,
            ip="10.0.0.1",
            mac="11:22:33:44:55:66",
            hostname=None,
            os_name=None,
            os_provenance="unknown",
            source="discovery",
            sensor_id="s0",
            now="2026-11-11T10:05:00+00:00",
            create_if_missing=True,
        )
    assert len(changes) == 1 and changes[0].type == EventType.ARP_MAPPING_CHANGED
    with db.read() as conn:
        row = AssetRepository().get(conn, asset_id)
        assert row is not None and row["mac"] == "11:22:33:44:55:66"


def test_missing_threshold_three_completed_cycles(db: Database) -> None:
    """BR-U2-14: N=3 ⇒ absent; BR-U2-15: sin discovery no incrementa."""
    svc = _svc()
    with db.write() as conn:
        a1, _ = svc.observe(
            conn,
            ip="10.0.0.1",
            mac=None,
            hostname=None,
            os_name=None,
            os_provenance="unknown",
            source="discovery",
            sensor_id="s0",
            now=NOW,
            create_if_missing=True,
        )
        a2, _ = svc.observe(
            conn,
            ip="10.0.0.2",
            mac=None,
            hostname=None,
            os_name=None,
            os_provenance="unknown",
            source="discovery",
            sensor_id="s0",
            now=NOW,
            create_if_missing=True,
        )
    # 2 ciclos sin ver 10.0.0.2
    for i in range(2):
        with db.write() as conn:
            svc.reconcile_missing(
                conn,
                seen_asset_ids={a1},
                missing_cycles=3,
                now=f"2026-11-11T11:0{i}:00+00:00",
            )
    with db.read() as conn:
        assert AssetRepository().get(conn, a2)["status"] == "present"  # type: ignore[index]
    # 3er ciclo ⇒ absent + evento
    with db.write() as conn:
        changes = svc.reconcile_missing(
            conn, seen_asset_ids={a1}, missing_cycles=3, now="2026-11-11T12:00:00+00:00"
        )
    with db.read() as conn:
        row = AssetRepository().get(conn, a2)
        assert row is not None and row["status"] == "absent"
        assert any(c.type == EventType.ASSET_MISSING for c in changes)
        # reaparición ⇒ present y miss_count 0
    with db.write() as conn:
        svc.observe(
            conn,
            ip="10.0.0.2",
            mac=None,
            hostname=None,
            os_name=None,
            os_provenance="unknown",
            source="discovery",
            sensor_id="s0",
            now="2026-11-11T13:00:00+00:00",
            create_if_missing=True,
        )
    with db.read() as conn:
        row = AssetRepository().get(conn, a2)
        assert row is not None and row["status"] == "present" and row["miss_count"] == 0
    # a1 sigue present: reconciliar sin ver a1 tres veces lo marca absent
    for i in range(3):
        with db.write() as conn:
            svc.reconcile_missing(
                conn, seen_asset_ids=set(), missing_cycles=3, now=f"2026-11-11T14:0{i}:00+00:00"
            )
    with db.read() as conn:
        assert AssetRepository().get(conn, a1)["status"] == "absent"  # type: ignore[index]
