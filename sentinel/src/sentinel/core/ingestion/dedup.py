"""Identidad estable de observaciones/eventos (ST-M4-03, Q3 FD, BR-U2-06/08).

``dedup_key = UUIDv5(NAMESPACE, sha256(contenido_normalizado))``:

- El contenido se toma del modelo **ya validado/normalizado** por Pydantic U1
  (MAC minúsculas, timestamps UTC tz-aware) ⇒ reenvíos con distinto formato
  generan el mismo UUID (BR-U2-08, PB-U2-02).
- Namespace fijo constante en código (BR-U2-09).
"""

from __future__ import annotations

import hashlib
import json
import uuid

from sentinel.foundation.models import (
    ArpObservation,
    DiscoveryObservation,
    Observation,
    TrafficObservation,
)

__all__ = ["EVENT_NAMESPACE", "OBSERVATION_NAMESPACE", "dedup_key", "event_id_for"]

#: Namespace determinista para claves de observación.
OBSERVATION_NAMESPACE = uuid.UUID("1b671a64-40d5-491e-99b0-da01ff1f3341")

#: Namespace determinista para event_id de inventario (mismo esquema que
#: ``InventoryService`` en FD/domain-entities).
EVENT_NAMESPACE = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")


def _content(item: Observation) -> dict[str, object]:
    if isinstance(item, DiscoveryObservation):
        return {
            "source": "discovery",
            "sensor_id": item.sensor_id,
            "observed_at": item.observed_at.isoformat(),
            "ip": str(item.ip),
            "mac": item.mac,
            "hostname": item.hostname,
            "method": item.method,
            "os_name": item.os_name,
            "os_provenance": item.os_provenance,
            "ports": [
                {"port": p.port, "protocol": p.protocol, "state": p.state, "service": p.service}
                for p in item.ports
            ],
        }
    if isinstance(item, TrafficObservation):
        return {
            "source": "traffic",
            "sensor_id": item.sensor_id,
            "observed_at": item.observed_at.isoformat(),
            "window_start": item.window_start.isoformat(),
            "window_end": item.window_end.isoformat(),
            "interface": item.interface,
            "protocol": item.protocol,
            "packet_length_bytes": item.packet_length_bytes,
            "bytes_per_second": item.bytes_per_second,
            "packets": item.packets,
            "flows": item.flows,
            "pairs": [{"src_ip": str(p.src_ip), "dst_ip": str(p.dst_ip)} for p in item.pairs],
            "window_id": str(item.window_id) if item.window_id else None,
        }
    if isinstance(item, ArpObservation):
        return {
            "source": "arp",
            "sensor_id": item.sensor_id,
            "observed_at": item.observed_at.isoformat(),
            "interface": item.interface,
            "opcode": item.opcode,
            "psrc": str(item.psrc),
            "pdst": str(item.pdst),
            "hwsrc": item.hwsrc,
            "hwdst": item.hwdst,
        }
    raise TypeError(f"unknown observation type: {type(item)!r}")  # pragma: no cover


def _sha(content: dict[str, object]) -> str:
    blob = json.dumps(content, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def dedup_key(item: Observation) -> str:
    """UUIDv5 estable del contenido normalizado de la observación."""
    return str(uuid.uuid5(OBSERVATION_NAMESPACE, _sha(_content(item))))


def event_id_for(event_type: str, asset_id: str | None, occurred_at: str, details: dict) -> str:
    """UUIDv5 estable de un evento (contenido normalizado)."""
    content = json.dumps(
        {
            "type": event_type,
            "asset_id": asset_id,
            "occurred_at": occurred_at,
            "details": {k: details[k] for k in sorted(details)},
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return str(uuid.uuid5(EVENT_NAMESPACE, content))
