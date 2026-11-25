"""Validación de alcance C12 (U4, BR-U4-06..09): worker y API comparten."""

from __future__ import annotations

from sentinel.discovery.config import DiscoverySettings
from sentinel.discovery.domain import ScopeConfig
from sentinel.discovery.scope import ScopeValidator


def _explicit(*hosts: str) -> ScopeValidator:
    return ScopeValidator(ScopeConfig(mode="explicit_hosts", hosts=tuple(hosts)))


def _cidr(*cidrs: str) -> ScopeValidator:
    return ScopeValidator(ScopeConfig(mode="cidr", cidrs=tuple(cidrs)))


def test_mode_explicit_match() -> None:
    validator = _explicit("10.0.0.1", "10.0.0.2")
    assert validator.validate_target("10.0.0.1").ok
    assert validator.validate_target(" 10.0.0.2 ").ok
    result = validator.validate_target("10.0.0.3")
    assert not result.ok
    assert "fuera de alcance" in result.errors[0]


def test_mode_cidr_membership() -> None:
    validator = _cidr("192.168.1.0/24")
    assert validator.validate_target("192.168.1.50").ok
    assert not validator.validate_target("10.9.9.9").ok


def test_mode_cidr_rejects_non_ip() -> None:
    validator = _cidr("192.168.1.0/24")
    assert not validator.validate_target("hostname.local").ok


def test_validate_scope_aggregates_errors() -> None:
    validator = _explicit("10.0.0.1")
    ok = validator.validate_scope(["10.0.0.1"])
    assert ok.ok and ok.errors == ()
    bad = validator.validate_scope(["10.0.0.1", "10.9.9.9", "8.8.8.8"])
    assert not bad.ok
    assert len(bad.errors) == 2


def test_validate_scope_empty_target() -> None:
    assert not _explicit("10.0.0.1").validate_target("").ok


def test_validate_ports() -> None:
    validator = _explicit("10.0.0.1")
    assert validator.validate_ports([22, 80, 443]).ok
    assert not validator.validate_ports([]).ok
    assert not validator.validate_ports([0]).ok
    assert not validator.validate_ports([70000]).ok


def test_scope_validator_from_discovery_settings() -> None:
    settings = DiscoverySettings(hosts="10.0.0.1,10.0.0.2")
    validator = ScopeValidator(settings)
    assert validator.mode == "explicit_hosts"
    assert validator.validate_scope(["10.0.0.2"]).ok
    assert not validator.validate_scope(["10.0.0.9"]).ok
