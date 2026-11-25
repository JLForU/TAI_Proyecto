"""Campos mínimos de tráfico (U5, BR-U5-08, ST-M3-01): sin payload/MAC/puerto."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from sentinel.foundation.models import ArpObservation, FlowPair, TrafficObservation

NOW = datetime(2026, 11, 19, 12, 0, 0, tzinfo=UTC)

#: Conjunto exacto de campos de la observación de tráfico (FR-TRAF-03).
EXPECTED_TRAFFIC_FIELDS = {
    "observed_at",
    "sensor_id",
    "source",
    "window_start",
    "window_end",
    "interface",
    "protocol",
    "packet_length_bytes",
    "bytes_per_second",
    "packets",
    "flows",
    "pairs",
    "window_id",
}


def _traffic_kwargs() -> dict:
    return {
        "observed_at": NOW + timedelta(seconds=5),
        "window_start": NOW,
        "window_end": NOW + timedelta(seconds=5),
        "interface": "eth0",
        "protocol": "tcp",
        "packet_length_bytes": 64,
        "bytes_per_second": 12.8,
        "packets": 1,
        "flows": 1,
        "pairs": [FlowPair(src_ip="10.0.0.1", dst_ip="10.0.1.1")],
    }


def test_minimal_fields() -> None:
    assert set(TrafficObservation.model_fields) == EXPECTED_TRAFFIC_FIELDS
    forbidden = {"payload", "mac", "src_port", "dst_port", "port"}
    assert not forbidden & set(TrafficObservation.model_fields)
    observation = TrafficObservation(**_traffic_kwargs())
    assert observation.model_dump().keys() == EXPECTED_TRAFFIC_FIELDS


def test_no_payload() -> None:
    with pytest.raises(ValidationError):
        TrafficObservation(**_traffic_kwargs(), payload=b"\x00\x01\x02")
    with pytest.raises(ValidationError):
        ArpObservation(
            observed_at=NOW,
            interface="eth0",
            opcode=1,
            psrc="10.0.0.1",
            pdst="10.0.0.99",
            hwsrc="aa:bb:cc:dd:ee:01",
            hwdst="ff:ff:ff:ff:ff:ff",
            payload="secret",
        )
