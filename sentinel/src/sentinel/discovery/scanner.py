"""Escáner intercambiable de U4 (FD §3.4): whitelist, nmap real y fixtures.

- ``validate_scan_options`` / ``build_nmap_argv``: argv **programático** con
  whitelist estricta (BR-U4-10..12) — jamás un string crudo del usuario.
- ``NmapScanner``: subprocess ``shell=False`` (nmap, ``ip neigh``, ``ping``) y
  TCP connect stdlib — sin raw sockets ni root (BR-U4-19).
- ``FixtureScanner``: mismas primitivas desde XML/tabla ARP (tests, fallback).
- ``create_scanner``: modo ``auto`` con fallback a fixtures (BR-U4-18).
"""

from __future__ import annotations

import shlex
import shutil
import socket
import subprocess
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from ipaddress import IPv4Address
from pathlib import Path
from typing import Protocol

from sentinel.discovery.config import CONNECT_TIMEOUT_S, PING_TIMEOUT_S
from sentinel.discovery.domain import HostFinding
from sentinel.foundation.errors import ConfigError, ProbeError
from sentinel.foundation.logging import get_logger
from sentinel.foundation.models import MAX_STRING_LEN, PortInfo

__all__ = [
    "ALLOWED_NMAP_FLAGS",
    "FORBIDDEN_NMAP_FLAGS",
    "FixtureScanner",
    "NmapScanner",
    "Scanner",
    "ScannerError",
    "build_nmap_argv",
    "create_scanner",
    "parse_nmap_xml",
    "validate_scan_options",
]

_log = get_logger("discovery.scanner")

#: Flags permitidos como extras (BR-U4-10).
ALLOWED_NMAP_FLAGS = frozenset({"-sT", "-sV", "--version-light", "-p", "-oX", "-oN", "-Pn", "-n"})

#: Flags agresivos/prohibidos por FR-DISC-02 (nunca en el argv).
FORBIDDEN_NMAP_FLAGS = frozenset({"-O", "-sU", "-sS", "-sC", "-A"})

#: Flags que consumen el token siguiente como valor.
_VALUE_FLAGS = frozenset({"-p", "-oX", "-oN"})


class ScannerError(ProbeError):
    """Fallo controlado del escáner (XML inválido, binario ausente, timeout)."""

    code = "scanner_error"


class Scanner(Protocol):
    """Primitivas del escáner (una por fase del ciclo)."""

    def arp_neighbors(self) -> dict[str, str]:
        """Tabla ARP del sistema: ``ip -> mac`` (filtrada aguas abajo)."""
        ...

    def ping(self, host: str) -> bool:
        """ICMP echo al host (``ping -c 1 -W 1``)."""
        ...

    def tcp_open(self, host: str, port: int) -> bool:
        """Connect TCP al puerto de la allowlist."""
        ...

    def nmap_scan(
        self,
        targets: Sequence[str],
        ports: Sequence[int],
        extra_args: str = "",
        timeout: float | None = None,
    ) -> list[HostFinding]:
        """Sondeo ligero de servicios (``-sT -sV --version-light``)."""
        ...


def validate_scan_options(tokens: Sequence[str]) -> None:
    """Whitelist estricta de extras (BR-U4-10): lanza ``ConfigError``.

    Acepta tokens con forma ``flag`` o ``flag=valor``; los flags con valor
    consumen el siguiente token (que no debe empezar por ``-``) — impide
    colar targets o subcomandos crudos en ``SENTINEL_DISCOVERY_NMAP_ARGS``.
    """
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if not token.startswith("-"):
            raise ConfigError(f"unexpected scan option token: {token}")
        base = token.split("=", 1)[0]
        if base in FORBIDDEN_NMAP_FLAGS or base.startswith("--script"):
            raise ConfigError(f"forbidden scan option: {token}")
        if base not in ALLOWED_NMAP_FLAGS:
            raise ConfigError(f"unknown scan option: {token}")
        if base in _VALUE_FLAGS and "=" not in token:
            if index + 1 >= len(tokens) or tokens[index + 1].startswith("-"):
                raise ConfigError(f"scan option {token} requires a value")
            index += 2
            continue
        index += 1


def build_nmap_argv(
    targets: Sequence[str], ports: Sequence[int], extra_args: str = ""
) -> list[str]:
    """argv de nmap construido programáticamente (BR-U4-11/12)."""
    extras = shlex.split(extra_args) if extra_args.strip() else []
    validate_scan_options(extras)
    return [
        "nmap",
        "-sT",
        "-sV",
        "--version-light",
        "-p",
        ",".join(str(port) for port in ports),
        "-oX",
        "-",
        *extras,
        *targets,
    ]


