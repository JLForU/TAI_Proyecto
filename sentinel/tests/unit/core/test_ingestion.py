"""Tests de IngestionService (ST-M4-01/03/04, BR-U2-05..08/11)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from sentinel.core.db.database import Database
from sentinel.core.db.repos.observations import ObservationRepository
from sentinel.core.ingestion.dedup import dedup_key
from sentinel.core.ingestion.service import IngestionService
from sentinel.foundation.errors import StorageError
from sentinel.foundation.models import (
    Batch,
    DiscoveryObservation,
    FlowPair,
    TrafficObservation,
)

NOW = datetime(2026, 11, 11, 10, 0, 0, tzinfo=UTC)


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    database = Database(str(tmp_path / "ing.db"))
    database.startup_checks()
    yield database
    database.close()


@pytest.fixture()
def svc(db: Database) -> IngestionService:
    return IngestionService(db, missing_cycles=3)


def _disc(ip: str, mac: str = "aa:bb:cc:dd:ee:ff", t: datetime = NOW) -> DiscoveryObservation:
    return DiscoveryObservation(observed_at=t, ip=ip, mac=mac, hostname="host", method="arp")


def test_valid_batch_accepted(db: Database, svc: IngestionService) -> None:
    result = svc.process(Batch(items=[_disc("10.0.0.1"), _disc("10.0.0.2")]))
    assert result.accepted == 2
    assert result.deduplicated == 0
    assert result.events_persisted == 2  # asset_first_seen x2
    with db.read() as conn:
        assert ObservationRepository().count(conn) == 2


def test_same_batch_twice_does_not_duplicate(db: Database, svc: IngestionService) -> None:
    batch = Batch(items=[_disc("10.0.0.1"), _disc("10.0.0.2")])
    first = svc.process(batch)
    second = svc.process(batch)
    assert second.accepted == 0
    assert second.deduplicated == 2
    assert second.events_persisted == 0
    with db.read() as conn:
        assert ObservationRepository().count(conn) == 2
        assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == first.events_persisted


def test_mac_case_does_not_change_event_id(db: Database, svc: IngestionService) -> None:
    """BR-U2-08 / PB-U2-02: mismo contenido en distinto formato ⇒ misma clave."""
    upper = DiscoveryObservation(
        observed_at=NOW, ip="10.0.0.1", mac="AA:BB:CC:DD:EE:FF", hostname="host", method="arp"
    )
    lower = _disc("10.0.0.1")
    assert dedup_key(upper) == dedup_key(lower)
    svc.process(Batch(items=[lower]))
    result = svc.process(Batch(items=[upper]))
    assert result.accepted == 0 and result.deduplicated == 1


def test_traffic_correlates_by_ip(db: Database, svc: IngestionService) -> None:
    svc.process(Batch(items=[_disc("10.0.0.1")]))
    traffic = TrafficObservation(
        observed_at=NOW,
        window_start=NOW,
        window_end=NOW + timedelta(seconds=5),
        interface="eth0",
        protocol="tcp",
        packet_length_bytes=64,
        bytes_per_second=12.5,
        packets=3,
        flows=1,
        pairs=[FlowPair(src_ip="10.0.0.1", dst_ip="10.0.0.9")],
    )
    svc.process(Batch(items=[traffic]))
    with db.read() as conn:
        row = conn.execute(
            "SELECT o.asset_id FROM observations o WHERE o.source='traffic'"
        ).fetchone()
        assert row["asset_id"] is not None
        asset = conn.execute(
            "SELECT asset_id FROM assets WHERE asset_id = ?", (row["asset_id"],)
        ).fetchone()
        assert asset is not None


def test_rollback_on_failure_leaves_no_partial_writes(db: Database) -> None:
    """BR-U2-05 / REL-04: error a mitad de lote ⇒ rollback total."""
    svc = IngestionService(db, missing_cycles=3)

    original = ObservationRepository().insert_ignore
    calls = {"n": 0}

    def flaky(conn, obs):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] == 3:
            raise StorageError("forced failure")
        return original(conn, obs)

    svc._observations.insert_ignore = flaky  # type: ignore[method-assign]
    batch = Batch(items=[_disc(f"10.0.0.{i}") for i in range(1, 6)])
    with pytest.raises(StorageError):
        svc.process(batch)
    with db.read() as conn:
        assert conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0


def test_invalid_item_rejected_before_processing(db: Database) -> None:
    from pydantic import ValidationError as PydanticValidationError

    with pytest.raises(PydanticValidationError):
        Batch(items=[{"source": "discovery", "observed_at": "not-a-date"}])  # type: ignore[list-item]
    with db.read() as conn:
        assert ObservationRepository().count(conn) == 0
