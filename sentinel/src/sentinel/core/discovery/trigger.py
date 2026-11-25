"""DiscoveryTrigger — expone ``POST /api/v1/discovery`` sin conocer el runner.

P2: U2 crea ``discovery_runs`` y llama a un ``CycleRunner`` inyectado (U4 lo
implementa con el escáner). Sin runner ⇒ ``RunnerUnavailableError`` (503,
BR-U2-30). Un ciclo ya en curso ⇒ ``ConflictError`` (409, BR-U2-31). El lock
único lo provee la transacción ``write`` (check-and-create serializado).

Protocolo del runner (inyección): ``run(hosts, timeout_seconds) -> hosts_seen``;
timeout ⇒ excepción ``DiscoveryTimeoutError``; cualquier otro error ⇒ ``failed``.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Protocol

from sentinel.foundation.logging import get_logger

from ..api.schemas import DiscoveryRunStatus
from ..db.database import Database
from ..db.repos.discovery_runs import DiscoveryRunRepository
from ..errors import ConflictError, RunnerUnavailableError

if TYPE_CHECKING:  # typing-only: sin dependencia runtime de U4
    from ...discovery.scope import ScopeValidator
    from ..metrics.collect import CycleCounter

__all__ = ["CycleRunner", "DiscoveryTimeoutError", "DiscoveryTrigger"]

_log = get_logger("discovery.trigger")


class DiscoveryTimeoutError(Exception):
    """El runner superó ``timeout_seconds`` (estado ``timeout``)."""


class CycleRunner(Protocol):
    def run(self, hosts: list[str], timeout_seconds: int) -> int:
        """Ejecuta un ciclo; devuelve ``hosts_seen``."""
        ...


class DiscoveryTrigger:
    def __init__(
        self,
        db: Database,
        *,
        runner: CycleRunner | None = None,
        runs: DiscoveryRunRepository | None = None,
        counter: CycleCounter | None = None,
        scope_validator: ScopeValidator | None = None,
    ) -> None:
        self._db = db
        self._runner = runner
        self._runs = runs or DiscoveryRunRepository()
        self._counter = counter
        self._scope_validator = scope_validator

    @property
    def scope_validator(self) -> ScopeValidator | None:
        """Validador C12 del proceso (``None`` sin config de scope, D-U4-04)."""
        return self._scope_validator

    @property
    def available(self) -> bool:
        return self._runner is not None

    def trigger(
        self, hosts: list[str], timeout_seconds: int, *, wait: bool = False
    ) -> DiscoveryRunStatus:
        if self._runner is None:
            raise RunnerUnavailableError("cycle runner not available (U4 pending)")
        with self._db.write() as conn:
            if self._runs.any_running(conn):
                raise ConflictError("discovery cycle already running")
            run_id = self._runs.create(conn, hosts=hosts, now=_now_iso())
        thread = threading.Thread(
            target=self._execute, args=(run_id, list(hosts), timeout_seconds), daemon=True
        )
        thread.start()
        if wait:
            thread.join()
        with self._db.read() as conn:
            row = self._runs.get(conn, run_id)
        assert row is not None
        return _status(row)

    def get_status(self, run_id: str) -> DiscoveryRunStatus | None:
        """Estado de un run; ``None`` si no existe (⇒ 404 en la API)."""
        with self._db.read() as conn:
            row = self._runs.get(conn, run_id)
        return _status(row) if row is not None else None

    def _execute(self, run_id: str, hosts: list[str], timeout_seconds: int) -> None:
        assert self._runner is not None
        status, hosts_seen, error, cause = "completed", None, None, None
        try:
            hosts_seen = int(self._runner.run(hosts, timeout_seconds))
        except DiscoveryTimeoutError as exc:
            status, error, cause = "timeout", str(exc) or "timeout", "timeout"
        except Exception as exc:  # noqa: BLE001 - el runner es externo
            status, error = "failed", str(exc)
            cause = getattr(exc, "code", None) or error or "failed"
        try:
            with self._db.write() as conn:
                self._runs.finish(conn, run_id, status=status, hosts_seen=hosts_seen, error=error)
        except Exception:  # noqa: BLE001 - el run queda stale ⇒ startup_checks lo marcará failed
            pass
        if self._counter is not None:
            self._counter.record(status)
        if status in {"failed", "timeout"}:
            _log.info(
                "discovery cycle failed",
                extra={
                    "event": "discovery_cycle_failed",
                    "run_id": run_id,
                    "cause": cause or status,
                    "status": status,
                },
            )


def _status(row) -> DiscoveryRunStatus:  # type: ignore[no-untyped-def]
    return DiscoveryRunStatus(
        run_id=str(row["run_id"]),
        status=str(row["status"]),
        started_at=str(row["started_at"]),
        finished_at=row["finished_at"],
        hosts_seen=row["hosts_seen"],
        error=row["error"],
    )


def _now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
