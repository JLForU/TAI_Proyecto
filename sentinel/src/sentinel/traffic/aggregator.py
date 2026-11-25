"""Agregación de ventanas tumbling (U5, BR-U5-12..18, P2/P12, D-U5-01/02).

Estado por ventana en dicts O(1) por protocolo/pares; cierre epoch-aligned
UTC; proyección **una vez por ventana** a ``TrafficObservation`` (frontera
Pydantic U1, P5/P6). El guard de emisión monótono vive en ``worker`` (P2).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from ipaddress import IPv4Address

from sentinel.foundation.models import FlowPair, TrafficObservation

from .source import ArpPacket, IpPacket, IpProtocol

__all__ = [
    "MAX_PAIRS_PER_OBSERVATION",
    "WindowAccumulator",
    "to_observations",
    "window_bounds",
    "window_id_for",
]

#: Muestra de pares acotada por observación (BR-U5-16, P13).
MAX_PAIRS_PER_OBSERVATION = 100

#: Namespace fijo para el ``window_id`` determinista (D-U5-02).
_WINDOW_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "sentinel.traffic.window")


def window_bounds(now: datetime, window_seconds: int) -> tuple[datetime, datetime]:
    """Ventana tumbling epoch-aligned: ``[floor(now/W)*W, +W)`` (BR-U5-12)."""
    epoch = int(now.timestamp())
    start_epoch = epoch - (epoch % window_seconds)
    start = datetime.fromtimestamp(start_epoch, tz=UTC)
    return start, start + timedelta(seconds=window_seconds)


def window_id_for(
    sensor_id: str, window_start: datetime, interface: str, protocol: str
) -> uuid.UUID:
    """UUIDv5 estable del contenido de la ventana (D-U5-02)."""
    name = f"{sensor_id}|{window_start.isoformat()}|{interface}|{protocol}"
    return uuid.uuid5(_WINDOW_NAMESPACE, name)


@dataclass(slots=True)
class WindowAccumulator:
    """Estado interno por ventana; se descarta al cerrar (domain-entities §1.5)."""

    window_start: datetime
    window_end: datetime
    interface: str
    packets_by_protocol: dict[IpProtocol, int] = field(default_factory=dict)
    bytes_by_protocol: dict[IpProtocol, int] = field(default_factory=dict)
    pairs_by_protocol: dict[IpProtocol, dict[tuple[IPv4Address, IPv4Address], int]] = field(
        default_factory=dict
    )
    arp_count: int = 0

    def add(self, event: IpPacket | ArpPacket) -> None:
        """Acumula un evento (O(1) por entrada)."""
        if isinstance(event, ArpPacket):
            self.arp_count += 1
            return
        protocol = event.protocol
        self.packets_by_protocol[protocol] = self.packets_by_protocol.get(protocol, 0) + 1
        self.bytes_by_protocol[protocol] = (
            self.bytes_by_protocol.get(protocol, 0) + event.packet_length_bytes
        )
        pairs = self.pairs_by_protocol.setdefault(protocol, {})
        key = (event.src_ip, event.dst_ip)
        pairs[key] = pairs.get(key, 0) + 1

    @property
    def total_packets(self) -> int:
        return sum(self.packets_by_protocol.values())


def to_observations(accumulator: WindowAccumulator, *, sensor_id: str) -> list[TrafficObservation]:
    """Proyección a contratos U1 (domain-entities §2.1).

    Ventana sin paquetes ⇒ 1 observación cero ``protocol="other"`` con
    ``pairs=[]`` (heartbeat factual, D-U5-01). Con tráfico ⇒ 1 observación
    por protocolo con ≥1 paquete, ``pairs`` acotado y orden determinista
    (BR-U5-16), ``window_id`` uuid5 (D-U5-02).
    """
    duration = (accumulator.window_end - accumulator.window_start).total_seconds()
    if accumulator.total_packets == 0:
        return [
            TrafficObservation(
                observed_at=accumulator.window_end,
                sensor_id=sensor_id,
                window_start=accumulator.window_start,
                window_end=accumulator.window_end,
                interface=accumulator.interface,
                protocol="other",
                packet_length_bytes=0,
                bytes_per_second=0.0,
                packets=0,
                flows=0,
                pairs=[],
                window_id=window_id_for(
                    sensor_id, accumulator.window_start, accumulator.interface, "other"
                ),
            )
        ]

    observations: list[TrafficObservation] = []
    for protocol in sorted(accumulator.packets_by_protocol):
        packets = accumulator.packets_by_protocol[protocol]
        total_bytes = accumulator.bytes_by_protocol[protocol]
        counts = accumulator.pairs_by_protocol[protocol]
        # orden: packets desc, src asc, dst asc (BR-U5-16)
        ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0][0], kv[0][1]))
        pairs = [
            FlowPair(src_ip=src, dst_ip=dst)
            for (src, dst), _ in ordered[:MAX_PAIRS_PER_OBSERVATION]
        ]
        observations.append(
            TrafficObservation(
                observed_at=accumulator.window_end,
                sensor_id=sensor_id,
                window_start=accumulator.window_start,
                window_end=accumulator.window_end,
                interface=accumulator.interface,
                protocol=protocol,
                packet_length_bytes=total_bytes,
                bytes_per_second=total_bytes / duration,
                packets=packets,
                flows=len(counts),
                pairs=pairs,
                window_id=window_id_for(
                    sensor_id, accumulator.window_start, accumulator.interface, protocol
                ),
            )
        )
    return observations
