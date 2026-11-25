"""Componente de acceso a DB de U2 (Q8 NFR, P1–P4, BR-U2-18/19).

- Conexión **por request/transaction** (context manager), WAL para lecturas
  concurrentes, ``write_lock`` en proceso para serializar escrituras (REL-01).
- ``startup_checks()``: integrity_check (P1) + stale discovery runs (P2).
- ``close()``: ``wal_checkpoint(TRUNCATE)`` + cierre (P4, NFR-U2-REL-02).
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path

from sentinel.foundation.errors import StorageError
from sentinel.foundation.logging import get_logger

from .schema import apply_schema

__all__ = ["Database", "DbIntegrityError"]

_log = get_logger("core.db")


class DbIntegrityError(StorageError):
    """``PRAGMA integrity_check`` falló; el archivo queda intacto (P1)."""

    code = "db_integrity_failed"


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


class Database:
    """Gestor de SQLite del Core: conexiones puntuales + lock de escritura."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.write_lock = threading.Lock()
        self._open: set[sqlite3.Connection] = set()

    # --- conexiones ---------------------------------------------------------

    def _new_connection(self) -> sqlite3.Connection:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        try:
            conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        except sqlite3.Error as exc:
            raise StorageError(f"cannot open database: {exc}") from exc
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        self._open.add(conn)
        return conn

    def _release(self, conn: sqlite3.Connection) -> None:
        self._open.discard(conn)
        with suppress(sqlite3.Error):  # best effort
            conn.close()

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        """Conexión de solo lectura (WAL, sin lock)."""
        conn = self._new_connection()
        try:
            yield conn
        finally:
            self._release(conn)

    @contextmanager
    def write(self) -> Iterator[sqlite3.Connection]:
        """Transacción de escritura serializada (write_lock, BEGIN/COMMIT)."""
        with self.write_lock:
            conn = self._new_connection()
            try:
                conn.execute("BEGIN")
                yield conn
                conn.execute("COMMIT")
            except BaseException:
                with suppress(sqlite3.Error):  # tx ya abortada
                    conn.execute("ROLLBACK")
                raise
            finally:
                self._release(conn)

    # --- arranque y apagado (P1/P2/P4) --------------------------------------

    def apply_schema(self) -> None:
        # executescript hace commit implícito: se ejecuta fuera de write()
        # (idempotente, arranque single-threaded; el lock no aporta nada aquí).
        conn = self._new_connection()
        try:
            apply_schema(conn)
        finally:
            self._release(conn)

    def startup_checks(self) -> None:
        """Integrity check (P1) + DDL + stale runs (P2). Lanza sin tocar el archivo."""
        self._integrity_check()
        self.apply_schema()
        self._fail_stale_runs()

    def _integrity_check(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.DatabaseError as exc:
            conn.close()
            raise DbIntegrityError(f"database integrity check failed: {exc}") from exc
        conn.close()
        if row is None or row[0] != "ok":
            raise DbIntegrityError(
                f"database integrity check failed: {row[0] if row else 'no result'}"
            )

    def _fail_stale_runs(self) -> None:
        with self.write() as conn:
            cur = conn.execute(
                "UPDATE discovery_runs SET status = 'failed', error = ?, finished_at = ? "
                "WHERE status = 'running'",
                ("core restarted", _utcnow()),
            )
        if cur.rowcount:
            _log.warning(
                "stale discovery runs marked failed",
                extra={"event": "stale_runs_recovered", "count": cur.rowcount},
            )

    def close(self) -> None:
        """Apagado ordenado: checkpoint TRUNCATE + cierre de conexiones (P4)."""
        for conn in list(self._open):
            self._release(conn)
        try:
            conn = sqlite3.connect(self.path)
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()
        except sqlite3.Error:  # pragma: no cover - DB ya inaccesible
            pass
