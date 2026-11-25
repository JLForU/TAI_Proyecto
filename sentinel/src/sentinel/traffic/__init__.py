"""U5 — Traffic Sensor & ARP observation.

Frontera (BR-U5-32, unit-of-work §imports): todo el paquete importa solo
``sentinel.foundation``, httpx y stdlib — nunca ``sentinel.core`` ni
``sqlite3``. Las historias ST-M3-01..06 son documented-only; el simulador,
los fixtures y los tests son el soporte construido de la unidad.
"""

from __future__ import annotations

from sentinel.traffic.aggregator import (
    MAX_PAIRS_PER_OBSERVATION,
    WindowAccumulator,
    to_observations,
)
from sentinel.traffic.arp import arp_rate, to_arp_observations
from sentinel.traffic.config import TrafficSettings, load_traffic_settings
from sentinel.traffic.source import (
    ArpPacket,
    FixtureSource,
    IpPacket,
    PacketSource,
    SimulatedSource,
)
from sentinel.traffic.worker import SensorState, WindowResult, run_window

__all__ = [
    "MAX_PAIRS_PER_OBSERVATION",
    "ArpPacket",
    "FixtureSource",
    "IpPacket",
    "PacketSource",
    "SensorState",
    "SimulatedSource",
    "TrafficSettings",
    "WindowAccumulator",
    "WindowResult",
    "arp_rate",
    "load_traffic_settings",
    "run_window",
    "to_arp_observations",
    "to_observations",
]
