"""View models de presentación de la GUI (FD §2/§4 de domain-entities).

Dataclasses puros: convierten los schemas Pydantic de U2 en formas listas
para las plantillas, con etiquetas ES de presentación. Sin I/O, sin
FastAPI — testeables en aislamiento (MNT-02).
"""

from __future__ import annotations

import math
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Generic, Literal, TypeVar

from sentinel.core.api.schemas import (
    AlertOut,
    AssetDetail,
    AssetSummary,
    EventOut,
    HealthStatus,
    ObservationOut,
)

__all__ = [
    "ArpMappingVM",
    "AssetDetailVM",
    "AssetRowVM",
    "DiscoveryRunVM",
    "ErrorVM",
    "HealthVM",
    "PageVM",
    "SensorVM",
    "TimelineEntryVM",
    "TrafficPairVM",
    "TrafficSummaryVM",
]

#: Sin heartbeat más antiguo que esto ⇒ badge "sensor caído" (BR-U3-17).
HEARTBEAT_STALE_SECONDS = 300.0

_PROVENANCE_LABELS = {
    "observed": "observado",
    "inferred": "inferido",
    "declared": "declarado",
    "unknown": "desconocido",
}

_STATUS_LABELS = {"present": "presente", "absent": "ausente"}

T = TypeVar("T")


def _provenance_label(provenance: str) -> str:
    return _PROVENANCE_LABELS.get(provenance, "desconocido")


def _traffic_pair_name(pair: dict) -> str:
    src = pair.get("src_ip", "?")
    dst = pair.get("dst_ip", "?")
    return f"{src} → {dst}"


@dataclass(frozen=True)
class PageVM(Generic[T]):
    """Página de resultados (BR-U3-05: total ⇒ ``pages = ceil(total/limit)``)."""

    items: list[T]
    page: int
    pages: int
    total: int
    limit: int
    offset: int

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    @classmethod
    def build(cls, items: list[T], *, page: int, total: int, limit: int) -> PageVM[T]:
        pages = max(1, math.ceil(total / limit)) if total else 1
        return cls(
            items=items,
            page=page,
            pages=pages,
            total=total,
            limit=limit,
            offset=(page - 1) * limit,
        )


@dataclass(frozen=True)
class AssetRowVM:
    """Fila del inventario (N+1 enriquecida con el detalle, FQ1)."""

    asset_id: str
    ips: list[str]
    mac: str | None
    hostname: str | None
    os_label: str
    os_provenance: str
    provenance_label: str
    last_seen: str
    status: str
    status_label: str
    sources: list[str]

    @classmethod
    def from_detail(cls, detail: AssetDetail) -> AssetRowVM:
        sources = sorted({o.source for o in detail.recent_observations})
        return cls(
            asset_id=detail.asset_id,
            ips=list(detail.ips),
            mac=detail.mac,
            hostname=detail.hostname,
            os_label=detail.os_name or "desconocido",
            os_provenance=detail.os_provenance,
            provenance_label=_provenance_label(detail.os_provenance),
            last_seen=detail.last_seen,
            status=detail.status,
            status_label=_STATUS_LABELS.get(detail.status, detail.status),
            sources=sources,
        )

    @classmethod
    def from_summary_with_detail(
        cls, summary: AssetSummary, detail: AssetDetail | None
    ) -> AssetRowVM:
        """Detalle ausente (404 transitorio) ⇒ fila desde el summary sin OS."""
        if detail is not None:
            return cls.from_detail(detail)
        sources: list[str] = []
        return cls(
            asset_id=summary.asset_id,
            ips=list(summary.ips),
            mac=summary.mac,
            hostname=summary.hostname,
            os_label="desconocido",
            os_provenance="unknown",
            provenance_label="desconocido",
            last_seen=summary.last_seen,
            status=summary.status,
            status_label=_STATUS_LABELS.get(summary.status, summary.status),
            sources=sources,
        )


@dataclass(frozen=True)
class TrafficPairVM:
    pair: str
    bytes_per_second: float | None


@dataclass(frozen=True)
class TrafficSummaryVM:
    """``available=False`` ⇒ la plantilla pinta "sin datos" (nunca 0)."""

    available: bool
    bytes_per_second_max: float | None
    pairs: list[TrafficPairVM]
    window: str


@dataclass(frozen=True)
class ArpMappingVM:
    ip: str
    mac: str
    observed_at: str


def _traffic_summary(observations: Iterable[ObservationOut]) -> TrafficSummaryVM:
    rows = [o for o in observations if o.source == "traffic"]
    if not rows:
        return TrafficSummaryVM(False, None, [], "")
    bps_values = [
        float(o.payload["bytes_per_second"])
        for o in rows
        if o.payload.get("bytes_per_second") is not None
    ]
    pairs: list[TrafficPairVM] = []
    seen: set[str] = set()
    for o in rows:
        bps = o.payload.get("bytes_per_second")
        bps_f = float(bps) if bps is not None else None
        for pair in o.payload.get("pairs") or []:
            name = _traffic_pair_name(pair)
            if name in seen:
                continue
            seen.add(name)
            pairs.append(TrafficPairVM(pair=name, bytes_per_second=bps_f))
    starts = [str(o.payload["window_start"]) for o in rows if o.payload.get("window_start")]
    ends = [str(o.payload["window_end"]) for o in rows if o.payload.get("window_end")]
    if starts and ends:
        window = f"{min(starts)} – {max(ends)}"
    else:
        observed = sorted(o.observed_at for o in rows)
        window = f"{observed[0]} – {observed[-1]}"
    return TrafficSummaryVM(
        available=True,
        bytes_per_second_max=max(bps_values) if bps_values else None,
        pairs=pairs,
        window=window,
    )


