"""Manejo de errores HTTP de U2 (FD §5 — tabla de mapeo, sin stacktrace)."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from sentinel.foundation.errors import (
    IngestionError,
    ScopeError,
    StorageError,
    ValidationError,
)
from sentinel.foundation.logging import get_logger

from ..errors import ConflictError, NotFoundError, RunnerUnavailableError

__all__ = ["register_exception_handlers"]

_log = get_logger("core.api.errors")


def _json(status: int, detail: str, **extra: object) -> JSONResponse:
    body: dict[str, object] = {"detail": detail}
    body.update(extra)
    return JSONResponse(status_code=status, content=body)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def _not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return _json(404, "not found")

    @app.exception_handler(ConflictError)
    async def _conflict(request: Request, exc: ConflictError) -> JSONResponse:
        return _json(409, "discovery already running")

    @app.exception_handler(RunnerUnavailableError)
    async def _runner_unavailable(request: Request, exc: RunnerUnavailableError) -> JSONResponse:
        return _json(503, "discovery runner not available")

    @app.exception_handler(StorageError)
    async def _storage(request: Request, exc: StorageError) -> JSONResponse:
        return _json(503, "storage unavailable")

    @app.exception_handler(IngestionError)
    async def _ingestion(request: Request, exc: IngestionError) -> JSONResponse:
        return _json(503, "storage unavailable")

    @app.exception_handler(ScopeError)
    async def _scope(request: Request, exc: ScopeError) -> JSONResponse:
        return _json(400, str(exc), code="scope_violation")

    @app.exception_handler(ValidationError)
    async def _validation(request: Request, exc: ValidationError) -> JSONResponse:
        return _json(400, str(exc))

    @app.exception_handler(RequestValidationError)
    async def _request_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        # FD §5: falta de campo obligatorio/lote malformado ⇒ 400; payload
        # fuera de schema ⇒ 422 con detalle de campo (§3.1 permite 400/422).
        errors = jsonable_encoder(exc.errors())
        status_code = 400 if errors and all(e.get("type") == "missing" for e in errors) else 422
        return JSONResponse(status_code=status_code, content={"detail": errors})

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        _log.error(
            "unhandled error",
            extra={"event": "internal_error", "path": request.url.path},
            exc_info=True,
        )
        return _json(500, "internal error")

    @app.exception_handler(HTTPException)
    async def _http(request: Request, exc: HTTPException) -> JSONResponse:
        return _json(exc.status_code, str(exc.detail))