def parse_nmap_xml(xml_text: str) -> list[HostFinding]:
    """Parsea la salida XML de nmap → hallazgos ``method="nmap"``.

    XML malformado ⇒ ``ScannerError`` controlado (BR-U4-20, P12); nunca una
    excepción cruda del parser. Atributos hostiles (IP/MAC/puerto inválidos,
    strings largos) se descartan o recortan en lugar de explotar (PBT MNT-03).
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ScannerError(f"invalid nmap xml: {exc}") from exc

    findings: list[HostFinding] = []
    for host in root.findall("host"):
        status = host.find("status")
        if status is not None and status.get("state") not in (None, "up"):
            continue
        ip = _address_of(host, "ipv4")
        if ip is None or not _is_ipv4(ip):
            continue
        mac = _address_of(host, "mac")
        if mac is not None and not _is_mac(mac):
            mac = None
        hostname = None
        name = host.find("hostnames/hostname")
        if name is not None:
            hostname = _clip(name.get("name"))
        ports: list[PortInfo] = []
        for port_el in host.findall("ports/port"):
            state_el = port_el.find("state")
            state = state_el.get("state", "unknown") if state_el is not None else "unknown"
            if state != "open":
                continue
            number = _parse_portid(port_el.get("portid"))
            if number is None:
                continue
            service_el = port_el.find("service")
            service = _clip(service_el.get("name")) if service_el is not None else None
            version = _clip(service_el.get("version")) if service_el is not None else None
            protocol = port_el.get("protocol", "tcp")
            if protocol not in {"tcp", "udp"}:
                protocol = "other"
            ports.append(
                PortInfo(
                    port=number,
                    protocol=protocol,  # type: ignore[arg-type]
                    state="open",
                    service=service,
                    version=version,
                    confidence="confirmed" if (service or version) else "probable",
                )
            )
        findings.append(HostFinding(ip=ip, mac=mac, hostname=hostname, ports=ports, method="nmap"))
    return findings


_MAC_RE = __import__("re").compile(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$")


def _is_ipv4(raw: str) -> bool:
    try:
        IPv4Address(raw)
    except ValueError:
        return False
    return True


def _is_mac(raw: str) -> bool:
    return bool(_MAC_RE.match(raw.strip().lower()))


def _clip(raw: str | None) -> str | None:
    if raw is None:
        return None
    return raw[:MAX_STRING_LEN]


def _parse_portid(raw: str | None) -> int | None:
    if raw is None:
        return None
    try:
        number = int(raw)
    except ValueError:
        return None
    if not 1 <= number <= 65535:
        return None
    return number


def _address_of(host: ET.Element, kind: str) -> str | None:
    for addr in host.findall("address"):
        if addr.get("addrtype") == kind:
            return addr.get("addr")
    return None


class NmapScanner:
    """Escáner real: subprocess ``shell=False`` + stdlib (BR-U4-19)."""

    def __init__(self) -> None:
        self._ping_warned = False

    def arp_neighbors(self) -> dict[str, str]:
        try:
            proc = subprocess.run(
                ["ip", "neigh"], capture_output=True, text=True, timeout=5, check=False
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return {}
        table: dict[str, str] = {}
        for line in proc.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4 and "lladdr" in parts:
                try:
                    IPv4Address(parts[0])
                except ValueError:
                    continue
                table[parts[0]] = parts[parts.index("lladdr") + 1]
        return table

    def ping(self, host: str) -> bool:
        try:
            proc = subprocess.run(
                ["ping", "-c", "1", "-W", str(int(PING_TIMEOUT_S)), host],
                capture_output=True,
                text=True,
                timeout=PING_TIMEOUT_S + 2,
                check=False,
            )
        except FileNotFoundError:
            if not self._ping_warned:
                self._ping_warned = True
                _log.warning(
                    "ping binary unavailable; icmp phase skipped",
                    extra={"event": "ping_unavailable"},
                )
            return False
        except (subprocess.TimeoutExpired, OSError):
            return False
        return proc.returncode == 0

    def tcp_open(self, host: str, port: int) -> bool:
        try:
            with socket.create_connection((host, port), timeout=CONNECT_TIMEOUT_S):
                return True
        except OSError:
            return False

    def nmap_scan(
        self,
        targets: Sequence[str],
        ports: Sequence[int],
        extra_args: str = "",
        timeout: float | None = None,
    ) -> list[HostFinding]:
        if shutil.which("nmap") is None:
            raise ScannerError("nmap binary not found")
        argv = build_nmap_argv(targets, ports, extra_args)
        try:
            proc = subprocess.run(
                argv, capture_output=True, text=True, timeout=timeout, check=False
            )
        except subprocess.TimeoutExpired as exc:
            raise ScannerError("nmap timed out") from exc
        except OSError as exc:
            raise ScannerError(f"nmap failed to start: {exc}") from exc
        if proc.returncode != 0 and not proc.stdout.strip():
            raise ScannerError(f"nmap exited {proc.returncode}: {proc.stderr.strip()[:200]}")
        return parse_nmap_xml(proc.stdout)


_DEFAULT_NMAP_XML = """<?xml version="1.0"?>
<nmaprun>
  <host><status state="up"/>
    <address addr="192.168.1.10" addrtype="ipv4"/>
    <address addr="aa:bb:cc:dd:ee:0a" addrtype="mac"/>
    <hostnames><hostname name="lab-host-10"/></hostnames>
    <ports>
      <port protocol="tcp" portid="22"><state state="open"/>
        <service name="ssh" version="OpenSSH 9.0"/></port>
      <port protocol="tcp" portid="80"><state state="open"/>
        <service name="http"/></port>
    </ports>
  </host>
  <host><status state="up"/>
    <address addr="192.168.1.11" addrtype="ipv4"/>
    <hostnames><hostname name="lab-host-11"/></hostnames>
    <ports>
      <port protocol="tcp" portid="443"><state state="open"/>
        <service name="https"/></port>
    </ports>
  </host>
