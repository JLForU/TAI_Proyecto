"""Vocabulario canónico de eventos de Sentinel (BR-11).

Usado en logs (campo ``event``), en ``InventoryEvent.type`` y en las reglas
de negocio para que todas las unidades compartan el mismo vocabulario.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["EventType", "EventName"]


class EventType(StrEnum):
    """Eventos canónicos de inventario, ciclo, alcance y condiciones."""

    ASSET_FIRST_SEEN = "asset_first_seen"
    ASSET_MISSING = "asset_missing"
    PORT_SERVICE_CHANGED = "port_service_changed"
    ARP_MAPPING_CHANGED = "arp_mapping_changed"
    DISCOVERY_CYCLE_FAILED = "discovery_cycle_failed"
    SCOPE_VIOLATION = "scope_violation"
    SENSOR_HEARTBEAT = "sensor_heartbeat"
    CONDITION_FIRING = "condition_firing"
    CONDITION_RESOLVED = "condition_resolved"


#: Alias para consumidores que piensan en nombres de evento de log.
EventName = EventType