def _arp_mappings(observations: Iterable[ObservationOut]) -> list[ArpMappingVM]:
    rows: list[ArpMappingVM] = []
    for o in observations:
        if o.source != "arp":
            continue
        ip = o.payload.get("psrc") or o.payload.get("ip")
        mac = o.payload.get("hwsrc") or o.payload.get("mac")
        if ip and mac:
            rows.append(ArpMappingVM(ip=str(ip), mac=str(mac), observed_at=o.observed_at))
    return rows


@dataclass(frozen=True)
class AssetDetailVM:
    """Detalle del activo: 4 secciones del AC ``-k sections``."""

    summary: AssetRowVM
    os_name: str | None
    os_provenance: str
    observations: list[ObservationOut]
    events: list[EventOut]
    traffic: TrafficSummaryVM
    arp: list[ArpMappingVM]

    @classmethod
    def from_detail(cls, detail: AssetDetail) -> AssetDetailVM:
        return cls(
            summary=AssetRowVM.from_detail(detail),
            os_name=detail.os_name,
            os_provenance=detail.os_provenance,
            observations=list(detail.recent_observations),
            events=list(detail.recent_events),
            traffic=_traffic_summary(detail.recent_observations),
            arp=_arp_mappings(detail.recent_observations),
        )


@dataclass(frozen=True)
class TimelineEntryVM:
    """Entrada unificada de la línea de tiempo (eventos + alertas)."""

    kind: Literal["event", "alert"]
    when: str
    title: str
    severity_or_state: str
    asset_id: str | None
    rule: str | None
    detail: str
    resolved_at: str | None

    @classmethod
    def from_event(cls, event: EventOut) -> TimelineEntryVM:
        details = ", ".join(f"{k}={v}" for k, v in sorted(event.details.items()))
        return cls(
            kind="event",
            when=event.occurred_at,
            title=event.type,
            severity_or_state=event.severity,
            asset_id=event.asset_id,
            rule=event.rule,
            detail=details,
            resolved_at=None,
        )

    @classmethod
    def from_alert(cls, alert: AlertOut) -> TimelineEntryVM:
        parts = []
        if alert.metric_key:
            parts.append(f"metric={alert.metric_key}")
        if alert.measured_value is not None:
            parts.append(f"measured={alert.measured_value}")
        if alert.threshold is not None:
            parts.append(f"threshold={alert.threshold}")
        return cls(
            kind="alert",
            when=alert.fired_at,
            title=alert.rule,
            severity_or_state=alert.state,
            asset_id=alert.asset_id,
            rule=alert.rule,
            detail=", ".join(parts),
            resolved_at=alert.resolved_at,
        )


@dataclass(frozen=True)
class SensorVM:
    sensor_id: str
    last_seen: str
    down: bool


@dataclass(frozen=True)
class HealthVM:
    """Salud derivada del Core; nunca presenta vacío como "red sin activos"."""

    status: str
    uptime_seconds: float
    last_ingest_at: str | None
    last_cycle_at: str | None
    sensors: list[SensorVM]
    counts: dict[str, int]
    db_connected: bool

    @classmethod
    def from_status(
        cls,
        health: HealthStatus,
        *,
        now_epoch: float | None = None,
        stale_after: float = HEARTBEAT_STALE_SECONDS,
    ) -> HealthVM:
        now = now_epoch if now_epoch is not None else time.time()
        sensors: list[SensorVM] = []
        for sensor_id, last_seen in sorted(health.sensor_heartbeats.items()):
            down = True
            try:
                seen_epoch = datetime.fromisoformat(last_seen).timestamp()
                down = (now - seen_epoch) > stale_after
            except ValueError:
                down = True
            sensors.append(SensorVM(sensor_id=sensor_id, last_seen=last_seen, down=down))
        last_run = health.last_discovery_run or {}
        last_cycle = last_run.get("finished_at") or last_run.get("started_at")
        return cls(
            status=health.status,
            uptime_seconds=health.uptime_seconds,
            last_ingest_at=health.last_ingest_at,
            last_cycle_at=str(last_cycle) if last_cycle else None,
            sensors=sensors,
            counts=dict(health.counts),
            db_connected=health.db_connected,
        )


@dataclass(frozen=True)
class DiscoveryRunVM:
    """Estado del run de discovery + mensaje localizado para la vista."""

    run_id: str
    status: str
    started_at: str
    finished_at: str | None
    hosts_seen: int | None
    error: str | None
    message: str = ""

    @property
    def poll_state(self) -> str:
        """``active`` mientras corre; ``stopped`` en estado terminal (P1)."""
        return "active" if self.status == "running" else "stopped"


@dataclass(frozen=True)
class ErrorVM:
    """Página de error de la GUI (404/409/422/502/500 — FD §5)."""

    status: int
    title: str
    detail: str
    code: str | None = None
