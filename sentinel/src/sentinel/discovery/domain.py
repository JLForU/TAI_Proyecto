"""Dominio puro de discovery (U4): entidades, targets y fusión de hallazgos.

Sin I/O: solo modelos inmutables y funciones puras (FD §3.3, BR-U4-16/17).
"""

from __future__ import annotations

from ipaddress import IPv4Network, ip_network
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from sentinel.foundation.models import OsProvenance, PortInfo

__all__ = [
    "CycleResult",
    "CycleStatus",
    "HostFinding",
    "Method",
    "ScopeConfig",
    "merge_findings",
    "resolve_targets",
]

CycleStatus = Literal["completed", "timeout", "failed"]
Method = Literal["arp", "icmp", "tcp", "nmap"]

#: Preponderancia del método fusionado: nmap > tcp > icmp > arp (BR-U4-16).
_PRECEDENCE: dict[str, int] = {"nmap": 0, "tcp": 1, "icmp": 2, "arp": 3}

#: Cap duro de targets por ciclo (P13/SCAL-01 — crecimiento lo trata U11).
TARGET_CAP = 1000


class ScopeConfig(BaseModel):
    """Allowlist de alcance normalizada (C12)."""

    model_config = ConfigDict(frozen=True)

    mode: Literal["cidr", "explicit_hosts"] = "explicit_hosts"
    hosts: tuple[str, ...] = ()
    cidrs: tuple[str, ...] = ()
    ports: tuple[int, ...] = (22, 80, 443)


class HostFinding(BaseModel):
    """Hallazgo de un host dentro de un ciclo (antes de la fusión final)."""

    model_config = ConfigDict(frozen=True)

    ip: str
    mac: str | None = None
    hostname: str | None = None
    os_name: str | None = None
    os_provenance: OsProvenance = "unknown"
    ports: list[PortInfo] = Field(default_factory=list)
    method: Method

class CycleResult(BaseModel):
    """Resultado de un ciclo (FD §1.4)."""

    model_config = ConfigDict(frozen=True)

    status: CycleStatus
    hosts_seen: int = 0
    hosts_targeted: int = 0
    findings: list[HostFinding] = Field(default_factory=list)
    partial: bool = False
    error: str | None = None


def resolve_targets(
    hosts: tuple[str, ...] | list[str],
    *,
    mode: str = "explicit_hosts",
    cidrs: tuple[str, ...] | list[str] = (),
    cap: int = TARGET_CAP,
) -> list[str]:
    """Targets canónicos: lista explícita o expansión de CIDRs, dedup + cap.

    En modo ``explicit_hosts`` devuelve la lista tal cual (sin resolver DNS);
    en modo ``cidr`` expande las redes a IPs ordenadas y las recorta a ``cap``.
    """
    if mode == "cidr":
        networks: list[IPv4Network] = []
        for raw in cidrs:
            try:
                net = ip_network(raw.strip(), strict=False)
            except ValueError:
                continue
            if isinstance(net, IPv4Network):
                networks.append(net)
        expanded: list[str] = []
        seen: set[str] = set()
        for net in networks:
            for host in net.hosts():
                text = str(host)
                if text not in seen:
                    seen.add(text)
                    expanded.append(text)
                if len(expanded) >= cap:
                    return expanded
        return expanded

    ordered: list[str] = []
    seen_hosts: set[str] = set()
    for raw in hosts:
        text = raw.strip()
        if text and text not in seen_hosts:
            seen_hosts.add(text)
            ordered.append(text)
        if len(ordered) >= cap:
            break
    return ordered


def _merge_ports(findings: list[HostFinding]) -> list[PortInfo]:
    """1 PortInfo por puerto: servicio/versión de nmap gana (BR-U4-16)."""
    by_port: dict[int, PortInfo] = {}
    for finding in findings:
        for info in finding.ports:
            current = by_port.get(info.port)
            if current is None or _richer(info, current):
                by_port[info.port] = info
    return [by_port[port] for port in sorted(by_port)]


def _richer(candidate: PortInfo, current: PortInfo) -> bool:
    cand_score = (
        candidate.service is not None or candidate.version is not None,
        candidate.confidence == "confirmed",
    )
    cur_score = (
        current.service is not None or current.version is not None,
        current.confidence == "confirmed",
    )
    return cand_score > cur_score


def merge_findings(findings: list[HostFinding]) -> list[HostFinding]:
    """1 hallazgo por IP: método preponderante, MAC/hostname y puertos combinados."""
    by_ip: dict[str, list[HostFinding]] = {}
    for finding in findings:
        by_ip.setdefault(finding.ip, []).append(finding)

    merged: list[HostFinding] = []
    for ip in sorted(by_ip):
        group = by_ip[ip]
        ordered = sorted(group, key=lambda f: _PRECEDENCE[f.method])
        best = ordered[0]
        mac = next((f.mac for f in ordered if f.mac), None)
        hostname = next((f.hostname for f in ordered if f.hostname), None)
        os_finding = next((f for f in ordered if f.os_name), None)
        merged.append(
            HostFinding(
                ip=ip,
                mac=mac,
                hostname=hostname,
                os_name=os_finding.os_name if os_finding else None,
                os_provenance=os_finding.os_provenance if os_finding else "unknown",
                ports=_merge_ports(group),
                method=best.method,
            )
        )

    return merged
