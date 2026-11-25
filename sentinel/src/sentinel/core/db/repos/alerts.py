"""Repositorio de alertas (esquema U2; los llena U6 — OQ-02)."""

from __future__ import annotations

import sqlite3
from typing import Any

from ._common import dumps, normalize_iso

__all__ = ["AlertRepository"]


class AlertRepository:
    def upsert(self, conn: sqlite3.Connection, alert: dict[str, Any]) -> None:
        conn.execute(
            "INSERT INTO alerts (alert_id, condition_id, rule, metric_key, asset_id, state,"
            " measured_value, threshold, fired_at, resolved_at, evidence, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(alert_id) DO UPDATE SET"
            " state = excluded.state, measured_value = excluded.measured_value,"
            " threshold = excluded.threshold, resolved_at = excluded.resolved_at,"
            " evidence = excluded.evidence, updated_at = excluded.updated_at",
            (
                alert["alert_id"],
                alert["condition_id"],
                alert["rule"],
                alert.get("metric_key"),
                alert.get("asset_id"),
                alert["state"],
                alert.get("measured_value"),
                alert.get("threshold"),
                alert["fired_at"],
                alert.get("resolved_at"),
                dumps(alert.get("evidence", {})),
                alert.get("updated_at") or alert["fired_at"],
            ),
        )

    def list(
        self,
        conn: sqlite3.Connection,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        state: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[sqlite3.Row], int]:
        clauses, params = [], []
        if date_from:
            clauses.append("fired_at >= ?")
            params.append(normalize_iso(date_from))
        if date_to:
            clauses.append("fired_at <= ?")
            params.append(normalize_iso(date_to))
        if state:
            clauses.append("state = ?")
            params.append(state)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        total = int(conn.execute(f"SELECT COUNT(*) FROM alerts{where}", params).fetchone()[0])
        rows = list(
            conn.execute(
                f"SELECT * FROM alerts{where} ORDER BY fired_at DESC LIMIT ? OFFSET ?",
                [*params, limit, offset],
            )
        )
        return rows, total

    def count(self, conn: sqlite3.Connection) -> int:
        return int(conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0])
