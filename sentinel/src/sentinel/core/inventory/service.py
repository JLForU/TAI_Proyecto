"""InventoryService — reconciliación de activos (ST-M4-04, BR-U2-13..17, Q4 FD).

- Primera vez que se ve una IP ⇒ activo + evento ``asset_first_seen``.
- Cada observación ⇒ ``last_seen``; cambio de MAC ⇒ ``arp_mapping_changed``.
- Tras un ciclo de descubrimiento completado, los activos presentes no vistos
  acumulan ``miss_count``; al llegar a ``missing_cycles`` ⇒ ``absent`` +
  ``asset_missing`` (una sola vez). Solo ciclos con observaciones de
  discovery cuentan (BR-U2-15).
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass, field
from typing import Any

from sentinel.foundation.events import EventType

from ..db.repos.assets import AssetRepository
from ..db.repos.events import EventRepository

__all__ = ["InventoryService", "InventoryChange"]

_NAMESPACE = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")


@dataclass
class InventoryChange:
    """Evento de inventario generado (se persiste con ``event_id`` calculado)."""

    type: EventType
    asset_id: str | None
    occurred_at: str
    details: dict[str, Any] = field(default_factory=dict)
    severity: str = "info"

    @property
    def event_id(self) -> str:
        content = f"{self.type}|{self.asset_id}|{self.occurred_at}|{sorted(self.details.items())}"
        return str(uuid.uuid5(_NAMESPACE, content))


class InventoryService:
    def __init__(self, assets: AssetRepository, events: EventRepository) -> None:
        self._assets = assets
        self._events = events

    def observe(
        self,
        conn: sqlite3.Connection,
        *,
        ip: str,
        mac: str | None,
        hostname: str | None,
        os_name: str | None,
        os_provenance: str,
        source: str,
        sensor_id: str | None,
        now: str,
        create_if_missing: bool,
    ) -> tuple[str | None, list[InventoryChange]]:
        """Registra la observación de una IP. Devuelve ``(asset_id, cambios)``.

        ``create_if_missing`` solo para discovery (los assets se crean desde
        discovery; traffic/arp solo tocan activos existentes).
        """
        changes: list[InventoryChange] = []
        asset_id = self._assets.find_asset_id_by_ip(conn, ip)
        if asset_id is None:
            if not create_if_missing:
                return None, changes
            asset_id = self._assets.create(
                conn,
                ip=ip,
                mac=mac,
                hostname=hostname,
                os_name=os_name,
                os_provenance=os_provenance,
                source=source,
                sensor_id=sensor_id,
                now=now,
            )
            changes.append(
                InventoryChange(
                    type=EventType.ASSET_FIRST_SEEN,
                    asset_id=asset_id,
                    occurred_at=now,
                    details={"ip": ip, "mac": mac or ""},
                )
            )
            return asset_id, changes

        mac_changed = self._assets.touch(
            conn,
            asset_id=asset_id,
            ip=ip,
            mac=mac,
            hostname=hostname,
            os_name=os_name,
            now=now,
        )
        if mac_changed:
            changes.append(
                InventoryChange(
                    type=EventType.ARP_MAPPING_CHANGED,
                    asset_id=asset_id,
                    occurred_at=now,
                    details={"ip": ip, "mac": mac or ""},
                    severity="warning",
                )
            )
        return asset_id, changes

    def reconcile_missing(
        self,
        conn: sqlite3.Connection,
        *,
        seen_asset_ids: set[str],
        missing_cycles: int,
        now: str,
    ) -> list[InventoryChange]:
        """Aplica el umbral de ausencia a los activos no vistos en el ciclo."""
        changes: list[InventoryChange] = []
        for row in self._assets.present_assets(conn):
            asset_id = str(row["asset_id"])
            if asset_id in seen_asset_ids:
                continue
            miss = self._assets.bump_miss(conn, asset_id)
            if miss >= missing_cycles:
                self._assets.mark_absent(conn, asset_id)
                changes.append(
                    InventoryChange(
                        type=EventType.ASSET_MISSING,
                        asset_id=asset_id,
                        occurred_at=now,
                        details={"miss_count": miss, "threshold": missing_cycles},
                        severity="warning",
                    )
                )
        return changes

    def persist_changes(self, conn: sqlite3.Connection, changes: list[InventoryChange]) -> int:
        """Persiste los cambios como eventos (INSERT OR IGNORE). Nuevos = count."""
        persisted = 0
        for change in changes:
            inserted = self._events.save_ignore(
                conn,
                {
                    "event_id": change.event_id,
                    "type": str(change.type),
                    "asset_id": change.asset_id,
                    "severity": change.severity,
                    "rule": None,
                    "occurred_at": change.occurred_at,
                    "details": change.details,
                    "created_at": change.occurred_at,
                },
            )
            if inserted:
                persisted += 1
        return persisted
