"""Config estricta del worker (U4, BR-U4-01..05/10): fail-fast con ConfigError."""

from __future__ import annotations

import pytest

from sentinel.discovery.config import DiscoverySettings, load_discovery_settings, parse_ports
from sentinel.foundation.errors import ConfigError

_HOSTS = {"SENTINEL_DISCOVERY_HOSTS": "10.0.0.1"}


def test_defaults() -> None:
    settings = load_discovery_settings(dict(_HOSTS))
    assert settings.scope_mode == "explicit_hosts"
    assert settings.ports == "22,80,443"
    assert settings.interval_minutes == 15
    assert settings.timeout_seconds == 30
    assert settings.scanner == "auto"
    assert settings.nmap_args == ""


def test_defaults_without_env_keys_are_lab_values() -> None:
    settings = DiscoverySettings()
    assert (settings.scope_mode, settings.ports, settings.interval_minutes) == (
        "explicit_hosts",
        "22,80,443",
        15,
    )


@pytest.mark.parametrize(
    "env",
    [
        {**_HOSTS, "SENTINEL_DISCOVERY_SCOPE_MODE": "bogus"},
        {**_HOSTS, "SENTINEL_DISCOVERY_SCANNER": "stealth"},
        {**_HOSTS, "SENTINEL_DISCOVERY_INTERVAL_MIN": "0"},
        {**_HOSTS, "SENTINEL_DISCOVERY_INTERVAL_MIN": "abc"},
        {**_HOSTS, "SENTINEL_DISCOVERY_TIMEOUT_SECONDS": "0"},
        {**_HOSTS, "SENTINEL_DISCOVERY_TIMEOUT_SECONDS": "3601"},
        {"SENTINEL_DISCOVERY_UNKNOWN_KEY": "x"},
    ],
)
def test_invalid_config(env: dict[str, str]) -> None:
    with pytest.raises(ConfigError):
        load_discovery_settings(env)


def test_empty_allowlist() -> None:
    with pytest.raises(ConfigError, match="HOSTS must not be empty"):
        load_discovery_settings({"SENTINEL_DISCOVERY_HOSTS": ""})


def test_allowlist_required_cidr_mode() -> None:
    with pytest.raises(ConfigError, match="CIDRS must not be empty"):
        load_discovery_settings({"SENTINEL_DISCOVERY_SCOPE_MODE": "cidr"})


def test_allowlist_required_explicit_mode() -> None:
    with pytest.raises(ConfigError, match="HOSTS must not be empty"):
        load_discovery_settings({"SENTINEL_DISCOVERY_SCOPE_MODE": "explicit_hosts"})


def test_cidr_mode_accepts_valid_network() -> None:
    settings = load_discovery_settings(
        {"SENTINEL_DISCOVERY_SCOPE_MODE": "cidr", "SENTINEL_DISCOVERY_CIDRS": "192.168.1.0/24"}
    )
    assert settings.cidrs_list() == ("192.168.1.0/24",)


def test_cidr_mode_rejects_invalid_network() -> None:
    with pytest.raises(ConfigError, match="invalid cidr"):
        load_discovery_settings(
            {"SENTINEL_DISCOVERY_SCOPE_MODE": "cidr", "SENTINEL_DISCOVERY_CIDRS": "not-a-cidr"}
        )


@pytest.mark.parametrize(
    "raw",
    ["", "0", "65536", "80,80", "abc", "80, ,80"],
)
def test_ports(raw: str) -> None:
    with pytest.raises(ConfigError):
        parse_ports(raw)


def test_ports_valid_tuple() -> None:
    assert parse_ports("22, 80,443") == (22, 80, 443)


@pytest.mark.parametrize(
    "args",
    ["-O", "-sU", "-sS", "-sC", "-A", "--script", "--script=http-title", "-f", "--open"],
)
def test_forbidden_scan_methods(args: str) -> None:
    with pytest.raises(ConfigError):
        load_discovery_settings({**_HOSTS, "SENTINEL_DISCOVERY_NMAP_ARGS": args})


def test_scan_options_allowlisted_extras() -> None:
    settings = load_discovery_settings({**_HOSTS, "SENTINEL_DISCOVERY_NMAP_ARGS": "-Pn -n"})
    assert settings.nmap_args == "-Pn -n"


def test_scan_options_rejects_coloned_target() -> None:
    with pytest.raises(ConfigError, match="unexpected scan option token"):
        load_discovery_settings({**_HOSTS, "SENTINEL_DISCOVERY_NMAP_ARGS": "10.0.0.5"})
