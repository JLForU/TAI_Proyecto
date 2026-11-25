"""Tests de entidades de dominio (BR-13..BR-18, P2/P7)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta, timezone
from ipaddress import IPv4Address

import pytest
from pydantic import ValidationError

from sentinel.foundation.events import EventType
from sentinel.foundation.models import (
    MAX_BATCH_ITEMS,
    MAX_STRING_LEN,
    AlertCondition,
    ArpMapping,
    ArpObservation,
    Asset,
    Baseline,
    Batch,
    DiscoveryCycle,
    DiscoveryObservation,
    InventoryEvent,
    PortInfo,
    TrafficObservation,
)

NOW = datetime(2026, 11, 11, 12, 0, 0, tzinfo=UTC)
MAC = "aa:bb:cc:dd:ee:ff"


def test_asset_valid() -> None:
    asset = Asset(
        asset_id=uuid.uuid4(),
        ips=[IPv4Address("192.168.1.10")],
        mac=MAC,
        status="present",
        first_seen=NOW,
        last_seen=NOW,
        source="discovery",
    )
    assert asset.sensor_id == "sensor-0"
    assert asset.os_provenance == "unknown"


def test_asset_frozen_rejects_mutation() -> None:
    asset = Asset(
        asset_id=uuid.uuid4(),
        ips=[IPv4Address("10.0.0.1")],
        status="present",
        first_seen=NOW,
        last_seen=NOW,
        source="discovery",
    )
    with pytest.raises(ValidationError):
        asset.status = "absent"  # type: ignore[misc]


def test_asset_extra_field_rejected() -> None:
    with pytest.raises(ValidationError):
        Asset(
            asset_id=uuid.uuid4(),
            ips=[IPv4Address("10.0.0.1")],
            status="present",
            first_seen=NOW,
            last_seen=NOW,
            source="discovery",
            unexpected="x",  # type: ignore[call-arg]
        )


def test_mac_normalized_lowercase() -> None:
    obs = _discovery(mac="AA:BB:CC:DD:EE:FF")
    assert obs.mac == MAC


def test_mac_invalid_rejected() -> None:
    with pytest.raises(ValidationError):
        _discovery(mac="not-a-mac")


def test_mac_pattern_enforced() -> None:
    with pytest.raises(ValidationError):
        _discovery(mac="aa:bb:cc:dd:ee")  # 5 octetos


def test_naive_datetime_rejected() -> None:
    with pytest.raises(ValidationError):
        _discovery(observed_at=datetime(2026, 1, 1, 0, 0, 0))


def test_datetime_converted_to_utc() -> None:
    aware = datetime(2026, 1, 1, 8, 0, 0, tzinfo=timezone(timedelta(hours=2)))
    obs = _discovery(observed_at=aware)
    assert obs.observed_at == datetime(2026, 1, 1, 6, 0, 0, tzinfo=UTC)


def test_sensor_id_present_on_all_variants() -> None:
    disc = _discovery()
    traffic = TrafficObservation(
        observed_at=NOW,
        window_start=NOW,
        window_end=NOW,
        interface="eth0",
        protocol="tcp",
        packet_length_bytes=100,
        bytes_per_second=20.0,
        packets=1,
        flows=1,
        pairs=[],
    )
    arp = ArpObservation(
        observed_at=NOW,
        interface="eth0",
        opcode=1,
        psrc=IPv4Address("192.168.1.1"),
        pdst=IPv4Address("192.168.1.2"),
        hwsrc=MAC,
        hwdst=MAC,
    )
    assert disc.sensor_id and traffic.sensor_id and arp.sensor_id


def test_extra_field_rejected_on_observation() -> None:
    with pytest.raises(ValidationError):
        _discovery(bogus=1)


def test_hostname_length_limit() -> None:
    with pytest.raises(ValidationError):
        _discovery(hostname="h" * (MAX_STRING_LEN + 1))


def test_batch_cardinality_limit() -> None:
    items = [
        _discovery(ip=f"10.0.0.{i % 254 + 1}").model_dump(mode="json")
        for i in range(MAX_BATCH_ITEMS + 1)
    ]
    with pytest.raises(ValidationError):
        Batch(items=items)


def test_batch_discriminator_rejects_unknown_source() -> None:
    with pytest.raises(ValidationError):
        Batch(items=[{"observed_at": NOW.isoformat(), "source": "bogus"}])


def test_batch_accepts_mixed_valid_items() -> None:
    disc = _discovery().model_dump(mode="json")
    arp = ArpObservation(
        observed_at=NOW,
        interface="eth0",
        opcode=2,
        psrc=IPv4Address("192.168.1.1"),
        pdst=IPv4Address("192.168.1.255"),
        hwsrc=MAC,
        hwdst=MAC,
    ).model_dump(mode="json")
    batch = Batch(items=[disc, arp])
    assert len(batch.items) == 2


def test_os_provenance_values() -> None:
    for value in ("observed", "inferred", "declared", "unknown"):
        assert _discovery(os_provenance=value).os_provenance == value
    with pytest.raises(ValidationError):
        _discovery(os_provenance="confirmed")  # BR-18: unknown jamás "confirmed"


def test_inventory_event_id_and_type() -> None:
    event = InventoryEvent(
        event_id=uuid.uuid4(),
        type=EventType.ASSET_FIRST_SEEN,
        occurred_at=NOW,
    )
    assert isinstance(event.event_id, uuid.UUID)
    assert event.type == "asset_first_seen"
    assert event.severity == "info"


def test_discovery_cycle_status_and_trigger() -> None:
    cycle = DiscoveryCycle(
        run_id=uuid.uuid4(),
        status="completed",
        trigger="manual",
        started_at=NOW,
        finished_at=NOW,
        hosts_targeted=3,
        hosts_seen=2,
    )
    assert cycle.status == "completed"
    with pytest.raises(ValidationError):
        DiscoveryCycle(
            run_id=uuid.uuid4(),
            status="bogus",
            trigger="manual",
            started_at=NOW,
            hosts_targeted=0,
            hosts_seen=0,
        )


def test_arp_mapping_change_timestamp() -> None:
    mapping = ArpMapping(
        ip=IPv4Address("192.168.1.5"),
        mac=MAC,
        interface="eth0",
        first_seen=NOW,
        last_seen=NOW,
        changed_at=None,
    )
    changed = mapping.model_copy(update={"changed_at": NOW})
    assert changed.changed_at == NOW


def test_alert_condition_rules() -> None:
    cond = AlertCondition(
        condition_id=uuid.uuid4(),
        rule="R-01",
        state="baseline_establishing",
    )
    assert cond.rule == "R-01"
    with pytest.raises(ValidationError):
        AlertCondition(
            condition_id=uuid.uuid4(),
            rule="R-99",  # type: ignore[arg-type]
            state="firing",
        )


def test_baseline_variance_non_negative() -> None:
    baseline = Baseline(
        metric_key="bytes_per_second:eth0:tcp",
        samples=[1.0, 2.0, 3.0],
        mean=2.0,
        variance=1.0,
    )
    assert baseline.established is False
    with pytest.raises(ValidationError):
        Baseline(
            metric_key="k",
            samples=[1.0],
            mean=1.0,
            variance=-0.1,
        )


def test_port_info_confidence() -> None:
    port = PortInfo(port=443, state="open", service="https", confidence="probable")
    assert port.confidence == "probable"
    with pytest.raises(ValidationError):
        PortInfo(port=70000, state="open")


def test_traffic_window_order() -> None:
    with pytest.raises(ValidationError):
        TrafficObservation(
            observed_at=NOW,
            window_start=NOW,
            window_end=NOW - timedelta(seconds=1),
            interface="eth0",
            protocol="tcp",
            packet_length_bytes=1,
            bytes_per_second=1.0,
            packets=1,
            flows=1,
            pairs=[],
        )


def _discovery(**overrides: object) -> DiscoveryObservation:
    data: dict = {
        "observed_at": NOW,
        "ip": IPv4Address("192.168.1.10"),
        "method": "arp",
        "mac": MAC,
    }
    data.update(overrides)
    return DiscoveryObservation(**data)  # type: ignore[arg-type]
