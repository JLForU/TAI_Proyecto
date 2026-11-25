"""Escáner: argv whitelist + fallback fixtures (U4, BR-U4-10..12/18/19)."""

from __future__ import annotations

from pathlib import Path

import pytest

from sentinel.discovery.scanner import (
    FixtureScanner,
    NmapScanner,
    ScannerError,
    build_nmap_argv,
    create_scanner,
    parse_nmap_xml,
    validate_scan_options,
)
from sentinel.foundation.errors import ConfigError

FIXTURES = Path(__file__).parent / "fixtures"

VALID_NMAP_XML = FIXTURES / "nmap_sample.xml"
VALID_ARP = FIXTURES / "arp_sample.txt"


def test_required_flags() -> None:
    argv = build_nmap_argv(["10.0.0.5"], [22, 80])
    assert argv[:8] == [
        "nmap",
        "-sT",
        "-sV",
        "--version-light",
        "-p",
        "22,80",
        "-oX",
        "-",
    ]
    assert argv[-1] == "10.0.0.5"


def test_no_aggressive_flags() -> None:
    for bad in ("-O", "-sU", "-sS", "-sC", "-A", "--script", "--script=vuln"):
        with pytest.raises(ConfigError):
            build_nmap_argv(["10.0.0.5"], [22], extra_args=bad)


def test_unknown_flag_rejected() -> None:
    with pytest.raises(ConfigError, match="unknown scan option"):
        validate_scan_options(["--datadir", "/tmp"])


def test_value_flag_consumes_next_token() -> None:
    validate_scan_options(["-p", "8080"])
    validate_scan_options(["-p=8080"])
    with pytest.raises(ConfigError):
        validate_scan_options(["-p"])
    with pytest.raises(ConfigError):
        validate_scan_options(["-p", "-n"])


def test_extras_are_placed_before_targets() -> None:
    argv = build_nmap_argv(["10.0.0.5"], [22], extra_args="-Pn -n")
    assert argv == [
        "nmap",
        "-sT",
        "-sV",
        "--version-light",
        "-p",
        "22",
        "-oX",
        "-",
        "-Pn",
        "-n",
        "10.0.0.5",
    ]


def test_parse_nmap_xml_extracts_hosts_and_ports() -> None:
    findings = parse_nmap_xml(VALID_NMAP_XML.read_text(encoding="utf-8"))
    assert [f.ip for f in findings] == ["192.168.1.10", "192.168.1.11"]
    first = findings[0]
    assert first.method == "nmap"
    assert first.hostname == "lab-host-10"
    assert first.mac == "aa:bb:cc:dd:ee:0a"
    assert [(p.port, p.service, p.confidence) for p in first.ports] == [
        (22, "ssh", "confirmed"),
        (80, "http", "confirmed"),
    ]


def test_parse_nmap_xml_controlled_error() -> None:
    with pytest.raises(ScannerError, match="invalid nmap xml"):
        parse_nmap_xml("<nmaprun><host></nmaprun>")
    with pytest.raises(ScannerError):
        parse_nmap_xml("definitely not xml")


def test_parse_nmap_xml_skips_down_hosts() -> None:
    xml = """<?xml version="1.0"?><nmaprun>
      <host><status state="down"/><address addr="10.0.0.9" addrtype="ipv4"/></host>
      <host><status state="up"/><address addr="10.0.0.10" addrtype="ipv4"/>
        <ports><port protocol="tcp" portid="22"><state state="closed"/></port></ports>
      </host></nmaprun>"""
    findings = parse_nmap_xml(xml)
    assert len(findings) == 1
    assert findings[0].ip == "10.0.0.10"
    assert findings[0].ports == []


def test_fixture_scanner_primitives() -> None:
    scanner = FixtureScanner(nmap_xml=VALID_NMAP_XML, arp_table=VALID_ARP)
    assert scanner.arp_neighbors() == {
        "192.168.1.10": "aa:bb:cc:dd:ee:0a",
        "192.168.1.11": "aa:bb:cc:dd:ee:0b",
    }
    assert scanner.ping("192.168.1.10") is True
    assert scanner.ping("10.9.9.9") is False
    assert scanner.tcp_open("192.168.1.10", 22) is True
    assert scanner.tcp_open("192.168.1.10", 443) is False
    findings = scanner.nmap_scan(["192.168.1.10"], [22])
    assert [f.ip for f in findings] == ["192.168.1.10"]


def test_fixture_scanner_default_dataset() -> None:
    scanner = FixtureScanner()
    assert scanner.ping("192.168.1.10")
    assert scanner.nmap_scan(["192.168.1.10", "10.9.9.9"], [22])


def test_fallback_fixtures_when_nmap_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from sentinel.discovery import scanner as scanner_mod

    monkeypatch.setattr(scanner_mod.shutil, "which", lambda _name: None)
    settings = type("S", (), {"scanner": "auto"})()
    chosen = create_scanner(settings)
    assert isinstance(chosen, FixtureScanner)


def test_create_scanner_explicit_modes() -> None:
    fixtures = create_scanner(type("S", (), {"scanner": "fixtures"})())
    assert isinstance(fixtures, FixtureScanner)
    nmap = create_scanner(type("S", (), {"scanner": "nmap"})())
    assert isinstance(nmap, NmapScanner)


def test_nmap_scanner_missing_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    import shutil as shutil_mod

    monkeypatch.setattr(shutil_mod, "which", lambda _name: None)
    with pytest.raises(ScannerError, match="nmap binary not found"):
        NmapScanner().nmap_scan(["10.0.0.1"], [22])


def test_nmap_scanner_unprivileged_primitives(monkeypatch: pytest.MonkeyPatch) -> None:
    """ARP/ICMP/TCP usan subprocess stdlib y sockets sin root (BR-U4-19)."""
    import subprocess

    from sentinel.discovery import scanner as scanner_mod

    calls: list[list[str]] = []

    def fake_run(argv, **_kwargs):  # type: ignore[no-untyped-def]
        calls.append(list(argv))
        return subprocess.CompletedProcess(
            argv, 0, stdout="10.0.0.5 dev eth0 lladdr aa:bb:cc:dd:ee:05 REACHABLE\n", stderr=""
        )

    monkeypatch.setattr(scanner_mod.subprocess, "run", fake_run)
    scanner = NmapScanner()
    assert scanner.arp_neighbors() == {"10.0.0.5": "aa:bb:cc:dd:ee:05"}
    assert calls[0][:2] == ["ip", "neigh"]
    assert scanner.ping("10.0.0.5") is True
    assert calls[1][:3] == ["ping", "-c", "1"]
