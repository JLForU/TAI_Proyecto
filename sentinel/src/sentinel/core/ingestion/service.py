"""IngestionService — ingesta idempotente de observaciones (ST-M4-01/03/04).

Flujo (FD §3.1): validar (Pydantic U1) → normalizar (modelos canónicos) →
``dedup_key = UUIDv5(sha256(contenido normalizado))`` → transacción única
(observations + assets + eventos de inventario) → evidencia JSON Lines →
``IngestResult``. Reenviar el mismo lote no cambia los contadores (BR-U2-07).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from pydantic import BaseModel, ConfigDict

from sentinel.foundation.errors import SentinelError, StorageError
from sentinel.foundation.models import (
    ArpObservation,
    Batch,
    DiscoveryObservation,
    Observation,
    TrafficObservation,
)

from .. import evidence as evidence_mod
from ..db.database import Database
from ..db.repos.assets import AssetRepository
from ..db.repos.events import EventRepository
from ..db.repos.observations import ObservationRepository
from ..inventory.service import InventoryChange, InventoryService
from .dedup import dedup_key

__all__ = ["IngestionService", "IngestResult"]


class IngestResult(BaseModel):
    """Respuesta 202 de ``POST /api/v1/ingest`` (component-methods §2)."""

    model_config = ConfigDict(frozen=True)

    ingest_id: str
    accepted: int
    deduplicated: int
    events_persisted: int


def _ip_of(item: Observation) -> str | None:
    if isinstance(item, DiscoveryObservation):
        return str(item.ip)
    if isinstance(item, ArpObservation):
        return str(item.psrc)
    if isinstance(item, TrafficObservation):
        return str(item.pairs[0].src_ip) if item.pairs else None
    return None  # pragma: no cover - unión cerrada


def _kind_of(item: Observation) -> str:
    if isinstance(item, DiscoveryObservation):
        return item.method
    if isinstance(item, ArpObservation):
        return "arp"
    return item.protocol


def _protocol_of(item: Observation) -> str | None:
    if isinstance(item, DiscoveryObservation):
        return item.method if item.method in {"tcp", "icmp"} else None
    if isinstance(item, ArpObservation):
        return "arp"
    return str(item.protocol)


def _now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


class IngestionService:
    def __init__(
        self,
        db: Database,
        *,
        inventory: InventoryService | None = None,
        observations: ObservationRepository | None = None,
        assets: AssetRepository | None = None,
        events: EventRepository | None = None,
        missing_cycles: int = 3,
        on_accepted: Callable[[list[Observation]], None] | None = None,
    ) -> None:
        self._db = db
        self._assets = assets or AssetRepository()
        self._observations = observations or ObservationRepository()
        self._events = events or EventRepository()
        self._inventory = inventory or InventoryService(self._assets, self._events)
        self._missing_cycles = missing_cycles
        self._on_accepted = on_accepted

    def process(self, batch: Batch) -> IngestResult:
        """Procesa un lote completo en una transacción (P6, REL-04)."""
        now = _now_iso()
        ingest_id = str(uuid.uuid4())
        accepted = 0
        deduplicated = 0
        accepted_obs: list[tuple[Observation, str | None, str]] = []
        changes: list[InventoryChange] = []
        seen_assets: set[str] = set()
        has_discovery = any(isinstance(i, DiscoveryObservation) for i in batch.items)
        events_persisted = 0

        try:
            with self._db.write() as conn:
                for item in batch.items:
                    ip = _ip_of(item)
                    asset_id: str | None = None
                    if ip is not None:
                        arp_mac = item.hwsrc if isinstance(item, ArpObservation) else None
                        asset_id, item_changes = self._inventory.observe(
                            conn,
                            ip=ip,
                            mac=getattr(item, "mac", None) or arp_mac,
                            hostname=getattr(item, "hostname", None),
                            os_name=getattr(item, "os_name", None),
                            os_provenance=getattr(item, "os_provenance", "unknown"),
                            source=item.source,
                            sensor_id=item.sensor_id,
                            now=now,
                            create_if_missing=isinstance(item, DiscoveryObservation),
                        )
                        changes.extend(item_changes)
                        if asset_id is not None:
                            seen_assets.add(asset_id)

                    inserted = self._observations.insert_ignore(
                        conn,
                        {
                            "dedup_key": dedup_key(item),
                            "asset_id": asset_id,
                            "source": str(item.source),
                            "kind": _kind_of(item),
                            "sensor_id": item.sensor_id,
                            "observed_at": item.observed_at.isoformat(),
                            "received_at": now,
                            "payload": item.model_dump(mode="json"),
                        },
                    )
                    if inserted:
                        accepted += 1
                        accepted_obs.append((item, asset_id, ip or ""))
                    else:
                        deduplicated += 1

                if has_discovery and batch.reconcile:
                    changes.extend(
                        self._inventory.reconcile_missing(
                            conn,
                            seen_asset_ids=seen_assets,
                            missing_cycles=self._missing_cycles,
                            now=now,
                        )
                    )
                events_persisted = self._inventory.persist_changes(conn, changes)
        except SentinelError:
            raise
        except Exception as exc:
            # Rollback total (ya aplicado por Database.write) ⇒ 503 en la API (P5).
            raise StorageError(f"ingest transaction failed: {exc}") from exc

        for item, asset_id, ip in accepted_obs:
            evidence_mod.emit(
                "observation",
                f"observation_{item.source}",
                asset=asset_id or ip,
                pair=ip or None,
                method=_kind_of(item),
                protocol=_protocol_of(item),
                result="persisted",
                sensor_id=item.sensor_id,
            )
        for change in changes:
            details = change.details
            evidence_mod.emit(
                "event",
                str(change.type),
                asset=change.asset_id,
                pair=str(details["ip"]) if details.get("ip") else None,
                condition=str(change.type),
                threshold=details.get("threshold"),
                measured_value=details.get("miss_count"),
                result=str(change.type),
                severity=change.severity,
            )

        # Post-commit (FD §3.2, BR-U6-14/15): solo observaciones aceptadas;
        # cualquier fallo se traga para no romper el 202.
        if self._on_accepted and accepted_obs:
            try:
                self._on_accepted([item for item, _, _ in accepted_obs])
            except Exception:  # noqa: BLE001 - degradación deliberada (P1)
                from sentinel.foundation.logging import get_logger

                get_logger("core.ingestion").warning(
                    "ingestion hook failed",
                    extra={"event": "ingestion_hook_failed"},
                )

        return IngestResult(
            ingest_id=ingest_id,
            accepted=accepted,
            deduplicated=deduplicated,
            events_persisted=events_persisted,
        )
