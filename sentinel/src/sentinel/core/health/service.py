"""HealthService — ``GET /health`` derivado de la BD (ST-M4-08).

``status = up`` ⇔ la BD responde; ``degraded`` en caso contrario (sin excepción
propagada: la salud nunca rompe el proceso). Corazones por sensor = última
``observed_at`` por ``sensor_id`` (U2 solo reporta; U3/4 los llenan).
"""

from __future__ import annotations

import sqlite3
import time

from ..api.schemas import HealthStatus
from ..db.database import Database
from ..db.repos.discovery_runs import DiscoveryRunRepository

__all__ = ["HealthService"]


class HealthService:
    def __init__(
        self,
        db: Database,
        *,
        runs: DiscoveryRunRepository | None = None,
        started_at: float | None = None,
    ) -> None:
        self._db = db
        self._runs = runs or DiscoveryRunRepository()
        self._started_at = started_at if started_at is not None else time.time()

    @staticmethod
    def _heartbeats(conn: sqlite3.Connection) -> dict[str, str]:
        return {
            str(r["sensor_id"]): str(r["last_seen"])
            for r in conn.execute(
                "SELECT sensor_id, MAX(observed_at) AS last_seen FROM observations"
                " WHERE sensor_id IS NOT NULL GROUP BY sensor_id"
            )
        }

    def sensor_heartbeats(self) -> dict[str, str]:
        """Último ``observed_at`` por sensor para el colector (BR-U7-09).

        La salud nunca rompe el proceso: si la BD falla se devuelve ``{}`` y
        el colector reporta antigüedad 0 (degradación visible en métricas).
        """
        try:
            with self._db.read() as conn:
                return self._heartbeats(conn)
        except Exception:  # pragma: no cover - BD inaccesible
            return {}

    def health(self) -> HealthStatus:
        uptime = max(0.0, time.time() - self._started_at)
        try:
            with self._db.read() as conn:
                conn.execute("SELECT 1").fetchone()
                last_ingest = conn.execute(
                    "SELECT MAX(received_at) AS v FROM observations"
                ).fetchone()["v"]
                heartbeats = self._heartbeats(conn)
                counts = {
                    "assets": int(conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]),
                    "events": int(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]),
                    "alerts": int(conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]),
                }
                run = self._runs.latest(conn)
                last_run = None
                if run is not None:
                    last_run = {
                        "run_id": str(run["run_id"]),
                        "status": str(run["status"]),
                        "started_at": str(run["started_at"]),
                        "finished_at": run["finished_at"],
                        "hosts_seen": run["hosts_seen"],
                        "error": run["error"],
                    }
            return HealthStatus(
                status="up",
                uptime_seconds=round(uptime, 3),
                db_connected=True,
                last_ingest_at=str(last_ingest) if last_ingest else None,
                sensor_heartbeats=heartbeats,
                counts=counts,
                last_discovery_run=last_run,
            )
        except Exception:
            return HealthStatus(
                status="degraded",
                uptime_seconds=round(uptime, 3),
                db_connected=False,
            )
