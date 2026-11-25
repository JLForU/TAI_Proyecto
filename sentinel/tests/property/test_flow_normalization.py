"""Property tests de normalización de flujos (PB-U2-01..03, EN-02, MNT-04).

- PB-U2-01: ``normalize(normalize(x)) == normalize(x)`` (idempotente).
- PB-U2-02: mismo hecho en distinto formato ⇒ mismo ``dedup_key``/``event_id``.
- PB-U2-03: cualquier lote ⇒ ``accepted + deduplicated == len(items)``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from sentinel.core.db.database import Database
from sentinel.core.ingestion.dedup import dedup_key, event_id_for
from sentinel.core.ingestion.service import IngestionService
from sentinel.foundation.models import Batch, DiscoveryObservation

# --- estrategias locales -----------------------------------------------------

_FACTS = [
    ("10.0.0.1", "aa:bb:cc:dd:ee:01", "host-a"),
    ("192.168.1.10", "11:22:33:44:55:66", "host-b"),
    ("172.16.0.9", "ff:ee:dd:cc:bb:aa", "host-c"),
]

_base_times = st.datetimes(
    min_value=datetime(2020, 1, 1, tzinfo=UTC),
    max_value=datetime(2030, 1, 1, tzinfo=UTC),
    timezones=st.just(UTC),
)
_offsets = st.integers(min_value=-12, max_value=14).map(lambda h: timezone(timedelta(hours=h)))


@st.composite
def discovery_variants(draw: st.DrawFn) -> tuple[dict, dict]:
    """Par (formato_canonico, formato_alternativo) del mismo hecho."""
    ip, mac, hostname = draw(st.sampled_from(_FACTS))
    when = draw(_base_times)
    tz = draw(_offsets)
    alt_when = when.astimezone(tz)
    upper = draw(st.booleans())
    mac_a = mac.lower()
    mac_b = mac.upper() if upper else mac
    method = draw(st.sampled_from(["arp", "tcp", "icmp"]))
    common = {"source": "discovery", "ip": ip, "hostname": hostname, "method": method}
    a = {**common, "mac": mac_a, "observed_at": when}
    b = {**common, "mac": mac_b, "observed_at": alt_when}
    return a, b


# --- PB-U2-01: idempotencia de normalize ------------------------------------


@given(discovery_variants())
@settings(max_examples=50, deadline=None)
def test_normalize_is_idempotent(pair: tuple[dict, dict]) -> None:
    a, _b = pair
    first = DiscoveryObservation(**a)
    second = DiscoveryObservation(**first.model_dump())
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    # y la normalización es estable en MAC y UTC
    assert first.mac == first.mac.lower()
    assert first.observed_at.tzinfo is not None
    assert first.observed_at.utcoffset() == timedelta(0)


# --- PB-U2-02: identidad estable en distinto formato ------------------------


@given(discovery_variants())
@settings(max_examples=50, deadline=None)
def test_same_fact_same_dedup_key(pair: tuple[dict, dict]) -> None:
    a, b = pair
    key_a = dedup_key(DiscoveryObservation(**a))
    key_b = dedup_key(DiscoveryObservation(**b))
    assert key_a == key_b


@given(_base_times, st.sampled_from(_FACTS))
@settings(max_examples=50, deadline=None)
def test_event_id_stable_for_normalized_content(when: datetime, fact: tuple[str, str, str]) -> None:
    """Normalizar a UTC-ISO antes de hashear ⇒ mismo event_id (PB-U2-02)."""
    ip, _mac, _host = fact
    alt = when.astimezone(timezone(timedelta(hours=5)))
    occurred_a = when.astimezone(UTC).isoformat()
    occurred_b = alt.astimezone(UTC).isoformat()
    details_a = {"ip": ip, "ts": occurred_a}
    details_b = {"ip": ip, "ts": occurred_b}
    id_a = event_id_for("asset_first_seen", None, occurred_a, details_a)
    id_b = event_id_for("asset_first_seen", None, occurred_b, details_b)
    assert id_a == id_b
    # sin normalizar (formato distinto) el hash cambia: por eso se normaliza antes
    assert (
        event_id_for("asset_first_seen", None, alt.isoformat(), {"ip": ip, "ts": alt.isoformat()})
        != id_a
    )


# --- PB-U2-03: conservación de contadores -----------------------------------


@pytest.fixture()
def db(tmp_path) -> Database:  # type: ignore[no-untyped-def]
    database = Database(str(tmp_path / "prop.db"))
    database.startup_checks()
    yield database
    database.close()


@st.composite
def random_batches(draw: st.DrawFn) -> list[dict]:
    size = draw(st.integers(min_value=0, max_value=15))
    return [draw(st.sampled_from(_FACTS)) for _ in range(size)]


def _item(fact: tuple[str, str, str], i: int) -> dict:
    ip, mac, hostname = fact
    return {
        "source": "discovery",
        "observed_at": datetime(2026, 1, 1, 12, 0, i % 60, tzinfo=UTC),
        "ip": ip,
        "mac": mac,
        "hostname": hostname,
        "method": "arp",
    }


# La BD (function-scoped) no se reinicia entre ejemplos a propósito: la
# propiedad accepted+deduplicated==len se cumple con datos acumulados.
@settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(random_batches())
def test_counters_are_conserved(db: Database, facts: list[tuple[str, str, str]]) -> None:
    items = [_item(f, i) for i, f in enumerate(facts)]
    batch = Batch(items=items)  # valida con Pydantic U1
    result = IngestionService(db, missing_cycles=3).process(batch)
    assert result.accepted + result.deduplicated == len(items)
