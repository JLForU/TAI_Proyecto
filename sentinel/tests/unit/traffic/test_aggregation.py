"""Agregación de ventanas (U5, BR-U5-12..18, D-U5-01/02)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from ipaddress import IPv4Address

from sentinel.traffic.aggregator import (
    MAX_PAIRS_PER_OBSERVATION,
    WindowAccumulator,
    to_observations,
    window_bounds,
    window_id_for,
)
from sentinel.traffic.source import IpPacket, protocol_from_number

NOW = datetime(2026, 11, 19, 12, 0, 3, tzinfo=UTC)  # a mitad de ventana (W=5)
SENSOR = "sensor-0"
W = 5


def _ip(
    at: datetime,
    *,
    proto: str = "tcp",
    src: str = "10.0.0.1",
    dst: str = "10.0.1.1",
    length: int = 100,
) -> IpPacket:
    return IpPacket(
        observed_at=at,
        interface="eth0",
        protocol=proto,  # type: ignore[arg-type]
        src_ip=IPv4Address(src),
        dst_ip=IPv4Address(dst),
        packet_length_bytes=length,
    )


def _accumulator() -> WindowAccumulator:
    start, end = window_bounds(NOW, W)
    return WindowAccumulator(window_start=start, window_end=end, interface="eth0")


def test_epoch_aligned() -> None:
    start, end = window_bounds(NOW, W)
    assert start == datetime(2026, 11, 19, 12, 0, 0, tzinfo=UTC)
    assert end == datetime(2026, 11, 19, 12, 0, 5, tzinfo=UTC)
    assert start.timestamp() % W == 0
    # cualquier instante de la ventana mapea al mismo inicio
    assert window_bounds(datetime(2026, 11, 19, 12, 0, 4, tzinfo=UTC), W)[0] == start


def test_empty_window_emitted() -> None:
    acc = _accumulator()
    observations = to_observations(acc, sensor_id=SENSOR)
    assert len(observations) == 1
    (zero,) = observations
    assert zero.protocol == "other"
    assert zero.packets == 0
    assert zero.bytes_per_second == 0.0
    assert zero.pairs == []
    assert zero.flows == 0
    assert zero.window_id is not None
    assert zero.observed_at == zero.window_end


def test_one_obs_per_protocol() -> None:
    acc = _accumulator()
    start, _ = window_bounds(NOW, W)
    acc.add(_ip(start, proto="tcp"))
    acc.add(_ip(start + timedelta(seconds=1), proto="tcp"))
    acc.add(_ip(start + timedelta(seconds=2), proto="udp"))
    observations = to_observations(acc, sensor_id=SENSOR)
    assert {o.protocol for o in observations} == {"tcp", "udp"}
    by_protocol = {o.protocol: o for o in observations}
    assert by_protocol["tcp"].packets == 2
    assert by_protocol["tcp"].packet_length_bytes == 200
    assert by_protocol["tcp"].bytes_per_second == 200 / W
    assert by_protocol["udp"].packets == 1


def test_five_second_windows() -> None:
    """ST-M3-02 AC1: 25 s @ 5 s ⇒ 5 ventanas."""
    base = datetime(2026, 11, 19, 12, 0, 0, tzinfo=UTC)
    starts = {window_bounds(base + timedelta(seconds=second), W)[0] for second in range(25)}
    assert len(starts) == 5


def test_pairs_cap() -> None:
    acc = _accumulator()
    start, _ = window_bounds(NOW, W)
    for i in range(150):
        acc.add(_ip(start, src=f"10.0.{i // 256}.{i % 256 + 1}", dst="10.0.9.1"))
    (observation,) = to_observations(acc, sensor_id=SENSOR)
    assert len(observation.pairs) <= MAX_PAIRS_PER_OBSERVATION
    assert len(observation.pairs) == 100
    assert observation.flows == 150
    assert observation.flows >= len(observation.pairs)


def test_pairs_order_deterministic() -> None:
    acc = _accumulator()
    start, _ = window_bounds(NOW, W)
    for _ in range(5):
        acc.add(_ip(start, src="10.0.0.2", dst="10.0.1.1"))
    for _ in range(3):
        acc.add(_ip(start, src="10.0.0.1", dst="10.0.1.1"))
    acc.add(_ip(start, src="10.0.0.3", dst="10.0.1.1"))
    (observation,) = to_observations(acc, sensor_id=SENSOR)
    # packets desc: 5, 3, 1
    assert [str(p.src_ip) for p in observation.pairs] == ["10.0.0.2", "10.0.0.1", "10.0.0.3"]


def test_window_id_stable() -> None:
    start, _ = window_bounds(NOW, W)
    identifier = window_id_for(SENSOR, start, "eth0", "tcp")
    assert identifier == window_id_for(SENSOR, start, "eth0", "tcp")
    assert identifier != window_id_for(SENSOR, start, "eth0", "udp")
    assert identifier != window_id_for("sensor-1", start, "eth0", "tcp")

    acc = _accumulator()
    acc.add(_ip(start, proto="tcp"))
    (observation,) = to_observations(acc, sensor_id=SENSOR)
    assert observation.window_id == identifier


def test_protocol_mapping() -> None:
    assert protocol_from_number(6) == "tcp"
    assert protocol_from_number(17) == "udp"
    assert protocol_from_number(1) == "icmp"
    assert protocol_from_number(99) == "other"
    assert protocol_from_number(58) == "other"
