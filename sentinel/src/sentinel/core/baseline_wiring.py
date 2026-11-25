"""Wiring de U6 en core: adaptadores de store + fábrica del ConditionService.

Composición **core→baseline** (BR-U6-01): core conoce a baseline; ``baseline``
nunca importa core ni ``sqlite3`` (los adaptadores viven aquí, P11/ID-U6-01).
La hidratación ocurre aquí y su fallo degrada a servicio vacío con
``event=baseline_hydration_failed`` (P2, NFR-Req Q5=A) — jamás impide arrancar.
"""

from __future__ import annotations

from typing import Any

from sentinel.baseline import (
    BaselineSettings,
    ConditionService,
    SystemClock,
    load_baseline_settings,
)
from sentinel.foundation.logging import get_logger

from .db.database import Database
from .db.repos.alerts import AlertRepository
from .db.repos.baselines import BaselineRepository

__all__ = ["AlertStore", "BaselineStore", "build_condition_service"]

_log = get_logger("baseline.wiring")


class BaselineStore:
    """Adaptador ``BaselineStore`` (Protocol de baseline) sobre ``Database``."""

    def __init__(self, db: Database) -> None:
        self._db = db
        self._repo = BaselineRepository()

    def list(self) -> list[dict[str, Any]]:
        with self._db.read() as conn:
            return [dict(row) for row in self._repo.list(conn)]

    def upsert(self, baseline: dict[str, Any]) -> None:
        with self._db.write() as conn:
            self._repo.upsert(conn, baseline)


class AlertStore:
    """Adaptador ``AlertStore`` (Protocol de baseline) sobre ``Database``."""

    def __init__(self, db: Database) -> None:
        self._db = db
        self._repo = AlertRepository()

    def upsert(self, alert: dict[str, Any]) -> None:
        with self._db.write() as conn:
            self._repo.upsert(conn, alert)

    def list_firing(self) -> list[dict[str, Any]]:
        with self._db.read() as conn:
            rows, _ = self._repo.list(conn, state="firing", limit=10_000)
            return [dict(row) for row in rows]


def build_condition_service(
    db: Database,
    settings: BaselineSettings | None = None,
    clock: Any | None = None,
) -> ConditionService:
    """Fábrica con hidratación degradada (FD §3.7, P2).

    Un fallo al cargar ``baselines``/``alerts`` ⇒ log
    ``baseline_hydration_failed`` + servicio **vacío** (arranque OK);
    ``load_baseline_settings()`` sí es fail-fast (ConfigError ⇒ arranque
    fallido, precedente discovery).
    """
    resolved_settings = settings if settings is not None else load_baseline_settings()
    resolved_clock = clock if clock is not None else SystemClock()
    service = ConditionService(
        baselines=BaselineStore(db),
        alerts=AlertStore(db),
        settings=resolved_settings,
        clock=resolved_clock,
    )
    try:
        service.hydrate()
    except Exception:  # noqa: BLE001 - degradación deliberada (P2)
        _log.warning(
            "baseline hydration failed; starting empty",
            extra={"event": "baseline_hydration_failed"},
        )
        service = ConditionService(
            baselines=BaselineStore(db),
            alerts=AlertStore(db),
            settings=resolved_settings,
            clock=resolved_clock,
        )
    return service
