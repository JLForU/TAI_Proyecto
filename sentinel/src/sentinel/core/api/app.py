"""Factory de la aplicación FastAPI del Core (U2, P10/P11).

``create_app(settings, runner=..., metrics_port=...)`` ensambla servicios +
rutas; el lifespan ejecuta ``startup_checks`` (integrity + DDL + stale runs),
arranca el servidor de métricas (9108) y ``close`` (checkpoint) — FD §3.1/§5.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable, Iterable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from sentinel.baseline import BaselineSettings
from sentinel.baseline.conditions import Clock
from sentinel.foundation.errors import ConfigError
from sentinel.foundation.logging import get_logger
from sentinel.foundation.models import Observation

from ..baseline_wiring import build_condition_service
from ..config import CoreSettings, load_core_settings
from ..db.database import Database
from ..discovery.trigger import CycleRunner, DiscoveryTrigger
from ..export.service import ExportService
from ..health.service import HealthService
from ..ingestion.service import IngestionService
from ..metrics.collect import ApiRequestCounter, CycleCounter, ObservationCounters, collect
from ..metrics.server import METRICS_PORT, MetricsServer
from ..query.service import QueryService
from .errors import register_exception_handlers

if TYPE_CHECKING:  # anotación de ``scope_validator`` sin dependencia runtime
    from ...discovery.scope import ScopeValidator

__all__ = ["create_app"]

_log = get_logger("core.api.app")


def _compose_hooks(
    *hooks: Callable[[Iterable[Observation]], None],
) -> Callable[[Iterable[Observation]], None]:
    """Encadena hooks post-commit aislados (BR-U7-11/12, D-U7-02).

    Un fallo en un hook se registra como ``metrics_hook_failed`` y **no**
    revierte la ingesta ni impide que el siguiente hook se ejecute.
    """

    def composed(observations: Iterable[Observation]) -> None:
        for hook in hooks:
            try:
                hook(observations)
            except Exception as exc:  # noqa: BLE001 - hook best-effort
                _log.error(
                    "metrics hook failed",
                    extra={"event": "metrics_hook_failed", "error": str(exc)},
                )

    return composed


def create_app(
    settings: CoreSettings | None = None,
    *,
    runner: CycleRunner | None = None,
    metrics_port: int | None = METRICS_PORT,
    api_base: str | None = None,
    http_client: httpx.Client | None = None,
    scope_validator: ScopeValidator | None = None,
    baseline_settings: BaselineSettings | None = None,
    condition_clock: Clock | None = None,
) -> FastAPI:
    """Crea la app. ``metrics_port=None`` desactiva el servidor 9108 (tests).

    El ``MetricsServer`` se construye/arranca en el lifespan (bind en
    ``start()``, no en el import): la instancia de módulo ``app`` no ocupa
    el puerto hasta que el proceso realmente sirve.

    ``api_base``/``http_client`` configuran el loopback del GUI U3
    (``gui_config`` en ``app.state``); si el paquete ``gui`` no está
    disponible la app sigue siendo solo-API (Q10=A, bloque try/except).

    ``scope_validator`` (U4): ``None`` ⇒ se construye desde el env
    ``SENTINEL_DISCOVERY_*`` si existe (D-U4-04); un valor explícito
    (tests) se usa tal cual.

    ``baseline_settings``/``condition_clock`` (U6, ID-U6-07): seams de test
    (precedente ``runner=``); por defecto ``load_baseline_settings()``
    (fail-fast ``ConfigError`` ⇒ arranque fallido) + ``SystemClock``.
    """
    cfg = settings if settings is not None else load_core_settings()
    db = Database(cfg.db_path)
    api_counter = ApiRequestCounter()
    cycle_counter = CycleCounter()
    obs_counters = ObservationCounters()

    # --- U4 (edición acotada FD §4): scope condicional + runner lazy -------
    # D-U4-04: solo hay validador de scope si el proceso tiene config de
    # discovery; Q15=A: runner por import perezoso (composición core→discovery).
    # Sin env ``SENTINEL_DISCOVERY_*`` no se intenta nada (cero ruido en los
    # tests de U2 y ``503 runner unavailable`` como hasta ahora — BR-U4-36).
    has_discovery_env = any(key.startswith("SENTINEL_DISCOVERY_") for key in dict(os.environ))
    if scope_validator is None and has_discovery_env:
        try:
            from ...discovery.config import load_discovery_settings
            from ...discovery.scope import ScopeValidator as _ScopeValidator

            discovery_settings = load_discovery_settings()
            scope_validator = _ScopeValidator(discovery_settings)
        except ImportError as exc:  # pragma: no cover — paquete discovery ausente
            _log.warning(
                "discovery wiring skipped",
                extra={"event": "discovery_wiring_skipped", "reason": str(exc)},
            )
        except ConfigError as exc:  # config inválida ⇒ sin validador; el
            # runner explícito (tests) no se toca; sin él se queda en 503.
            _log.warning(
                "discovery wiring skipped",
                extra={"event": "discovery_wiring_skipped", "reason": str(exc)},
            )
            scope_validator = None

    if runner is None and has_discovery_env:
        try:
            from ...discovery.config import load_discovery_settings
            from ...discovery.runner import CycleRunnerImpl

            runner = CycleRunnerImpl(load_discovery_settings())
        except ImportError as exc:  # pragma: no cover — paquete discovery ausente
            _log.warning(
                "discovery runner unavailable",
                extra={"event": "discovery_runner_unavailable", "reason": str(exc)},
            )
        except ConfigError as exc:
            _log.warning(
                "discovery runner unavailable",
                extra={"event": "discovery_runner_unavailable", "reason": str(exc)},
            )
            runner = None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        db.startup_checks()
        server: MetricsServer | None = None
        if metrics_port is not None:
            server = MetricsServer(
                port=metrics_port,
                collect_fn=lambda: collect(
                    api_requests=api_counter,
                    cycles=cycle_counter,
                    heartbeats=HealthService(db).sensor_heartbeats(),
                    condition_service=app.state.condition,
                    db=db,
                    obs_counters=obs_counters,
                ),
            )
            server.start()
            app.state.metrics_server = server
        try:
            yield
        finally:
            if server is not None:
                server.stop()
                app.state.metrics_server = None
            db.close()

    app = FastAPI(title="Sentinel Core", version="2.0.0", lifespan=lifespan)
    app.state.settings = cfg
    app.state.db = db
    # U6 (FD §3.7): ConditionService hidratado (degradado) + hook post-commit.
    app.state.condition = build_condition_service(db, baseline_settings, condition_clock)
    app.state.ingestion = IngestionService(
        db,
        missing_cycles=cfg.missing_cycles,
        on_accepted=_compose_hooks(
            app.state.condition.on_accepted,
            obs_counters.on_accepted,
        ),
    )
    app.state.query = QueryService(db, page_limit=cfg.page_limit)
    app.state.export = ExportService(db)
    app.state.health = HealthService(db)
    app.state.discovery = DiscoveryTrigger(
        db, runner=runner, counter=cycle_counter, scope_validator=scope_validator
    )
    app.state.api_counter = api_counter
    app.state.cycle_counter = cycle_counter
    app.state.obs_counters = obs_counters
    app.state.metrics_server = None

    @app.middleware("http")
    async def count_api_requests(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        api_counter.inc(str(response.status_code))
        return response

    from .routes_discovery import router as discovery_router
    from .routes_export import router as export_router
    from .routes_health import router as health_router
    from .routes_ingest import router as ingest_router
    from .routes_query import router as query_router

    app.include_router(ingest_router, prefix="/api/v1")
    app.include_router(query_router, prefix="/api/v1")
    app.include_router(export_router, prefix="/api/v1")
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(discovery_router, prefix="/api/v1")
    register_exception_handlers(app)

    # --- U3 (edición acotada Q10=A): montaje del GUI de operador ---------
    # Si el paquete gui/ sus dependencias no están, la app sigue sirviendo
    # solo la API (sin /ui, sin /static, sin handlers 502 del loopback).
    try:
        from ...gui.client import API_BASE as GUI_API_BASE
        from ...gui.errors import register_gui_exception_handlers
        from ...gui.routes import report_api_router
        from ...gui.routes import router as gui_router

        app.state.gui_config = (api_base or GUI_API_BASE, http_client)
        app.include_router(gui_router)
        app.include_router(report_api_router)
        register_gui_exception_handlers(app)
        static_dir = Path(__file__).resolve().parent.parent.parent / "gui" / "static"
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    except ImportError as exc:  # pragma: no cover — degradación a solo-API
        import logging

        logging.getLogger("sentinel.core.api.app").warning(
            "gui not mounted",
            extra={"event": "gui_mount_skipped", "reason": str(exc)},
        )
    return app


#: Instancia por defecto (``uvicorn sentinel.core.api.app:app`` / ``python -m sentinel.core``).
app = create_app()
