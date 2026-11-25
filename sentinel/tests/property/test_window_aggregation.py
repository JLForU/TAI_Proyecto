"""Property tests de la ventana (PB-U5-01..03, MNT-03, BR-U5-24/25/26).

- PB-U5-01 partición: las ventanas son contiguas y cubren todos los paquetes.
- PB-U5-02 conservación: bytes/paquetes de entrada == suma de observaciones.
- PB-U5-03 determinismo: misma entrada ⇒ mismas observaciones (eq pydantic).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from ipaddress import IPv4Address

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from sentinel.traffic.aggregator import (
    WindowAccumulator,
    to_observations,
    window_bounds,
)
from sentinel.traffic.source import IpPacket

_MIN = datetime(2026, 1, 1, tzinfo=UTC)
_MAX = datetime(2027, 1, 1, tzinfo=UTC)
_IFACE = "eth0"
_SENSOR = "sensor-pbt"

_timestamps = st.datetimes(min_value=_MIN, max_value=_MAX, timezones=st.just(UTC))
_protocols = st.sampled_from(["tcp", "udp", "icmp", "other"])
_lengths = st.integers(min_value=0, max_value=65535)
_ips = st.integers(min_value=0, max_value=2**32 - 1).map(IPv4Address)
_window_seconds = st.sampled_from([1, 5, 10, 30, 60])


@st.composite
def packet_sets(draw: st.DrawFn) -> tuple[list[IpPacket], int]:
    """Lote arbitrario de paquetes + el tamaño de ventana elegido."""
    window_seconds = draw(_window_seconds)
    n = draw(st.integers(min_value=0, max_value=60))
    packets = [
        IpPacket(
            observed_at=draw(_timestamps),
            interface=_IFACE,
            protocol=draw(_protocols),
            src_ip=draw(_ips),
            dst_ip=draw(_ips),
            packet_length_bytes=draw(_lengths),
        )
        for _ in range(n)
    ]
    return packets, window_seconds


def _group(packets: list[IpPacket], window_seconds: int) -> dict[datetime, WindowAccumulator]:
    grouped: dict[datetime, WindowAccumulator] = {}
    for packet in packets:
        start, end = window_bounds(packet.observed_at, window_seconds)
        acc = grouped.get(start)
        if acc is None:
            acc = WindowAccumulator(window_start=start, window_end=end, interface=_IFACE)
            grouped[start] = acc
        acc.add(packet)
    return grouped


# --- PB-U5-01: partición (disjunta + alineada) -------------------------------


@given(packet_sets())
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_windows_are_contiguous_and_cover_every_packet(data) -> None:  # type: ignore[no-untyped-def]
    packets, window_seconds = data
    grouped = _group(packets, window_seconds)
    # cobertura: ningún paquete se pierde al agrupar
    assert sum(acc.total_packets for acc in grouped.values()) == len(packets)
    starts = sorted(grouped)
    for start in starts:
        acc = grouped[start]
        # alineación epoch y longitud exacta de ventana tumbling (BR-U5-12)
        assert int(start.timestamp()) % window_seconds == 0
        assert acc.window_end - acc.window_start == timedelta(seconds=window_seconds)
    # disjunta: las ventanas ocupadas nunca se solapan
    for prev, cur in zip(starts, starts[1:], strict=False):
        assert cur >= prev + timedelta(seconds=window_seconds)


# --- PB-U5-02: conservación de bytes ----------------------------------------


@given(packet_sets())
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_bytes_are_conserved(data) -> None:  # type: ignore[no-untyped-def]
    packets, window_seconds = data
    grouped = _group(packets, window_seconds)
    total_bytes_in = sum(p.packet_length_bytes for p in packets)
    total_bytes_out = 0
    total_packets_out = 0
    for acc in grouped.values():
        total_bytes_out += sum(acc.bytes_by_protocol.values())
        total_packets_out += acc.total_packets
        obs_list = to_observations(acc, sensor_id=_SENSOR)
        if acc.total_packets > 0:
            # con tráfico: 1 obs por protocolo, todas con ≥1 paquete
            assert obs_list
            assert all(obs.packets >= 1 for obs in obs_list)
        else:
            # ventana cero: exactamente 1 heartbeat factual (D-U5-01)
            assert len(obs_list) == 1
            assert obs_list[0].packets == 0
    assert total_bytes_out == total_bytes_in
    assert total_packets_out == len(packets)


# --- PB-U5-03: determinismo --------------------------------------------------


@given(packet_sets())
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_projection_is_deterministic(data) -> None:  # type: ignore[no-untyped-def]
    packets, window_seconds = data
    acc_a = WindowAccumulator(
        window_start=datetime(2026, 6, 1, tzinfo=UTC),
        window_end=datetime(2026, 6, 1, 0, 0, 5, tzinfo=UTC),
        interface=_IFACE,
    )
    acc_b = WindowAccumulator(
        window_start=acc_a.window_start, window_end=acc_a.window_end, interface=_IFACE
    )
    for packet in packets:
        acc_a.add(packet)
        acc_b.add(packet)
    first = to_observations(acc_a, sensor_id=_SENSOR)
    second = to_observations(acc_b, sensor_id=_SENSOR)
    assert first == second  # igualdad pydantic (MNT-03)
    # reglas de borde invariadas: acotación y orden estable (BR-U5-16)
    for obs in first:
        assert len(obs.pairs) <= 100
        assert obs.window_start == acc_a.window_start
        assert obs.sensor_id == _SENSOR
