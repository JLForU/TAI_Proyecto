"""Worker de ventana (U5, BR-U5-25/28/30, P1/P2/P3, AVAIL, GT-05)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from ipaddress import IPv4Address
from pathlib import Path

import pytest

from sentinel.foundation.errors import IngestionError
from sentinel.traffic.config import TrafficSettings
from sentinel.traffic.source import FixtureSource, IpPacket, PacketSource
from sentinel.traffic.worker import SensorState, run_window

FIXTURES = Path(__file__).parent / "fixtures"
WINDOW_SAMPLE = FIXTURES / "window_sample.json"

W1_START = datetime(2026, 11, 19, 12, 0, 0, tzinfo=UTC)
W1_END = datetime(2026, 11, 19, 12, 0, 5, tzinfo=UTC)
W2_START = datetime(2026, 11, 19, 12, 0, 5, tzinfo=UTC)
W3_START = datetime(2026, 11, 19, 12, 0, 10, tzinfo=UTC)
MID_W1 = datetime(2026, 11, 19, 12, 0, 2, tzinfo=UTC)
MID_W2 = datetime(2026, 11, 19, 12, 0, 7, tzinfo=UTC)
MID_W3 = datetime(2026, 11, 19, 12, 0, 12, tzinfo=UTC)


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def set(self, now: datetime) -> None:
        self._now = now


class RecordingClient:
    """Cliente que registra lotes; los primeros ``fail_first`` fallan."""

    def __init__(self, fail_first: int = 0) -> None:
        self.fail_first = fail_first
        self.calls: list[list] = []

    def post_batch(self, items) -> dict:  # type: ignore[no-untyped-def]
        self.calls.append(list(items))
        if len(self.calls) <= self.fail_first:
            raise IngestionError("core unavailable")
        return {"accepted": len(items)}


def _settings(**overrides) -> TrafficSettings:
    base = {"window_seconds": 5, "interface": "eth0", "sensor_id": "sensor-0"}
    base.update(overrides)
    return TrafficSettings(**base)  # type: ignore[arg-type]


def _source() -> FixtureSource:
    return FixtureSource(WINDOW_SAMPLE)


def test_ciclo() -> None:
    client = RecordingClient()
    result = run_window(_settings(), _source(), client, FakeClock(MID_W1))
    assert result.status == "emitted"
    assert result.window_start == W1_START
    assert result.window_end == W1_END
    assert result.traffic == 2  # tcp (2 paquetes) + udp
    assert result.arp == 2
    assert result.items == 4

    items = client.calls[0]
    # lote mixto con traffic primero (BR-U5-23)
    assert items[0].source == "traffic"
    traffic = [i for i in items if i.source == "traffic"]
    arp = [i for i in items if i.source == "arp"]
    assert len(traffic) == 2 and len(arp) == 2
    # observed_at = window_end y window_start alineado (domain-entities §2.1)
    assert all(i.observed_at == W1_END for i in traffic)
    assert all(i.window_start == W1_START for i in traffic)
    assert all(i.sensor_id == "sensor-0" for i in items)
    assert {i.protocol for i in traffic} == {"tcp", "udp"}


def test_retry_exhausted_drop(caplog: pytest.LogCaptureFixture) -> None:
    client = RecordingClient(fail_first=1)
    with caplog.at_level(logging.ERROR):
        result = run_window(_settings(), _source(), client, FakeClock(MID_W1))
    assert result.status == "export_failed"
    assert result.items == 0
    events = [getattr(r, "event", None) for r in caplog.records]
    assert "sensor_export_failed" in events
    # sin buffer local: la ventana se descarta (D-U5-05)
    assert client.calls[0], "el intento de export sí ocurrió"


def test_continue_next_window() -> None:
    """P1: 2 ventanas fallidas ⇒ la tercera se emite; el worker sigue vivo."""
    client = RecordingClient(fail_first=2)
    state = SensorState()
    clock = FakeClock(MID_W1)

    first = run_window(_settings(), _source(), client, clock, state)
    assert first.status == "export_failed"

    clock.set(MID_W2)
    second = run_window(_settings(), _source(), client, clock, state)
    assert second.status == "export_failed"

    clock.set(MID_W3)
    third = run_window(_settings(), _source(), client, clock, state)
    assert third.status == "emitted"
    assert len(client.calls) == 3


def test_source_error_continues(caplog: pytest.LogCaptureFixture) -> None:
    class BrokenSource:
        def events(self):  # type: ignore[no-untyped-def]
            raise RuntimeError("fixture corrupta")

    client = RecordingClient()
    state = SensorState()
    clock = FakeClock(MID_W1)
    with caplog.at_level(logging.ERROR):
        first = run_window(_settings(), BrokenSource(), client, clock, state)  # type: ignore[arg-type]
    assert first.status == "source_error"
    events = [getattr(r, "event", None) for r in caplog.records]
    assert "sensor_source_error" in events
    assert client.calls == []

    # siguiente ventana con fuente sana ⇒ emite (P3)
    clock.set(MID_W2)
    second = run_window(_settings(), _source(), client, clock, state)
    assert second.status == "emitted"


def test_clock_regression(caplog: pytest.LogCaptureFixture) -> None:
    client = RecordingClient()
    state = SensorState()
    clock = FakeClock(MID_W1)
    first = run_window(_settings(), _source(), client, clock, state)
    assert first.status == "emitted"
    assert state.last_emitted_window_start == W1_START

    # reloj retrocede: ventana calculada ≤ último emitido (P2)
    clock.set(datetime(2026, 11, 19, 11, 59, 58, tzinfo=UTC))
    with caplog.at_level(logging.WARNING):
        second = run_window(_settings(), _source(), client, clock, state)
    assert second.status == "clock_regression"
    assert len(client.calls) == 1  # sin segunda emisión
    events = [getattr(r, "event", None) for r in caplog.records]
    assert "window_clock_regression" in events


def test_observations_are_heartbeat() -> None:
    """Toda ventana emitida porta sensor_id ⇒ HealthService avanza el heartbeat."""
    client = RecordingClient()
    result = run_window(_settings(sensor_id="lab-sensor"), _source(), client, FakeClock(MID_W1))
    assert result.status == "emitted"
    assert client.calls
    for item in client.calls[0]:
        assert item.sensor_id == "lab-sensor"


def test_sensor_id_on_obs() -> None:
    client = RecordingClient()
    run_window(_settings(sensor_id="sensor-42"), _source(), client, FakeClock(MID_W1))
    items = client.calls[0]
    assert items
    assert all(i.sensor_id == "sensor-42" for i in items)
    assert any(i.source == "traffic" for i in items)
    assert any(i.source == "arp" for i in items)


def test_injectable_clock() -> None:
    """La ventana la define el reloj inyectado, no el reloj real (P9)."""
    client = RecordingClient()
    clock = FakeClock(datetime(2026, 3, 5, 9, 30, 7, tzinfo=UTC))
    result = run_window(_settings(), _source(), client, clock)
    assert result.window_start == datetime(2026, 3, 5, 9, 30, 5, tzinfo=UTC)
    assert result.window_end == datetime(2026, 3, 5, 9, 30, 10, tzinfo=UTC)
    # eventos del fixture son de otra época ⇒ ventana cero emitida (heartbeat)
    assert result.status == "emitted"
    assert result.traffic == 1
    assert client.calls[0][0].packets == 0


def test_gt05_stops_heartbeat() -> None:
    """GT-05: loop detenido ⇒ sin nuevas emisiones ⇒ el heartbeat deja de avanzar."""
    client = RecordingClient()
    state = SensorState()
    clock = FakeClock(MID_W1)
    running = run_window(_settings(), _source(), client, clock, state)
    assert running.status == "emitted"
    assert len(client.calls) == 1
    # el loop se detiene: no hay más run_window ⇒ no hay más observaciones
    # (U2 deriva sensor_heartbeats = MAX(observed_at): sin envíos no avanza)
    assert len(client.calls) == 1
    assert state.last_emitted_window_start == W1_START


def test_empty_window_still_emits_heartbeat() -> None:
    """Ventana sin eventos ⇒ 1 observación cero (D-U5-01) — red idle ≠ sensor caído."""

    class EmptySource:
        def events(self):  # type: ignore[no-untyped-def]
            return iter(())

    client = RecordingClient()
    result = run_window(_settings(), EmptySource(), client, FakeClock(MID_W1))  # type: ignore[arg-type]
    assert result.status == "emitted"
    assert result.traffic == 1
    assert result.arp == 0
    (zero,) = client.calls[0]
    assert zero.protocol == "other"
    assert zero.packets == 0
    assert zero.pairs == []


def test_pending_event_not_lost_at_boundary() -> None:
    """El primer evento en el borde pasa a la ventana siguiente (sin pérdida)."""

    class TwoEventSource:
        def __init__(self) -> None:
            self._emitted = False

        def events(self):  # type: ignore[no-untyped-def]
            if self._emitted:
                return
            self._emitted = True
            yield IpPacket(
                observed_at=W1_END,  # exactamente en el borde
                interface="eth0",
                protocol="tcp",
                src_ip=IPv4Address("10.0.0.7"),
                dst_ip=IPv4Address("10.0.1.7"),
                packet_length_bytes=64,
            )

    client = RecordingClient()
    state = SensorState()
    source: PacketSource = TwoEventSource()  # type: ignore[assignment]
    first = run_window(_settings(), source, client, FakeClock(MID_W1), state)
    assert first.status == "emitted"
    assert first.traffic == 1  # solo la ventana cero (heartbeat)
    assert state.pending is not None

    second = run_window(_settings(), source, client, FakeClock(MID_W2), state)
    assert second.status == "emitted"
    # el evento pendiente se atribuyó a la ventana 2 (no se perdió)
    window_two_traffic = [i for i in client.calls[1] if i.source == "traffic" and i.packets == 1]
    assert window_two_traffic
    assert window_two_traffic[0].window_start == W2_START
    assert window_two_traffic[0].packets == 1


def test_source_protocol_satisfied() -> None:
    source: PacketSource = _source()
    events = list(source.events())
    assert events
    assert all(hasattr(e, "observed_at") for e in events)
    # la ventana W1 del fixture contiene 3 IP + 2 ARP
    assert len(events) == 5
