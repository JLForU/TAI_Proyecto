"""ST-M4-02 AC1: los datos sobreviven un reinicio del Core (AVAIL-02)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sentinel.core.db.database import Database
from sentinel.core.db.repos.discovery_runs import DiscoveryRunRepository
from sentinel.core.ingestion.service import IngestionService
from sentinel.foundation.models import Batch, DiscoveryObservation


def _batch() -> Batch:
    now = datetime.now(UTC)
    return Batch(
        items=[
            DiscoveryObservation(
                observed_at=now,
                ip="10.0.0.1",
                mac="aa:bb:cc:dd:ee:ff",
                hostname="h1",
                method="arp",
            ),
            DiscoveryObservation(
                observed_at=now,
                ip="10.0.0.2",
                mac="aa:bb:cc:dd:ee:02",
                hostname="h2",
                method="tcp",
            ),
        ]
    )


def test_events_survive_restart(tmp_path: Path) -> None:
    db_path = str(tmp_path / "restart.db")

    # --- proceso 1: ingestar y apagar limpio ---
    db1 = Database(db_path)
    db1.startup_checks()
    result = IngestionService(db1, missing_cycles=3).process(_batch())
    assert result.accepted == 2
    with db1.read() as conn:
        before = [
            (r["event_id"], r["type"])
            for r in conn.execute("SELECT event_id, type FROM events ORDER BY event_id")
        ]
        before_obs = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    db1.close()

    # --- proceso 2 (reinicio): startup_checks + datos consultables ---
    db2 = Database(db_path)
    db2.startup_checks()
    with db2.read() as conn:
        after = [
            (r["event_id"], r["type"])
            for r in conn.execute("SELECT event_id, type FROM events ORDER BY event_id")
        ]
        after_obs = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
        assets = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    assert after == before
    assert after_obs == before_obs == 2
    assert assets == 2
    db2.close()


def test_stale_running_run_marked_failed_on_restart(tmp_path: Path) -> None:
    db_path = str(tmp_path / "stale.db")
    db1 = Database(db_path)
    db1.startup_checks()
    with db1.write() as conn:
        run_id = DiscoveryRunRepository().create(conn, hosts=["10.0.0.0/24"])
    db1.close()  # corte "duro" sin finish()

    db2 = Database(db_path)
    db2.startup_checks()
    with db2.read() as conn:
        row = DiscoveryRunRepository().get(conn, run_id)
    assert row is not None
    assert row["status"] == "failed"
    assert row["error"] == "core restarted"
    db2.close()
