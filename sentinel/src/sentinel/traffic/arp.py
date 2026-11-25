"""Dominio ARP (U5, BR-U5-09/19/22, D-U5-08): proyección y tasa pura.

Sin estado de mapping IP↔MAC (delegado en U2, D-U5-09) y sin campo de tasa
en los contratos U1 (BR-U5-22): la tasa solo vive en el log vía
:func:`arp_rate` al cierre de cada ventana.
"""

from __future__ import annotations

from collections.abc import Sequence

from sentinel.foundation.models import ArpObservation

from .source import ArpPacket

__all__ = ["arp_rate", "to_arp_observations"]


def to_arp_observations(packets: Sequence[ArpPacket], *, sensor_id: str) -> list[ArpObservation]:
    """1 ``ArpObservation`` por mensaje ARP — frontera U1 (BR-U5-09)."""
    return [
        ArpObservation(
            observed_at=packet.observed_at,
            sensor_id=sensor_id,
            interface=packet.interface,
            opcode=packet.opcode,
            psrc=packet.psrc,
            pdst=packet.pdst,
            hwsrc=packet.hwsrc,
            hwdst=packet.hwdst,
        )
        for packet in packets
    ]


def arp_rate(count: int, window_seconds: float) -> float:
    """Tasa de mensajes ARP por ventana — función pura sin I/O (BR-U5-19)."""
    return count / window_seconds
