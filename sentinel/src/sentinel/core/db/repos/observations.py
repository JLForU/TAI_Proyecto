"""Repositorio de observaciones (dedup por ``dedup_key``, BR-U2-06/07)."""

from __future__ import annotations

import sqlite3
from typing import Any

from ._common import dumps

__all__ = ["ObservationRepository"]


class ObservationRepository:
    def insert_ignore(self, conn: sqlite3.Connection, obs: dict[str, Any]) -> bool:
        """Inserta si la clave no existe. Devuelve ``True`` si fue aceptada."""
        cur = conn.execute(
            "INSERT OR IGNORE INTO observations"
            " (dedup_key, asset_id, source, kind, sensor_id, observed_at, received_at, payload)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                obs["dedup_key"],
                obs["asset_id"],
                obs["source"],
                obs["kind"],
                obs.get("sensor_id"),
                obs["observed_at"],
                obs["received_at"],
                dumps(obs.get("payload", {})),
            ),
        )
        return cur.rowcount > 0

    def list_by_asset(
        self,
        conn: sqlite3.Connection,
        asset_id: str,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 200,
    ) -> list[sqlite3.Row]:
        sql = "SELECT * FROM observations WHERE asset_id = ?"
        params: list[Any] = [asset_id]
        if date_from:
            sql += " AND observed_at >= ?"
            params.append(date_from)
        if date_to:
            sql += " AND observed_at <= ?"
            params.append(date_to)
        sql += " ORDER BY observed_at DESC LIMIT ?"
        params.append(limit)
        return list(conn.execute(sql, params))

    def count(self, conn: sqlite3.Connection) -> int:
        return int(conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0])
