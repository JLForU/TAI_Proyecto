"""ST-M5-03/GT-04: supresión init/after window + ciclo de vida de alerta (U6).

``TestClient`` + BD temporal + ``condition_clock`` falso (seam ID-U6-07) +
``baseline_settings`` explícito ⇒ determinismo total sin env.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from sentinel.baseline.config import BaselineSettings
from sentinel.core.api.app import create_app
from sentinel.core.config import CoreSettings

T0 = datetime(2026, 11, 19, 12, 0, 0, tzinfo=UTC)
TOKEN = "t"
EVIDENCE_KEYS = {
    "measured_value",
    "threshold",
    "k",
    "mu",
    "sigma",
    "window_start",
    "interface",
    "protocol",
    "sensor_id",
}


class FakeClock:
    def __init__(self, start: datetime = T0) -> None:
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += timedelta(seconds=seconds)


def _client(tmp_path, clock: FakeClock):  # type: ignore[no-untyped-def]
    settings = CoreSettings(
        db_path=str(tmp_path / "baseline.db"),
        ingest_token=TOKEN,
        page_limit=100,
        missing_cycles=3,
    )
    app = create_app(
        settings,
        metrics_port=None,
        condition_clock=clock,
        baseline_settings=BaselineSettings(absolute_bps=None),
    )
    return TestClient(app, raise_server_exceptions=False)


def _traffic(bps: float, at: datetime, *, packets: int = 10, flows: int = 2) -> dict:
    return {
        "source": "traffic",
        "observed_at": at.isoformat(),
        "sensor_id": "sensor-0",
        "window_start": (at - timedelta(seconds=5)).isoformat(),
        "window_end": at.isoformat(),
        "interface": "eth0",
        "protocol": "tcp",
        "packet_length_bytes": int(bps * 5),
        "bytes_per_second": bps,
        "packets": packets,
        "flows": flows,
        "pairs": [{"src_ip": "10.0.0.1", "dst_ip": "10.0.1.1"}],
    }


def _post(client: TestClient, payload: dict) -> None:
    resp = client.post(
        "/api/v1/ingest", json={"items": [payload]}, headers={"Authorization": f"Bearer {TOKEN}"}
    )
    assert resp.status_code == 202, resp.text
    assert resp.json()["accepted"] == 1, resp.text


def _rows(db_path, table: str) -> list[dict]:  # type: ignore[no-untyped-def]
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(f"SELECT * FROM {table}")]
    finally:
        conn.close()


# --- Step 18: supresión init vs after window -------------------------------


def test_init_window_no_alerts(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """5 obs DENTRO de la ventana ⇒ baselines con established, SIN alerts."""
    clock = FakeClock()
    db_path = tmp_path / "baseline.db"
    with _client(tmp_path, clock) as client:
        for i in range(5):  # todas en t0 (FakeClock sin avanzar)
            _post(client, _traffic(100.0, T0 + timedelta(seconds=i)))

    baselines = _rows(db_path, "baselines")
    assert len(baselines) == 3  # bytes_per_second | packets | flows (eth0/tcp)
    bytes_row = next(r for r in baselines if r["metric_key"].startswith("bytes_per_second"))
    assert bytes_row["established"] == 1  # 5/5 muestras ⇒ congelada
    assert len(json.loads(bytes_row["samples"])) == 5

    alerts = _rows(db_path, "alerts")
    assert alerts == []  # supresión prioritaria (ST-M5-03): cero alertas


def test_after_window_fires(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Reloj > t_first+5×interval + bps alto ⇒ fila alerts firing R-01."""
    clock = FakeClock()
    db_path = tmp_path / "baseline.db"
    with _client(tmp_path, clock) as client:
        for i in range(5):
            _post(client, _traffic(100.0, T0 + timedelta(seconds=i)))
        clock.advance(30)  # > 5×5s ⇒ la ventana de supresión cerró
        _post(client, _traffic(5_000.0, T0 + timedelta(seconds=40)))

    alerts = _rows(db_path, "alerts")
    assert len(alerts) == 1
    row = alerts[0]
    assert row["rule"] == "R-01"
    assert row["state"] == "firing"
    assert row["metric_key"] == "bytes_per_second|eth0|tcp"
    assert row["measured_value"] == 5_000.0
    assert row["threshold"] == 100.0  # μ=100, σ=0, k=3
    assert row["fired_at"] is not None and row["resolved_at"] is None
    assert set(json.loads(row["evidence"])) == EVIDENCE_KEYS


# --- Step 19: ciclo de vida (BR-U6-17) + evidencia -------------------------


def test_fire_resolve_refire(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """firing ⇒ resolved en la MISMA fila ⇒ re-fire ⇒ fila nueva (id distinto)."""
    clock = FakeClock()
    db_path = tmp_path / "baseline.db"
    with _client(tmp_path, clock) as client:
        for i in range(5):
            _post(client, _traffic(100.0, T0 + timedelta(seconds=i)))
        clock.advance(30)
        _post(client, _traffic(5_000.0, T0 + timedelta(seconds=40)))  # fire
        _post(client, _traffic(10.0, T0 + timedelta(seconds=45)))  # resolve
        clock.advance(5)
        _post(client, _traffic(9_000.0, T0 + timedelta(seconds=55)))  # re-fire

    alerts = _rows(db_path, "alerts")
    assert len(alerts) == 2, [a["alert_id"] for a in alerts]
    by_state = {a["state"]: a for a in alerts}
    assert set(by_state) == {"firing", "resolved"}
    first_id = by_state["resolved"]["alert_id"]
    second_id = by_state["firing"]["alert_id"]
    assert first_id != second_id  # re-fire ⇒ identidad nueva (uuid5 fired_at)
    assert by_state["resolved"]["resolved_at"] is not None
    assert by_state["resolved"]["measured_value"] == 10.0
    assert by_state["firing"]["measured_value"] == 9_000.0
    # La fila resolved conserva el primer fired_at (misma activación)
    assert by_state["resolved"]["fired_at"] != by_state["firing"]["fired_at"]


def test_evidence_fields(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Claves EXACTAS de evidence en la alerta persistida (FR-BASE-04)."""
    clock = FakeClock()
    db_path = tmp_path / "baseline.db"
    with _client(tmp_path, clock) as client:
        for i in range(5):
            _post(client, _traffic(100.0, T0 + timedelta(seconds=i)))
        clock.advance(30)
        _post(client, _traffic(5_000.0, T0 + timedelta(seconds=40)))

    (row,) = _rows(db_path, "alerts")
    evidence = json.loads(row["evidence"])
    assert set(evidence) == EVIDENCE_KEYS
    assert evidence["interface"] == "eth0"
    assert evidence["protocol"] == "tcp"
    assert evidence["sensor_id"] == "sensor-0"
    assert evidence["measured_value"] == 5_000.0
    assert evidence["threshold"] == 100.0
    assert evidence["k"] == 3.0
    assert evidence["mu"] == 100.0
    assert evidence["sigma"] == 0.0
    assert evidence["window_start"] == (T0 + timedelta(seconds=35)).isoformat()
