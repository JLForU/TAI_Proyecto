"""Tests de los generadores hypothesis de foundation.testing (EN-02 infra)."""

from __future__ import annotations

import re
from datetime import UTC
from ipaddress import IPv4Address, IPv6Address
from uuid import UUID

from hypothesis import given

from sentinel.foundation.testing import (
    bounded_strings,
    ipv4_addresses,
    ipv6_addresses,
    mac_addresses,
    utc_datetimes,
    uuids,
)

MAC_RE = re.compile(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$")


@given(mac_addresses)
def test_mac_generator_valid(value: str) -> None:
    assert MAC_RE.match(value)


@given(ipv4_addresses)
def test_ipv4_generator_valid(value: IPv4Address) -> None:
    assert isinstance(value, IPv4Address)


@given(ipv6_addresses)
def test_ipv6_generator_valid(value: IPv6Address) -> None:
    assert isinstance(value, IPv6Address)


@given(utc_datetimes)
def test_datetime_generator_utc_aware(value) -> None:  # type: ignore[no-untyped-def]
    assert value.tzinfo is not None
    assert value.utcoffset() == UTC.utcoffset(None)


@given(bounded_strings)
def test_bounded_string_respects_max_len(value: str) -> None:
    assert len(value) <= 255


@given(uuids)
def test_uuid_generator_valid(value: UUID) -> None:
    assert isinstance(value, UUID)
