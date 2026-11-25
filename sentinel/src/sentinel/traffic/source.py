"""Fuente abstracta de paquetes (U5, BR-U5-06..11, P5, D-U5-03).

Eventos internos como ``dataclass`` slotted — sin validación Pydantic por
evento (P5); la proyección a contratos U1 ocurre en la frontera de export.
El MVP solo implementa ``SimulatedSource``/``FixtureSource``: la captura real
(``AfPacketSource``) queda documentada en domain-entities §5, sin código ni
dependencias (BR-U5-33). Solo IPv4 (D-U5-03).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from ipaddress import IPv4Address
from pathlib import Path
from typing import Literal, Protocol, cast, runtime_checkable

__all__ = [
    "ArpPacket",
    "FixtureSource",
    "IpPacket",
    "IpProtocol",
    "PacketSource",
    "SimulatedSource",
    "protocol_from_number",
]

IpProtocol = Literal["tcp", "udp", "icmp", "other"]
ArpOpcode = Literal[1, 2]

#: Tablas fijas del simulador (determinismo BR-U5-07).
_SRC_IPS = tuple(IPv4Address(f"10.0.0.{i}") for i in range(1, 21))
_DST_IPS = tuple(IPv4Address(f"10.0.1.{i}") for i in range(1, 21))
_ARP_TABLE = tuple((IPv4Address(f"10.0.0.{i}"), f"aa:bb:cc:dd:ee:{i:02x}") for i in range(1, 11))
_IP_PROTOCOL_NUMBERS = (6, 17, 1, 99)  # 99 ⇒ other (fallback BR-U5-18)
_BROADCAST_MAC = "ff:ff:ff:ff:ff:ff"
_ZERO_MAC = "00:00:00:00:00:00"


def protocol_from_number(number: int) -> IpProtocol:
    """Mapeo fijo IP protocol number → nombre (BR-U5-18; sin inspección de puertos)."""
    if number == 6:
        return "tcp"
    if number == 17:
        return "udp"
    if number == 1:
        return "icmp"
    return "other"


@dataclass(slots=True)
class IpPacket:
    """Evento IPv4 crudo: solo campos mínimos (BR-U5-08 — sin MAC/puerto/payload)."""

    observed_at: datetime
    interface: str
    protocol: IpProtocol
    src_ip: IPv4Address
    dst_ip: IPv4Address
    packet_length_bytes: int


@dataclass(slots=True)
class ArpPacket:
    """Evento ARP crudo: request (1) y reply (2), BR-U5-09."""

    observed_at: datetime
    interface: str
    opcode: ArpOpcode
    psrc: IPv4Address
    pdst: IPv4Address
    hwsrc: str
    hwdst: str


@runtime_checkable
class PacketSource(Protocol):
    """Protocolo intercambiable de eventos (BR-U5-06)."""

    def events(self) -> Iterator[IpPacket | ArpPacket]: ...


class SimulatedSource:
    """Generador determinista: IP a ``rate`` pps + ARP 1 msg/s (FD §3.2).

    Misma terna ``(seed, rate, start_at)`` ⇒ misma secuencia de eventos
    (BR-U5-07). No duerme: la línea temporal es interna y el worker la
    consume hasta el borde de ventana (P5, MNT-02).
    """

    def __init__(
        self,
        *,
        seed: int = 42,
        rate: float = 50.0,
        interface: str = "eth0",
        start_at: datetime | None = None,
    ) -> None:
        self._seed = seed
        self._rate = rate
        self._interface = interface
        self._start_at = start_at if start_at is not None else datetime.now(UTC)

    def events(self) -> Iterator[IpPacket | ArpPacket]:
        """Iterador infinito fusionando los flujos IP y ARP por timestamp."""
        start = self._start_at
        ip_step = 1.0 / self._rate
        ip_index = 0
        arp_index = 0
        while True:
            ip_at = start + timedelta(seconds=ip_index * ip_step)
            arp_at = start + timedelta(seconds=arp_index)
            if ip_at <= arp_at:
                yield self._ip_event(ip_at, ip_index)
                ip_index += 1
            else:
                yield self._arp_event(arp_at, arp_index)
                arp_index += 1

    def _ip_event(self, at: datetime, index: int) -> IpPacket:
        seed = self._seed
        return IpPacket(
            observed_at=at,
            interface=self._interface,
            protocol=protocol_from_number(_IP_PROTOCOL_NUMBERS[(index + seed) % 4]),
            src_ip=_SRC_IPS[(index + seed) % len(_SRC_IPS)],
            dst_ip=_DST_IPS[(index * 7 + seed) % len(_DST_IPS)],
            packet_length_bytes=64 + ((seed + index * 53) % 1400),
        )

    def _arp_event(self, at: datetime, index: int) -> ArpPacket:
        ip, mac = _ARP_TABLE[(index + self._seed) % len(_ARP_TABLE)]
        opcode = 1 if index % 2 == 0 else 2
        return ArpPacket(
            observed_at=at,
            interface=self._interface,
            opcode=cast(ArpOpcode, opcode),
            psrc=ip,
            pdst=IPv4Address("10.0.0.254"),
            hwsrc=mac,
            hwdst=_BROADCAST_MAC if opcode == 1 else _ZERO_MAC,
        )


class FixtureSource:
    """Replay de eventos desde JSON versionado (tests y demo, FD §3.2).

    Cada llamada a ``events()`` relee el archivo (iterador fresco, reutilizable
    entre ventanas); las entradas ``ip_version: 6`` se descartan (IPv4 only,
    D-U5-03). Soporta ``protocol`` (nombre) o ``ip_protocol`` (número).
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def events(self) -> Iterator[IpPacket | ArpPacket]:
        entries = json.loads(self._path.read_text(encoding="utf-8"))
        for entry in entries:
            if entry.get("ip_version", 4) == 6:
                continue
            yield _parse_entry(entry)


def _parse_entry(entry: dict) -> IpPacket | ArpPacket:
    observed_at = datetime.fromisoformat(entry["observed_at"])
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)
    interface = str(entry["interface"])
    if entry["type"] == "arp":
        return ArpPacket(
            observed_at=observed_at,
            interface=interface,
            opcode=cast(ArpOpcode, int(entry["opcode"])),
            psrc=IPv4Address(entry["psrc"]),
            pdst=IPv4Address(entry["pdst"]),
            hwsrc=str(entry["hwsrc"]),
            hwdst=str(entry["hwdst"]),
        )
    protocol = (
        cast(IpProtocol, entry["protocol"])
        if "protocol" in entry
        else protocol_from_number(int(entry.get("ip_protocol", 0)))
    )
    return IpPacket(
        observed_at=observed_at,
        interface=interface,
        protocol=protocol,
        src_ip=IPv4Address(entry["src_ip"]),
        dst_ip=IPv4Address(entry["dst_ip"]),
        packet_length_bytes=int(entry["packet_length_bytes"]),
    )
