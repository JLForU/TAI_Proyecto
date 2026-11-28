"""``ResetService`` — borra los datos derivados del escenario (no los pods).

El escenario vive en SQLite: inventario, observaciones, eventos, alertas,
baselines y runs de discovery. Los contenedores/pods de la red son externos a
Sentinel y **nunca** se tocan desde aquí. Se rechaza el reset si hay un ciclo
de discovery en curso para que el run no repueble los datos justo después.

Orden de borrado respeta las FK (hijos antes que ``assets``) y todo ocurre en
una única transacción serializada por ``Database.write``.
"""

from __future__ import annotations

import sqlite3

from sentinel.core.api.schemas import ResetResult
from sentinel.core.db.database import Database
from sentinel.core.db.repos.discovery_runs import DiscoveryRunRepository
from sentinel.core.errors import ConflictError

__all__ = ["RESET_TABLES", "ResetService"]

#: Hijos primero: events/observations/asset_ips referencian assets.
RESET_TABLES: tuple[str, ...] = (
    "events",
    "observations",
    "alerts",
    "asset_ips",
    "discovery_runs",
    "baselines",
    "assets",
)


class ResetService:
    """Borra el escenario completo en una transacción o falla sin cambios."""

    def __init__(
        self,
        db: Database,
        *,
        runs: DiscoveryRunRepository | None = None,
    ) -> None:
        self._db = db
        self._runs = runs or DiscoveryRunRepository()

    def reset(self) -> ResetResult:
        with self._db.write() as conn:
            if self._runs.any_running(conn):
                raise ConflictError("cannot reset while discovery is running")
            deleted = {table: _count(conn, table) for table in RESET_TABLES}
            for table in RESET_TABLES:
                conn.execute(f"DELETE FROM {table}")
        return ResetResult(deleted=deleted, total=sum(deleted.values()))


def _count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
