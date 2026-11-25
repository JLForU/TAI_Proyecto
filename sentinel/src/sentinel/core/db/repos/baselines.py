"""Repositorio de baselines (esquema U2; los llena U6 — OQ-02)."""

from __future__ import annotations

import sqlite3
from typing import Any

from ._common import dumps

__all__ = ["BaselineRepository"]


class BaselineRepository:
    def upsert(self, conn: sqlite3.Connection, baseline: dict[str, Any]) -> None:
        conn.execute(
            "INSERT INTO baselines (metric_key, interval_seconds, samples, mean, variance,"
            " established, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(metric_key) DO UPDATE SET"
            " interval_seconds = excluded.interval_seconds, samples = excluded.samples,"
            " mean = excluded.mean, variance = excluded.variance,"
            " established = excluded.established, updated_at = excluded.updated_at",
            (
                baseline["metric_key"],
                baseline.get("interval_seconds", 5),
                dumps(baseline.get("samples", [])),
                baseline.get("mean"),
                baseline.get("variance"),
                1 if baseline.get("established") else 0,
                baseline.get("updated_at") or "",
            ),
        )

    def get(self, conn: sqlite3.Connection, metric_key: str) -> sqlite3.Row | None:
        return conn.execute(
            "SELECT * FROM baselines WHERE metric_key = ?", (metric_key,)
        ).fetchone()

    def list(self, conn: sqlite3.Connection) -> list[sqlite3.Row]:
        return list(conn.execute("SELECT * FROM baselines ORDER BY metric_key"))
