"""Repositorio de eventos (``event_id`` UUIDv5, INSERT OR IGNORE — BR-U2-06/07)."""

from __future__ import annotations

import sqlite3
from typing import Any

from ._common import dumps, normalize_iso

__all__ = ["EventRepository"]

#: ``(cláusula WHERE, parámetros)`` — alias a nivel de módulo porque dentro
#: de la clase ``list`` (el método) sombrearía al builtin en las anotaciones.
_WhereClause = tuple[str, list[Any]]


class EventRepository:
    def save_ignore(self, conn: sqlite3.Connection, event: dict[str, Any]) -> bool:
        """Persiste el evento si ``event_id`` no existía. Devuelve ``True`` si se insertó."""
        cur = conn.execute(
            "INSERT OR IGNORE INTO events"
            " (event_id, type, asset_id, severity, rule, occurred_at, details, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event["event_id"],
                event["type"],
                event.get("asset_id"),
                event.get("severity", "info"),
                event.get("rule"),
                event["occurred_at"],
                dumps(event.get("details", {})),
                event.get("created_at") or event["occurred_at"],
            ),
        )
        return cur.rowcount > 0

    def list(
        self,
        conn: sqlite3.Connection,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        asset_id: str | None = None,
        rule: str | None = None,
        severity: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[sqlite3.Row], int]:
        where, params = self._filters(
            date_from=date_from,
            date_to=date_to,
            asset_id=asset_id,
            rule=rule,
            severity=severity,
        )
        total = int(conn.execute(f"SELECT COUNT(*) FROM events{where}", params).fetchone()[0])
        rows = list(
            conn.execute(
                f"SELECT * FROM events{where} ORDER BY occurred_at DESC, event_id LIMIT ? OFFSET ?",
                [*params, limit, offset],
            )
        )
        return rows, total

    def _filters(
        self,
        *,
        date_from: str | None,
        date_to: str | None,
        asset_id: str | None,
        rule: str | None,
        severity: str | None,
    ) -> _WhereClause:
        clauses, params = [], []
        if date_from:
            clauses.append("occurred_at >= ?")
            params.append(normalize_iso(date_from))
        if date_to:
            clauses.append("occurred_at <= ?")
            params.append(normalize_iso(date_to))
        if asset_id:
            clauses.append("asset_id = ?")
            params.append(asset_id)
        if rule:
            clauses.append("rule = ?")
            params.append(rule)
        if severity:
            clauses.append("severity = ?")
            params.append(severity)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        return where, params

    def count(self, conn: sqlite3.Connection) -> int:
        return int(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])