</nmaprun>
"""

_DEFAULT_ARP = "192.168.1.10 dev eth0 lladdr aa:bb:cc:dd:ee:0a REACHABLE\n"


class FixtureScanner:
    """Escáner de fixtures (tests, demo y fallback de ``auto``).

    Sin argumentos usa un dataset embebido de lab; los tests inyectan rutas a
    XML/tabla ARP propios (MNT-02: sin red en los tests).
    """

    def __init__(
        self,
        *,
        nmap_xml: str | Path | None = None,
        arp_table: str | Path | None = None,
        alive: Sequence[str] | None = None,
        open_ports: dict[str, set[int]] | None = None,
    ) -> None:
        xml_text = _read(nmap_xml) if nmap_xml is not None else _DEFAULT_NMAP_XML
        arp_text = _read(arp_table) if arp_table is not None else _DEFAULT_ARP
        self._findings = parse_nmap_xml(xml_text)
        self._arp = _parse_arp(arp_text)
        default_alive = {f.ip for f in self._findings} | set(self._arp)
        self._alive = set(alive) if alive is not None else default_alive
        if open_ports is not None:
            self._open = {ip: set(ports) for ip, ports in open_ports.items()}
        else:
            self._open = {
                f.ip: {p.port for p in f.ports if p.state == "open"} for f in self._findings
            }

    def arp_neighbors(self) -> dict[str, str]:
        return dict(self._arp)

    def ping(self, host: str) -> bool:
        return host in self._alive

    def tcp_open(self, host: str, port: int) -> bool:
        return host in self._alive and port in self._open.get(host, set())

    def nmap_scan(
        self,
        targets: Sequence[str],
        ports: Sequence[int],
        extra_args: str = "",
        timeout: float | None = None,
    ) -> list[HostFinding]:
        wanted = set(targets)
        return [f for f in self._findings if f.ip in wanted]


def _read(source: str | Path) -> str:
    return Path(source).read_text(encoding="utf-8")


def _parse_arp(text: str) -> dict[str, str]:
    table: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 4 and "lladdr" in parts:
            try:
                IPv4Address(parts[0])
            except ValueError:
                continue
            table[parts[0]] = parts[parts.index("lladdr") + 1]
    return table


def create_scanner(settings) -> Scanner:  # type: ignore[no-untyped-def]
    """Selecciona el escáner según ``SENTINEL_DISCOVERY_SCANNER`` (BR-U4-18)."""
    if settings.scanner == "fixtures":
        return FixtureScanner()
    if settings.scanner == "nmap":
        return NmapScanner()
    if shutil.which("nmap") is not None:
        return NmapScanner()
    _log.warning(
        "nmap binary not found; falling back to fixtures",
        extra={"event": "scanner_fallback"},
    )
    return FixtureScanner()
