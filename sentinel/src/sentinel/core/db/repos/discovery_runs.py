"""Repositorio de discovery runs (BR-U2-32/33, P2)."""

from __future__ import annotations

import sqlite3
import uuid

from ._common import dumps, iso_now

__all__ = ["DiscoveryRunRepository"]


class DiscoveryRunRepository:
    def create(
        self,
        conn: sqlite3.Connection,
        *,
        hosts: list[str],
        trigger: str = "manual_api",
        now: str | None = None,
    ) -> str:
        run_id = str(uuid.uuid4())
        ts = now or iso_now()
        conn.execute(
            "INSERT INTO discovery_runs"
            ' (run_id, status, "trigger", hosts_targeted, started_at)'
            " VALUES (?, 'running', ?, ?, ?)",
            (run_id, trigger, dumps(hosts), ts),
        )
        return run_id

    def get(self, conn: sqlite3.Connection, run_id: str) -> sqlite3.Row | None:
        return conn.execute("SELECT * FROM discovery_runs WHERE run_id = ?", (run_id,)).fetchone()

    def any_running(self, conn: sqlite3.Connection) -> bool:
        row = conn.execute(
            "SELECT 1 FROM discovery_runs WHERE status = 'running' LIMIT 1"
        ).fetchone()
        return row is not None

    def finish(
        self,
        conn: sqlite3.Connection,
        run_id: str,
        *,
        status: str,
        hosts_seen: int | None = None,
        error: str | None = None,
        now: str | None = None,
    ) -> None:
        conn.execute(
            "UPDATE discovery_runs SET status = ?, hosts_seen = ?, error = ?,"
            " finished_at = ? WHERE run_id = ?",
            (status, hosts_seen, error, now or iso_now(), run_id),
        )

    def latest(self, conn: sqlite3.Connection) -> sqlite3.Row | None:
        return conn.execute(
            "SELECT * FROM discovery_runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
