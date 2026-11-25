"""Tests del contrato de métricas (BR-20..BR-22)."""

from __future__ import annotations

import re

import pytest

from sentinel.foundation.metrics_contract import (
    ALLOWED_LABELS_DEFAULT,
    FORBIDDEN_LABELS,
    METRIC_FAMILIES,
    METRIC_PREFIX,
    assert_allowed,
    assert_labels,
    metric_name,
)


def test_prefix() -> None:
    assert METRIC_PREFIX == "sentinel_"


def test_metric_name_composes() -> None:
    assert metric_name("flows_total") == "sentinel_flows_total"


def test_metric_name_idempotent_with_prefix() -> None:
    assert metric_name("sentinel_flows_total") == "sentinel_flows_total"


@pytest.mark.parametrize("bad", ["", "Foo", "foo-bar", "foo.bar", "foo bar", "ünïcode"])
def test_metric_name_invalid(bad: str) -> None:
    with pytest.raises(ValueError):
        metric_name(bad)


def test_metric_names_match_pattern() -> None:
    for family in METRIC_FAMILIES:
        assert family.startswith(METRIC_PREFIX)
        assert re.match(r"^sentinel_[a-z0-9_]+$", family)


def test_forbidden_labels() -> None:
    assert frozenset({"src_ip", "dst_ip", "mac", "asset_id"}) == FORBIDDEN_LABELS


def test_allowed_labels_default() -> None:
    assert (
        frozenset({"component", "protocol", "interface", "rule", "state", "collector", "metric"})
        == ALLOWED_LABELS_DEFAULT
    )


@pytest.mark.parametrize("label", ["src_ip", "dst_ip", "mac", "asset_id"])
def test_assert_labels_rejects_forbidden(label: str) -> None:
    with pytest.raises(ValueError, match="forbidden"):
        assert_labels({label: "x"})


def test_assert_labels_allows_default() -> None:
    assert_labels({"component": "core", "protocol": "tcp"})


def test_assert_labels_empty() -> None:
    assert_labels({})


def test_baseline_families_present() -> None:
    """U6 (MNT-02): las 3 familias nuevas están en el catálogo."""
    for family in (
        "sentinel_traffic_threshold_exceeded",
        "sentinel_baseline_status",
        "sentinel_collector_up",
    ):
        assert family in METRIC_FAMILIES
        assert metric_name(family) == family  # idempotente con prefijo


def test_metric_name_valid_for_baseline_labels() -> None:
    assert metric_name("baseline_status") == "sentinel_baseline_status"
    assert metric_name("traffic_threshold_exceeded") == ("sentinel_traffic_threshold_exceeded")


def test_assert_labels_accepts_baseline_label_set() -> None:
    """assert_labels acepta {interface, protocol, state, collector, metric}."""
    assert_labels({"interface": "eth0", "protocol": "tcp"})
    assert_labels({"state": "firing", "metric": "bytes_per_second"})
    assert_labels({"collector": "traffic"})


def test_catalog_v2_has_fourteen_families() -> None:
    assert len(METRIC_FAMILIES) == 14
    assert "sentinel_assets_total" in METRIC_FAMILIES
    assert "sentinel_asset_changes_total" in METRIC_FAMILIES


def test_assert_allowed_accepts_allowlist() -> None:
    assert_allowed({"component": "core", "state": "200"})
    assert_allowed({"interface": "eth0", "protocol": "tcp"})
    assert_allowed({"collector": "traffic", "metric": "bytes_per_second"})
    assert_allowed({})


@pytest.mark.parametrize("label", ["src_ip", "dst_ip", "mac", "asset_id"])
def test_assert_allowed_rejects_forbidden(label: str) -> None:
    with pytest.raises(ValueError, match="forbidden"):
        assert_allowed({label: "x"})


@pytest.mark.parametrize("label", ["hostname", "sensor_id", "alert_id"])
def test_assert_allowed_rejects_outside_allowlist(label: str) -> None:
    with pytest.raises(ValueError, match="allowlist"):
        assert_allowed({label: "x"})
