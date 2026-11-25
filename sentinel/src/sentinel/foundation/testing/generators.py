"""Generadores hypothesis comunes para property-based testing (EN-02, BR-28).

Reutilizados por ``tests/property/`` de U2 (normalización de flujos),
U4 (Nmap XML) y U6 (baseline). Foundation no define propiedades de esas
áreas: solo aporta las estrategias.
"""

from __future__ import annotations

import ipaddress
from datetime import UTC, datetime

from hypothesis import strategies as st

from sentinel.foundation.models import (
    MAX_BATCH_ITEMS,
    MAX_STRING_LEN,
)

__all__ = [
    "ipv4_addresses",
    "ipv6_addresses",
    "mac_addresses",
    "bounded_strings",
    "utc_datetimes",
    "uuids",
    "batches_of",
]


def _mac_from_int(value: int) -> str:
    raw = value.to_bytes(6, "big")
    return ":".join(f"{b:02x}" for b in raw)


ipv4_addresses = st.builds(ipaddress.IPv4Address, st.integers(min_value=0, max_value=2**32 - 1))

ipv6_addresses = st.builds(ipaddress.IPv6Address, st.integers(min_value=0, max_value=2**128 - 1))

mac_addresses = st.integers(min_value=0, max_value=2**48 - 1).map(_mac_from_int)

bounded_strings = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=126),
    min_size=0,
    max_size=MAX_STRING_LEN,
)

utc_datetimes = st.datetimes(
    min_value=datetime(2000, 1, 1, tzinfo=UTC),
    max_value=datetime(2100, 1, 1, tzinfo=UTC),
    timezones=st.just(UTC),
)

uuids = st.uuids()

batches_of = st.lists(
    st.integers(min_value=0, max_value=MAX_BATCH_ITEMS - 1),
    min_size=0,
    max_size=10,
)
