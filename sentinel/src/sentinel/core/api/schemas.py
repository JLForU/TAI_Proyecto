"""Schemas Pydantic de la API de U2 (respuestas ``/api/v1``).

Solo Pydantic (sin FastAPI): los servicios pueden devolver estos tipos.
"""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from sentinel.core.ingestion.service import IngestResult

__all__ = [
    "AlertOut",
    "AssetDetail",
    "AssetSummary",
    "DiscoveryRequest",
    "DiscoveryRunStatus",
    "EventOut",
    "HealthStatus",
    "IngestResult",
    "ObservationOut",
    "Page",
]

T = TypeVar("T")


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True)


class Page(_Model, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class AssetSummary(_Model):
    asset_id: str
    mac: str | None = None
    ips: list[str]
    hostname: str | None = None
    status: Literal["present", "absent"]
    first_seen: str
    last_seen: str


class ObservationOut(_Model):
    dedup_key: str
    source: str
    kind: str
    sensor_id: str | None = None
    observed_at: str
    payload: dict = Field(default_factory=dict)


class EventOut(_Model):
    event_id: str
    type: str
    asset_id: str | None = None
    severity: str
    rule: str | None = None
    occurred_at: str
    details: dict = Field(default_factory=dict)


class AssetDetail(AssetSummary):
    os_name: str | None = None
    os_provenance: str = "unknown"
    recent_observations: list[ObservationOut] = Field(default_factory=list)
    recent_events: list[EventOut] = Field(default_factory=list)


class AlertOut(_Model):
    alert_id: str
    condition_id: str
    rule: str
    metric_key: str | None = None
    asset_id: str | None = None
    state: str
    measured_value: float | None = None
    threshold: float | None = None
    fired_at: str
    resolved_at: str | None = None


class HealthStatus(_Model):
    status: Literal["up", "degraded"]
    uptime_seconds: float
    db_connected: bool
    last_ingest_at: str | None = None
    sensor_heartbeats: dict[str, str] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)
    last_discovery_run: dict | None = None


class DiscoveryRequest(_Model):
    hosts: list[str] = Field(min_length=1, max_length=1000)
    timeout_seconds: int = Field(default=30, ge=1, le=3600)


class DiscoveryRunStatus(_Model):
    run_id: str
    status: str
    started_at: str
    finished_at: str | None = None
    hosts_seen: int | None = None
    error: str | None = None
