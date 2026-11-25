"""argv de nmap (U4, BR-U4-10..12): whitelist y fijos del ciclo."""

from __future__ import annotations

import pytest

from sentinel.discovery.scanner import build_nmap_argv, validate_scan_options
from sentinel.foundation.errors import ConfigError


def test_required_flags() -> None:
    argv = build_nmap_argv(["192.168.1.10", "192.168.1.11"], [22, 80, 443])
    assert argv[0] == "nmap"
    assert "-sT" in argv and "-sV" in argv and "--version-light" in argv
    assert argv[argv.index("-p") + 1] == "22,80,443"
    assert argv[argv.index("-oX") + 1] == "-"
    assert argv[-2:] == ["192.168.1.10", "192.168.1.11"]


def test_no_aggressive_flags_in_allowed_extras() -> None:
    """Los extras jamás pueden contener flags prohibidos (FR-DISC-02)."""
    for bad in ("-O", "-sU", "-sS", "-sC", "-A"):
        with pytest.raises(ConfigError, match="forbidden"):
            validate_scan_options([bad])


def test_no_aggressive_flags_via_build() -> None:
    for bad in ("-O", "-sU", "--script", "--script=vuln", "-A"):
        with pytest.raises(ConfigError):
            build_nmap_argv(["10.0.0.1"], [22], extra_args=bad)


def test_unknown_flags_rejected() -> None:
    with pytest.raises(ConfigError, match="unknown"):
        validate_scan_options(["-sV", "--bad-flag"])


def test_allowlisted_extras_pass() -> None:
    validate_scan_options(["-Pn", "-n", "-p", "8080", "-oN", "/tmp/out.nmap"])


def test_raw_target_token_rejected() -> None:
    """NMAP_ARGS no puede colar un target crudo (BR-U4-09)."""
    with pytest.raises(ConfigError, match="unexpected"):
        validate_scan_options(["10.0.0.5"])


def test_shell_metacharacters_rejected() -> None:
    """Sin string crudo al subprocess: tokens con shell metacharacter no pasan."""
    with pytest.raises(ConfigError):
        validate_scan_options(["-p;rm"])
    with pytest.raises(ConfigError):
        build_nmap_argv(["10.0.0.1"], [22], extra_args="; rm -rf /")
