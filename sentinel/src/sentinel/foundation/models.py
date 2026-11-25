"""Entidades de dominio compartidas de Sentinel (P2, P7 — BR-13..BR-18).

Pydantic ``frozen=True`` (inmutables) y ``extra="forbid"`` (payload
desconocido = error, no silencio). Límites de entrada como constantes
(P2): ``MAX_BATCH_ITEMS``, ``MAX_STRING_LEN``, ``MAX_PORTS_PER_OBSERVATION``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from ipaddress import IPv4Address, IPv6Address
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)
from pydantic import ValidationError as PydanticValidationError

from sentinel.foundation.events import EventType

__all__ = [
    "MAX_BATCH_ITEMS",
    "MAX_PORTS_PER_OBSERVATION",
    "MAX_STRING_LEN",
    "AlertCondition",
    "ArpMapping",
    "ArpObservation",
    "Asset",
    "AssetStatus",
    "Batch",
    "Baseline",
    "ConditionState",
    "CycleStatus",
    "DiscoveryCycle",
    "DiscoveryObservation",
    "FlowPair",
    "InventoryEvent",
    "MACAddress",
    "OsProvenance",
    "Observation",
    "PortInfo",
    "Protocol",
    "TrafficObservation",
    "UTCDateTime",
    "Uuid",
]

# --- Constantes de límite (P2) ---------------------------------------------

MAX_BATCH_ITEMS = 1000
MAX_STRING_LEN = 255
MAX_PORTS_PER_OBSERVATION = 65535

# --- Value objects (domain-entities §1) ------------------------------------

Protocol = Literal["tcp", "udp", "icmp", "arp", "other"]
OsProvenance = Literal["observed", "inferred", "declared", "unknown"]
AssetStatus = Literal["present", "absent"]
CycleStatus = Literal["running", "completed", "partial", "timeout", "failed"]
ConditionState = Literal["baseline_establishing", "firing", "resolved", "no_data"]
Uuid = uuid.UUID


def _normalize_mac(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip().lower()
    return value


MACAddress = Annotated[
    str,
    BeforeValidator(_normalize_mac),
    StringConstraints(pattern=r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$"),
]


def _ensure_utc(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("naive datetime not allowed; expected tz-aware UTC")
        return value.astimezone(UTC)
    return value


UTCDateTime = Annotated[datetime, BeforeValidator(_ensure_utc)]


# --- Modelos base ------------------------------------------------------------


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PortInfo(_Model):
    """Puerto observado en un host (confidence: probable = solo número)."""

    port: int = Field(ge=1, le=65535)
    protocol: Protocol = "tcp"
    state: str = Field(max_length=MAX_STRING_LEN)
    service: str | None = Field(default=None, max_length=MAX_STRING_LEN)
    version: str | None = Field(default=None, max_length=MAX_STRING_LEN)
    confidence: Literal["confirmed", "probable", "unknown"] = "unknown"


class FlowPair(_Model):
    """Par origen/destino de un flujo (observaciones/logs, nunca labels)."""

    src_ip: IPv4Address | IPv6Address
    dst_ip: IPv4Address | IPv6Address


class Asset(_Model):
    """Inventario de activos (identidad estable asignada por U2)."""

    asset_id: Uuid
    ips: list[IPv4Address] = Field(min_length=1)
    mac: MACAddress | None = None
    hostname: str | None = Field(default=None, max_length=MAX_STRING_LEN)
    os_name: str | None = Field(default=None, max_length=MAX_STRING_LEN)
    os_provenance: OsProvenance = "unknown"
    status: AssetStatus
    first_seen: UTCDateTime
    last_seen: UTCDateTime
    source: Literal["discovery", "manual", "declared"]
    sensor_id: str = Field(default="sensor-0", max_length=MAX_STRING_LEN)


class DiscoveryObservation(_Model):
    """Observación de descubrimiento (U4 → U2)."""

    observed_at: UTCDateTime
    sensor_id: str = Field(default="sensor-0", max_length=MAX_STRING_LEN)
    source: Literal["discovery"] = "discovery"
    ip: IPv4Address
    mac: MACAddress | None = None
    hostname: str | None = Field(default=None, max_length=MAX_STRING_LEN)
    ports: list[PortInfo] = Field(default_factory=list, max_length=MAX_PORTS_PER_OBSERVATION)
    os_name: str | None = Field(default=None, max_length=MAX_STRING_LEN)
    os_provenance: OsProvenance = "unknown"
    method: Literal["arp", "icmp", "tcp", "nmap"]


class TrafficObservation(_Model):
    """Ventana agregada de tráfico (U5 → U2); ``window_id`` opcional (§2.4)."""

    observed_at: UTCDateTime
    sensor_id: str = Field(default="sensor-0", max_length=MAX_STRING_LEN)
    source: Literal["traffic"] = "traffic"
    window_start: UTCDateTime
    window_end: UTCDateTime
    interface: str = Field(max_length=MAX_STRING_LEN)
    protocol: Protocol
    packet_length_bytes: int = Field(ge=0)
    bytes_per_second: float = Field(ge=0.0)
    packets: int = Field(ge=0)
    flows: int = Field(ge=0)
    pairs: list[FlowPair] = Field(default_factory=list, max_length=MAX_BATCH_ITEMS)
    window_id: Uuid | None = None

    @field_validator("window_end")
    @classmethod
    def _end_after_start(cls, value: Any, info: Any) -> Any:
        start = info.data.get("window_start")
        if start is not None and value < start:
            raise ValueError("window_end must be >= window_start")
        return value


class ArpObservation(_Model):
    """Observación ARP (U5 → U2)."""

    observed_at: UTCDateTime
    sensor_id: str = Field(default="sensor-0", max_length=MAX_STRING_LEN)
    source: Literal["arp"] = "arp"
    interface: str = Field(max_length=MAX_STRING_LEN)
    opcode: Literal[1, 2]
    psrc: IPv4Address
    pdst: IPv4Address
    hwsrc: MACAddress
    hwdst: MACAddress


Observation = Annotated[
    DiscoveryObservation | TrafficObservation | ArpObservation,
    Field(discriminator="source"),
]


class Batch(_Model):
    """Lote de observaciones con cardinalidad acotada (P2)."""

    items: list[Observation] = Field(max_length=MAX_BATCH_ITEMS)
    #: U4 (FD §4): ``false`` ⇒ persistir sin ``reconcile_missing`` — un ciclo
    #: parcial/timeout jamás incrementa ``miss_count`` (ST-M2-04 AC2).
    reconcile: bool = True


class DiscoveryCycle(_Model):
    """Ejecución de descubrimiento (U4)."""

    run_id: Uuid
    status: CycleStatus
    trigger: Literal["scheduled", "manual"]
    started_at: UTCDateTime
    finished_at: UTCDateTime | None = None
    hosts_targeted: int = Field(ge=0)
    hosts_seen: int = Field(ge=0)
    error: str | None = Field(default=None, max_length=MAX_STRING_LEN)


class ArpMapping(_Model):
    """Asociación IP↔MAC (U5 → U2)."""

    ip: IPv4Address
    mac: MACAddress
    interface: str = Field(max_length=MAX_STRING_LEN)
    first_seen: UTCDateTime
    last_seen: UTCDateTime
    changed_at: UTCDateTime | None = None


class InventoryEvent(_Model):
    """Evento persistible de inventario; deduplicación por ``event_id`` (BR-17)."""

    event_id: Uuid
    type: EventType
    asset_id: Uuid | None = None
    occurred_at: UTCDateTime
    details: dict[str, str | int | float] = Field(default_factory=dict)
    severity: Literal["info", "warning", "critical"] = "info"


class AlertCondition(_Model):
    """Condición determinista R-01..R-04 (U6)."""

    condition_id: Uuid
    rule: Literal["R-01", "R-02", "R-03", "R-04"]
    state: ConditionState
    measured_value: float | None = None
    threshold: float | None = None
    fired_at: UTCDateTime | None = None
    resolved_at: UTCDateTime | None = None
    evidence: dict[str, str | int | float] = Field(default_factory=dict)


class Baseline(_Model):
    """Línea base de una métrica (la calcula U6; el tipo vive en foundation)."""

    metric_key: str = Field(max_length=MAX_STRING_LEN)
    samples: list[float] = Field(max_length=MAX_BATCH_ITEMS)
    mean: float
    variance: float = Field(ge=0.0)
    established: bool = False
    interval_seconds: int = Field(default=5, ge=1)


# Re-exportar ValidationError de pydantic bajo nombre propio para tests/UTs
# que necesitan distinguirla de la de dominio (FD §5, "Payload con campo
# desconocido → ValidationError de foundation").
ModelValidationError = PydanticValidationError
