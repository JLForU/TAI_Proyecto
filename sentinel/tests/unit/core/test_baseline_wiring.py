"""Wiring de U6 en core (ID-U6-01, P11/P2, FD §3.6/§3.7)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from sentinel.core.baseline_wiring import AlertStore, BaselineStore, build_condition_service
from sentinel.core.db.database import Database
from sentinel.core.db.repos.alerts import AlertRepository
from sentinel.core.db.repos.baselines import BaselineRepository
from sentinel.foundation.logging import get_logger
from sentinel.foundation.models import TrafficObservation

# Logger en collection ⇒ pytest adjunta su handler de captura (patrón U5/U6).
_log = get_logger("baseline.wiring")

NOW = datetime(2026, 11, 23, 8, 0, 0, tzinfo=UTC)
KEY = "bytes_per_second|eth0|tcp"


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    database = Database(str(tmp_path / "wiring.db"))
    database.startup_checks()
    yield database
    database.close()


def _baseline_row(**over: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "metric_key": KEY,
        "interval_seconds": 5,
        "samples": [100.0] * 5,
        "mean": 100.0,
        "variance": 0.0,
        "established": True,
        "updated_at": NOW.isoformat(),
    }
    row.update(over)
    return row


def _alert_row(**over: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "alert_id": "a-1",
        "condition_id": "c-1",
        "rule": "R-01",
        "metric_key": KEY,
        "asset_id": None,
        "state": "firing",
        "measured_value": 500.0,
        "threshold": 100.0,
        "fired_at": NOW.isoformat(),
        "resolved_at": None,
        "evidence": {"measured_value": 500.0},
        "updated_at": NOW.isoformat(),
    }
    row.update(over)
    return row


def test_adapters_roundtrip(db: Database) -> None:
    b = BaselineStore(db)
    a = AlertStore(db)
    b.upsert(_baseline_row())
    a.upsert(_alert_row())

    b_rows = b.list()
    assert len(b_rows) == 1
    assert b_rows[0]["metric_key"] == KEY
    assert b_rows[0]["established"] in (1, True)

    firing = a.list_firing()
    assert len(firing) == 1
    assert firing[0]["alert_id"] == "a-1"

    a.upsert(_alert_row(state="resolved", resolved_at=NOW.isoformat()))
    assert a.list_firing() == []


def test_hydration_ok(db: Database) -> None:
    with db.write() as conn:
        BaselineRepository().upsert(conn, _baseline_row())
        AlertRepository().upsert(conn, _alert_row())
    svc = build_condition_service(db)
    assert KEY in svc.states
    assert svc.states[KEY].established is True
    assert len(svc.states[KEY].samples) == 5
    assert "c-1" in svc.active_alerts


def test_hydration_failure_starts_empty(db: Database, caplog: pytest.LogCaptureFixture) -> None:
    import logging

    # Tabla inexistente ⇒ el repo lanza ⇒ degradación a servicio vacío.
    with db.write() as conn:
        conn.execute("DROP TABLE baselines")
    with caplog.at_level(logging.WARNING):
        svc = build_condition_service(db)
    assert svc.states == {}
    assert svc.active_alerts == {}
    events = [getattr(r, "event", None) for r in caplog.records]
    assert "baseline_hydration_failed" in events
    # El servicio sigue operativo (on_accepted no lanza).
    from sentinel.foundation.models import TrafficObservation

    svc.on_accepted(
        [
            TrafficObservation(
                observed_at=NOW,
                window_start=NOW,
                window_end=NOW,
                interface="eth0",
                protocol="tcp",  # type: ignore[arg-type]
                packet_length_bytes=500,
                bytes_per_second=100.0,
                packets=1,
                flows=1,
                pairs=[],
                sensor_id="sensor-0",
            )
        ]
    )
    assert KEY in svc.states


def test_create_app_wires_hook(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from sentinel.core.api.app import create_app
    from sentinel.core.config import CoreSettings

    settings = CoreSettings(
        db_path=str(tmp_path / "wire_app.db"),
        ingest_token="test-token",
        page_limit=100,
        missing_cycles=3,
    )
    app = create_app(settings, metrics_port=None)
    assert hasattr(app.state, "condition")
    assert app.state.condition is not None
    hook = app.state.ingestion._on_accepted
    assert hook is not None
    # Servicio hidratado (vacío en BD nueva) y operativo.
    assert app.state.condition.states == {}
    # U7: hook compuesto (condición + contadores de observaciones).
    assert app.state.obs_counters is not None
    now = datetime.now(UTC)
    hook(
        [
            TrafficObservation(
                observed_at=now,
                window_start=now - timedelta(seconds=5),
                window_end=now,
                interface="eth0",
                protocol="tcp",
                packet_length_bytes=500,
                bytes_per_second=100.0,
                packets=5,
                flows=5,
            )
        ]
    )
    assert app.state.obs_counters.snapshot()["flows_total"] == 5
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/api/v1/health").status_code == 200


def test_condition_id_and_alert_id_stable_via_wiring(db: Database) -> None:
    """Identidad determinista pasando por los adaptadores reales (BR-U6-17)."""
    from sentinel.baseline.conditions import alert_id_for, condition_id_for

    cid = condition_id_for(KEY)
    aid = alert_id_for(cid, NOW.isoformat())
    a = AlertStore(db)
    a.upsert(_alert_row(alert_id=aid, condition_id=cid))
    rows = a.list_firing()
    assert rows[0]["alert_id"] == aid
    assert rows[0]["condition_id"] == cid
