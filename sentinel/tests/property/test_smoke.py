"""Property smoke tests — infraestructura PBT de foundation (EN-02 parcial).

Valida que la infraestructura hypothesis funciona en CI para las áreas
construidas de foundation. Las propiedades designadas (Nmap XML → U4,
normalización de flujos → U2, baseline → U6) viven en sus unidades.
"""

from __future__ import annotations

import re
from datetime import datetime

import pytest
from hypothesis import given
from pydantic import TypeAdapter, ValidationError

from sentinel.foundation.metrics_contract import metric_name
from sentinel.foundation.models import MACAddress, UTCDateTime
from sentinel.foundation.testing import mac_addresses, utc_datetimes

MAC_RE = re.compile(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$")

MAC_ADAPTER = TypeAdapter(MACAddress)
UTC_ADAPTER = TypeAdapter(UTCDateTime)


@given(mac_addresses)
def test_property_generated_macs_are_valid(value: str) -> None:
    assert MAC_RE.match(value), value
    assert MAC_ADAPTER.validate_python(value.upper()) == value


@given(utc_datetimes)
def test_property_generated_datetimes_are_valid(value: datetime) -> None:
    assert UTC_ADAPTER.validate_python(value) == value


@given(utc_datetimes)
def test_property_naive_datetimes_are_rejected(value: datetime) -> None:
    with pytest.raises(ValidationError):
        UTC_ADAPTER.validate_python(value.replace(tzinfo=None))


def test_property_metric_names_always_match_contract() -> None:
    for bare in ("flows_total", "a", "x_1_2", "0"):
        full = metric_name(bare)
        assert re.match(r"^sentinel_[a-z0-9_]+$", full)
