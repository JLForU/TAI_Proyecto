"""Dependencias FastAPI de U2 (auth de ingesta + paginación, P10)."""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from sentinel.foundation.logging import get_logger

from ..config import CoreSettings
from ..db.database import Database
from ..discovery.trigger import DiscoveryTrigger
from ..export.service import ExportService
from ..health.service import HealthService
from ..ingestion.service import IngestionService
from ..query.service import QueryService
from ..reset.service import ResetService

__all__ = [
    "get_db",
    "get_export",
    "get_health",
    "get_ingestion",
    "get_discovery",
    "get_query",
    "get_reset",
    "get_settings",
    "require_ingest_token",
]

_log = get_logger("core.api.auth")


def get_settings(request: Request) -> CoreSettings:
    return request.app.state.settings


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_ingestion(request: Request) -> IngestionService:
    return request.app.state.ingestion


def get_query(request: Request) -> QueryService:
    return request.app.state.query


def get_export(request: Request) -> ExportService:
    return request.app.state.export


def get_health(request: Request) -> HealthService:
    return request.app.state.health


def get_discovery(request: Request) -> DiscoveryTrigger:
    return request.app.state.discovery


def get_reset(request: Request) -> ResetService:
    return request.app.state.reset


def require_ingest_token(
    authorization: Annotated[str | None, Header()] = None,
    settings: CoreSettings = Depends(get_settings),
) -> None:
    """Bearer == ``SENTINEL_INGEST_TOKEN`` (FD §3.1, §5).

    - token no configurado ⇒ 403 ``ingest token not configured``
    - ausente/incorrecto ⇒ 401 ``unauthorized`` (comparación en tiempo constante)
    """
    configured = settings.ingest_token
    if not configured:
        _log.warning(
            "ingest request rejected: token not configured",
            extra={"event": "ingest_token_missing"},
        )
        raise HTTPException(status_code=403, detail="ingest token not configured")
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="unauthorized")
    provided = authorization[len("Bearer ") :]
    if not hmac.compare_digest(provided.encode(), configured.encode()) or not provided:
        raise HTTPException(status_code=401, detail="unauthorized")
