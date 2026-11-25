"""Fuente de paquetes (U5, BR-U5-06..11, GT-04): determinismo, fixtures, IPv4."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from itertools import islice
from pathlib import Path

from sentinel.traffic.source import (
    FixtureSource,
    IpPacket,
    SimulatedSource,
)

START = datetime(2026, 11, 19, 12, 0, 0, tzinfo=UTC)


def test_deterministic_seed() -> None:
    first = list(
        islice(SimulatedSource(seed=42, rate=10.0, interface="eth0", start_at=START).events(), 50)
    )
    second = list(
        islice(SimulatedSource(seed=42, rate=10.0, interface="eth0", start_at=START).events(), 50)
    )
    assert first == second
    other = list(
        islice(SimulatedSource(seed=7, rate=10.0, interface="eth0", start_at=START).events(), 50)
    )
    assert first != other


def test_protocol_fallback() -> None:
    events = list(
        islice(SimulatedSource(seed=0, rate=100.0, interface="eth0", start_at=START).events(), 30)
    )
    ip_protocols = {e.protocol for e in events if isinstance(e, IpPacket)}
    assert ip_protocols == {"tcp", "udp", "icmp", "other"}


def test_ipv6_skipped(tmp_path: Path) -> None:
    path = tmp_path / "mixed.json"
    path.write_text(
        json.dumps(
            [
                {
                    "type": "ip",
                    "observed_at": START.isoformat(),
                    "interface": "eth0",
                    "protocol": "tcp",
                    "src_ip": "10.0.0.1",
                    "dst_ip": "10.0.1.1",
                    "packet_length_bytes": 64,
                    "ip_version": 4,
                },
                {
                    "type": "ip",
                    "observed_at": (START + timedelta(seconds=1)).isoformat(),
                    "interface": "eth0",
                    "protocol": "tcp",
                    "src_ip": "2001:db8::1",
                    "dst_ip": "2001:db8::2",
                    "packet_length_bytes": 64,
                    "ip_version": 6,
                },
            ]
        ),
        encoding="utf-8",
    )
    events = list(FixtureSource(path).events())
    assert len(events) == 1
    ip = events[0]
    assert isinstance(ip, IpPacket)
    assert str(ip.src_ip) == "10.0.0.1"


def test_high_rate_windows() -> None:
    """GT-04: SIM_RATE alto ⇒ más eventos en la misma ventana (sin red ni sleep)."""
    horizon = START + timedelta(seconds=5)

    def events_in_window(rate: float) -> int:
        source = SimulatedSource(seed=42, rate=rate, interface="eth0", start_at=START)
        return sum(1 for e in islice(source.events(), 5000) if e.observed_at < horizon)

    assert events_in_window(500.0) > events_in_window(5.0) * 10


def test_fixture_replay(tmp_path: Path) -> None:
    path = tmp_path / "replay.json"
    path.write_text(
        json.dumps(
            [
                {
                    "type": "ip",
                    "observed_at": START.isoformat(),
                    "interface": "eth1",
                    "ip_protocol": 17,
                    "src_ip": "10.0.0.5",
                    "dst_ip": "10.0.1.5",
                    "packet_length_bytes": 128,
                },
                {
                    "type": "arp",
                    "observed_at": (START + timedelta(seconds=1)).isoformat(),
                    "interface": "eth1",
                    "opcode": 2,
                    "psrc": "10.0.0.9",
                    "pdst": "10.0.0.1",
                    "hwsrc": "aa:bb:cc:dd:ee:09",
                    "hwdst": "aa:bb:cc:dd:ee:01",
                },
            ]
        ),
        encoding="utf-8",
    )
    source = FixtureSource(path)
    first = list(source.events())
    second = list(source.events())  # iterador fresco por llamada
    assert first == second
    ip, arp = first
    assert isinstance(ip, IpPacket)
    assert ip.protocol == "udp"  # ip_protocol 17 ⇒ udp (BR-U5-18)
    assert ip.interface == "eth1"
    assert arp.opcode == 2  # type: ignore[union-attr]
