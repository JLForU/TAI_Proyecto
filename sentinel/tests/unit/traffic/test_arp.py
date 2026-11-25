"""Dominio ARP (U5, BR-U5-09): request y reply → ArpObservation U1."""

from __future__ import annotations

from datetime import UTC, datetime
from ipaddress import IPv4Address

from sentinel.foundation.models import ArpObservation
from sentinel.traffic.arp import to_arp_observations
from sentinel.traffic.source import ArpPacket

NOW = datetime(2026, 11, 19, 12, 0, 1, tzinfo=UTC)


def _request() -> ArpPacket:
    return ArpPacket(
        observed_at=NOW,
        interface="eth0",
        opcode=1,
        psrc=IPv4Address("10.0.0.1"),
        pdst=IPv4Address("10.0.0.99"),
        hwsrc="aa:bb:cc:dd:ee:01",
        hwdst="ff:ff:ff:ff:ff:ff",
    )


def _reply() -> ArpPacket:
    return ArpPacket(
        observed_at=NOW,
        interface="eth0",
        opcode=2,
        psrc=IPv4Address("10.0.0.99"),
        pdst=IPv4Address("10.0.0.1"),
        hwsrc="aa:bb:cc:dd:ee:99",
        hwdst="aa:bb:cc:dd:ee:01",
    )


def test_request_and_reply() -> None:
    observations = to_arp_observations([_request(), _reply()], sensor_id="sensor-0")
    assert len(observations) == 2
    request, reply = observations
    assert request.opcode == 1
    assert reply.opcode == 2
    assert request.source == "arp"
    assert request.sensor_id == "sensor-0"
    assert request.interface == "eth0"
    assert request.hwsrc == "aa:bb:cc:dd:ee:01"
    assert request.psrc == IPv4Address("10.0.0.1")
    assert request.pdst == IPv4Address("10.0.0.99")
    assert reply.hwsrc == "aa:bb:cc:dd:ee:99"
    assert reply.hwdst == "aa:bb:cc:dd:ee:01"
    # sin campo de tasa en el contrato (D-U5-08)
    assert "rate" not in ArpObservation.model_fields


def test_empty_input() -> None:
    assert to_arp_observations([], sensor_id="sensor-0") == []
