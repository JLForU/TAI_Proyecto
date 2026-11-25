"""ConditionService (U6, C5): estados, supresión, umbral, alertas, degradación."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sentinel.baseline.conditions import (
    ConditionService,
    TrafficWindow,
    alert_id_for,
    condition_id_for,
    metric_key_for,
)
from sentinel.baseline.config import BaselineSettings
from sentinel.foundation.models import ArpObservation, DiscoveryObservation, TrafficObservation

NOW = datetime(2026, 3, 5, 9, 30, 0, tzinfo=UTC)


class FakeClock:
    def __init__(self, start: datetime = NOW) -> None:
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += timedelta(seconds=seconds)


class FakeBaselines:
    def __init__(self, rows: list[dict] | None = None, *, fail: bool = False) -> None:
        self.rows: dict[str, dict] = {r["metric_key"]: dict(r) for r in (rows or [])}
        self.fail = fail

    def list(self) -> list[dict]:
        if self.fail:
            raise RuntimeError("db down")
        return [dict(r) for r in self.rows.values()]

    def upsert(self, baseline: dict) -> None:
        if self.fail:
            raise RuntimeError("db down")
        self.rows[baseline["metric_key"]] = dict(baseline)


class FakeAlerts:
    def __init__(self, rows: list[dict] | None = None, *, fail: bool = False) -> None:
        self.rows: dict[str, dict] = {r["alert_id"]: dict(r) for r in (rows or [])}
        self.fail = fail

    def upsert(self, alert: dict) -> None:
        if self.fail:
            raise RuntimeError("db down")
        self.rows[alert["alert_id"]] = dict(alert)

    def list_firing(self) -> list[dict]:
        if self.fail:
            raise RuntimeError("db down")
        return [dict(r) for r in self.rows.values() if r.get("state") == "firing"]


def _service(
    *,
    baselines: FakeBaselines | None = None,
    alerts: FakeAlerts | None = None,
    clock: FakeClock | None = None,
    settings: BaselineSettings | None = None,
) -> tuple[ConditionService, FakeBaselines, FakeAlerts, FakeClock]:
    b = baselines if baselines is not None else FakeBaselines()
    a = alerts if alerts is not None else FakeAlerts()
    c = clock if clock is not None else FakeClock()
    svc = ConditionService(
        baselines=b,
        alerts=a,
        settings=settings if settings is not None else BaselineSettings(absolute_bps=1000.0),
        clock=c,
    )
    return svc, b, a, c


def _obs(
    bps: float = 100.0,
    *,
    iface: str = "eth0",
    proto: str = "tcp",
    packets: int = 10,
    flows: int = 2,
    start: datetime = NOW,
    sensor: str = "sensor-0",
) -> TrafficObservation:
    return TrafficObservation(
        observed_at=start,
        window_start=start,
        window_end=start + timedelta(seconds=5),
        interface=iface,
        protocol=proto,  # type: ignore[arg-type]
        packet_length_bytes=int(bps * 5),
        bytes_per_second=bps,
        packets=packets,
        flows=flows,
        pairs=[],
        sensor_id=sensor,
    )


def _partial_state(metric_key: str, samples: list[float], *, established: bool) -> dict:
    from sentinel.baseline.statistics import mean, sample_variance

    return {
        "metric_key": metric_key,
        "interval_seconds": 5,
        "samples": samples,
        "mean": mean(samples),
        "variance": sample_variance(samples),
        "established": established,
        "updated_at": NOW.isoformat(),
    }


# --- ST-M5-01/02: primeras 5 muestras y congelado --------------------------


def test_first_five_samples() -> None:
    svc, b, _, clock = _service()
    key = metric_key_for("bytes_per_second", "eth0", "tcp")
    for i in range(5):
        svc.on_accepted([_obs(bps=100.0 + i)])
        clock.advance(5)
    state = svc.states[key]
    assert state.established is True
    assert len(state.samples) == 5
    assert state.samples[0] == 100.0 and state.samples[-1] == 104.0
    assert b.rows[key]["established"] is True


def test_interim_stats() -> None:
    svc, _, _, _ = _service()
    key = metric_key_for("bytes_per_second", "eth0", "tcp")
    svc.on_accepted([_obs(bps=10.0)])
    state = svc.states[key]
    assert state.established is False
    assert state.mean == 10.0
    assert state.variance == 0.0  # n=1 ⇒ 0
    svc.on_accepted([_obs(bps=20.0)])
    state = svc.states[key]
    assert state.mean == 15.0
    assert state.variance == 50.0  # s² n-1: (225+225)/2... Σ(x-15)²=50 ⇒ /1=50
    assert len(state.samples) == 2


def test_freeze_after_five() -> None:
    svc, _, _, clock = _service()
    key = metric_key_for("bytes_per_second", "eth0", "tcp")
    for _ in range(5):
        svc.on_accepted([_obs(bps=100.0)])
        clock.advance(5)
    before = list(svc.states[key].samples)
    mean_before = svc.states[key].mean
    svc.on_accepted([_obs(bps=9999.0)])  # congelada ⇒ no-op
    state = svc.states[key]
    assert state.samples == before
    assert state.mean == mean_before
    assert 9999.0 not in state.samples


# --- ST-M5-03: supresión prioritaria --------------------------------------


def test_suppression_window() -> None:
    svc, _, a, clock = _service()
    key = metric_key_for("bytes_per_second", "eth0", "tcp")
    # 5 muestras EN la ventana (t=0..20s) — umbral absoluto configurado pero
    # la supresión tiene prioridad aunque el absoluto se supere (Q7 FD).
    for _ in range(4):
        svc.on_accepted([_obs(bps=50_000.0)])
        clock.advance(5)
    assert svc.is_suppressed(key, clock.now()) is True  # t=20 < 0+25
    svc.on_accepted([_obs(bps=50_000.0)])  # 5ª muestra, aún dentro de la ventana
    assert svc.states[key].established is True
    cond = svc.evaluate(
        TrafficWindow(
            window_start=clock.now(),
            window_end=clock.now() + timedelta(seconds=5),
            interface="eth0",
            protocol="tcp",
            bytes_per_second=50_000.0,
            packets=1,
            flows=1,
            sensor_id="sensor-0",
        )
    )
    assert cond.state == "baseline_establishing"
    assert cond.suppressed is True
    assert [r for r in a.rows.values() if r["metric_key"] == key] == []
    clock.advance(10)  # t=30 > 25 ⇒ la ventana cierra
    assert svc.is_suppressed(key, clock.now()) is False


def test_suppression_priority_over_absolute() -> None:
    svc, _, a, clock = _service()
    # Sin establecer (1 muestra) y fuera de la ventana: absolute disponible.
    svc.on_accepted([_obs(bps=50_000.0)])
    clock.advance(100)  # fuera de t_first+25s
    # Parcial sin 5 muestras ⇒ se re-suprime si t_first se movió… aquí no:
    # t_first sigue en NOW, ventana 25s ya pasó ⇒ evalúa con absolute.
    svc.on_accepted([_obs(bps=50_000.0)])
    rows = [r for r in a.rows.values() if r["state"] == "firing"]
    # 50_000 > 1000 (absolute) ⇒ firing (fallback absoluto pre-establecimiento)
    assert len(rows) == 1


def test_suppressed_even_if_established() -> None:
    # Establecida rápido (muestras en ms) pero DENTRO de la ventana de 25s:
    # la supresión sigue teniendo prioridad (FR-BASE-04, ventana temporal).
    svc, _, a, clock = _service()
    for _ in range(5):
        svc.on_accepted([_obs(bps=50_000.0)])  # sin avanzar reloj
    key = metric_key_for("bytes_per_second", "eth0", "tcp")
    assert svc.states[key].established is True
    assert svc.is_suppressed(key, clock.now()) is True
    svc.on_accepted([_obs(bps=50_000.0)])
    assert [r for r in a.rows.values() if r["state"] == "firing"] == []


# --- umbral: firing / equal / resolved / no_data --------------------------


def _established_service() -> tuple[ConditionService, FakeBaselines, FakeAlerts, FakeClock]:
    svc, b, a, clock = _service()
    for _ in range(5):
        svc.on_accepted([_obs(bps=100.0)])  # μ=100, s²=0 ⇒ umbral=100 (k*0)
        clock.advance(5)
    clock.advance(100)  # fuera de la ventana de supresión
    return svc, b, a, clock


def test_threshold_firing() -> None:
    svc, _, a, clock = _established_service()
    svc.on_accepted([_obs(bps=500.0)])  # 500 > 100+3*0 ⇒ firing
    rows = [r for r in a.rows.values() if r["state"] == "firing"]
    assert len(rows) == 1
    row = rows[0]
    assert row["rule"] == "R-01"
    assert row["measured_value"] == 500.0
    assert row["threshold"] == 100.0
    assert set(row["evidence"]) == {
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


def test_threshold_equal_no_fire() -> None:
    svc, _, a, _ = _established_service()
    svc.on_accepted([_obs(bps=100.0)])  # igual al umbral ⇒ estricto `>` ⇒ no fire
    assert [r for r in a.rows.values() if r["state"] == "firing"] == []
    assert list(a.rows.values()) == []  # sin fila previa ⇒ sin fila


def test_resolved_transition() -> None:
    svc, _, a, clock = _established_service()
    svc.on_accepted([_obs(bps=500.0)])  # fire
    firing = [r for r in a.rows.values() if r["state"] == "firing"]
    assert len(firing) == 1
    alert_id = firing[0]["alert_id"]
    svc.on_accepted([_obs(bps=10.0)])  # baja ⇒ resolved en la MISMA fila
    row = a.rows[alert_id]
    assert row["state"] == "resolved"
    assert row["resolved_at"] is not None
    assert svc.active_alerts == {}


def test_no_data_without_absolute() -> None:
    svc, _, a, clock = _service(settings=BaselineSettings())  # absolute=None
    svc.on_accepted([_obs(bps=100.0)])  # 1 muestra, no establecida
    clock.advance(100)  # fuera de la ventana
    svc.on_accepted([_obs(bps=100.0)])
    key = metric_key_for("bytes_per_second", "eth0", "tcp")
    assert key in svc.states
    assert list(a.rows.values()) == []  # sin umbral ⇒ no_data, sin alerta


# --- BR-U6-17: identidad estable y re-fire ---------------------------------


def test_alert_ids_stable() -> None:
    key = metric_key_for("bytes_per_second", "eth0", "tcp")
    cid = condition_id_for(key)
    assert cid == condition_id_for(key)
    aid1 = alert_id_for(cid, NOW.isoformat())
    assert aid1 == alert_id_for(cid, NOW.isoformat())
    assert aid1 != alert_id_for(cid, (NOW + timedelta(seconds=5)).isoformat())


def test_fire_resolve_refire_new_row() -> None:
    svc, _, a, clock = _established_service()
    svc.on_accepted([_obs(bps=500.0)])
    first = next(iter(a.rows.values()))
    svc.on_accepted([_obs(bps=10.0)])  # resolved (misma fila)
    clock.advance(5)
    svc.on_accepted([_obs(bps=900.0)])  # re-fire ⇒ fila NUEVA
    firing = [r for r in a.rows.values() if r["state"] == "firing"]
    assert len(firing) == 1
    assert firing[0]["alert_id"] != first["alert_id"]
    assert len(a.rows) == 2  # fila resolved + fila nueva


# --- contratos del hook (BR-U6-11/15) --------------------------------------


def test_non_traffic_ignored() -> None:
    svc, b, a, _ = _service()
    arp = ArpObservation(
        observed_at=NOW,
        interface="eth0",
        opcode=1,  # type: ignore[arg-type]
        psrc="10.0.0.1",
        pdst="10.0.0.2",
        hwsrc="aa:bb:cc:dd:ee:ff",
        hwdst="00:00:00:00:00:00",
    )
    disc = DiscoveryObservation(
        observed_at=NOW,
        ip="10.0.0.3",
        method="icmp",  # type: ignore[arg-type]
        sensor_id="sensor-0",
    )
    svc.on_accepted([arp, disc])
    assert svc.states == {}
    assert b.rows == {}
    assert a.rows == {}


def test_persistence_failure_degrades(caplog) -> None:  # type: ignore[no-untyped-def]
    import logging

    b, a = FakeBaselines(fail=True), FakeAlerts(fail=True)
    svc, _, _, _ = _service(baselines=b, alerts=a)
    with caplog.at_level(logging.WARNING):
        svc.on_accepted([_obs(bps=100.0)])  # jamás lanza (P1/BR-U6-15)
    # El estado en memoria sigue vivo (degradación, NFR-U6-AVAIL-01).
    key = metric_key_for("bytes_per_second", "eth0", "tcp")
    assert key in svc.states
    events = [getattr(r, "event", None) for r in caplog.records]
    assert "condition_persistence_failed" in events


def test_hydration_loads_states() -> None:
    key_est = metric_key_for("bytes_per_second", "eth0", "tcp")
    key_part = metric_key_for("packets", "eth0", "udp")
    b = FakeBaselines(
        rows=[
            _partial_state(key_est, [100.0] * 5, established=True),
            _partial_state(key_part, [1.0, 2.0], established=False),
        ]
    )
    cid = condition_id_for(key_est)
    a = FakeAlerts(
        rows=[
            {
                "alert_id": alert_id_for(cid, NOW.isoformat()),
                "condition_id": cid,
                "rule": "R-01",
                "metric_key": key_est,
                "state": "firing",
                "fired_at": NOW.isoformat(),
            }
        ]
    )
    svc, _, _, clock = _service(baselines=b, alerts=a)
    svc.hydrate()
    assert svc.states[key_est].established is True
    assert svc.states[key_part].t_first == clock.now()  # re-supresión (BR-U6-13)
    assert cid in svc.active_alerts


def test_hydration_failure_propagates_to_caller() -> None:
    # El wiring (P2) captura la excepción; hydrate() sí lanza.
    svc, _, _, _ = _service(baselines=FakeBaselines(fail=True))
    try:
        svc.hydrate()
    except RuntimeError:
        pass
    else:  # pragma: no cover
        raise AssertionError("hydrate must propagate for the wiring to catch")


def test_persisted_roundtrip() -> None:
    svc, b, a, _ = _service()
    svc.on_accepted([_obs(bps=100.0)])
    row = next(iter(b.rows.values()))
    # Columnas OQ-02 de la tabla baselines (BR-U6-16).
    assert set(row) >= {
        "metric_key",
        "interval_seconds",
        "samples",
        "mean",
        "variance",
        "established",
        "updated_at",
    }
    svc2, _, a2, _ = _established_service()
    svc2.on_accepted([_obs(bps=500.0)])
    alert = next(iter(a2.rows.values()))
    assert set(alert) >= {
        "alert_id",
        "condition_id",
        "rule",
        "metric_key",
        "asset_id",
        "state",
        "measured_value",
        "threshold",
        "fired_at",
        "resolved_at",
        "evidence",
        "updated_at",
    }


# --- R-04 indicador y colección -------------------------------------------


def test_collector_up_timeout() -> None:
    svc, _, _, clock = _service()
    assert svc.collector_up(None) == 0
    assert svc.collector_up(clock.now()) == 1
    assert svc.collector_up(clock.now() - timedelta(seconds=299)) == 1
    assert svc.collector_up(clock.now() - timedelta(seconds=301)) == 0


def test_metric_samples_includes_families() -> None:
    svc, _, _, _ = _established_service()
    svc.on_accepted([_obs(bps=500.0)])  # firing
    samples = svc.metric_samples()
    names = {n for n, _, _ in samples}
    assert {
        "sentinel_traffic_threshold_exceeded",
        "sentinel_baseline_status",
        "sentinel_baseline_established",
        "sentinel_collector_up",
    } <= names
    exceeded = next(
        v for n, lbl, v in samples if n == "sentinel_traffic_threshold_exceeded" and lbl
    )
    assert exceeded == 1.0
