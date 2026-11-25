"""Tests de HealthService (ST-M4-08, AVAIL-01/02, Q11 FD)."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from sentinel.core.db.database import Database
from sentinel.core.db.repos.discovery_runs import DiscoveryRunRepository
from sentinel.core.health.service import HealthService
from sentinel.core.ingestion.service import IngestionService
from sentinel.foundation.models import Batch, DiscoveryObservation

NOW = datetime(2026, 11, 11, 10, 0, 0, tzinfo=UTC)


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    database = Database(str(tmp_path / "health.db"))
    database.startup_checks()
    yield database
    database.close()


def test_health_up_with_counts_and_heartbeats(db: Database) -> None:
    ing = IngestionService(db, missing_cycles=3)
    ing.process(
        Batch(
            items=[
                DiscoveryObservation(
                    observed_at=NOW, ip="10.0.0.1", mac=None, hostname="h", method="arp"
                )
            ]
        )
    )
    with db.write() as conn:
        DiscoveryRunRepository().create(
            conn, hosts=["10.0.0.0/24"], now="2026-11-11T09:00:00+00:00"
        )
    hs = HealthService(db, started_at=time.time() - 5).health()
    assert hs.status == "up" and hs.db_connected is True
    assert hs.uptime_seconds >= 5
    assert hs.counts == {"assets": 1, "events": 1, "alerts": 0}
    assert hs.last_ingest_at is not None
    assert "sensor-0" in hs.sensor_heartbeats
    assert hs.last_discovery_run is not None
    assert hs.last_discovery_run["run_id"]


def test_health_degraded_when_db_unopenable(tmp_path: Path) -> None:
    bad = tmp_path / "not-a-db"
    bad.mkdir()  # la ruta es un directorio: sqlite no puede abrir el archivo
    database = Database(str(bad))
    hs = HealthService(database).health()
    assert hs.status == "degraded" and hs.db_connected is False
