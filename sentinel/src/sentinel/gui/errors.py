"""Errores y páginas de error de la GUI (P10, Q12=NFR=A, FD §5).

- ``CoreUnavailableError``: loopback caído/timeout ⇒ **502** (sin retry).
- ``ApiStatusError``: la API devolvió 4xx/5xx ⇒ se traslada el status con
  la forma de error de U2 (JSON en ``/api/*``, página en ``/ui/*``).
- ``render_error`` + ``error.html``: página única para el operador.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

from sentinel.core.errors import ConflictError, NotFoundError
from sentinel.foundation.errors import SentinelError, ValidationError
from sentinel.foundation.logging import get_logger

from .templates import get_templates
from .viewmodels import ErrorVM

__all__ = [
    "ApiStatusError",
    "CoreUnavailableError",
    "register_gui_exception_handlers",
    "render_error",
]

_log = get_logger("gui.errors")


class CoreUnavailableError(SentinelError):
    """Loopback a la API inaccesible (conexión/timeout) ⇒ 502, sin retry."""

    code = "core_unavailable"


class ApiStatusError(SentinelError):
    """Respuesta 4xx/5xx de la API U2 trasladada a la GUI."""

    code = "api_status"

    def __init__(self, message: str, *, status_code: int, response_code: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_code = response_code


def _want_html(request: Request) -> bool:
    return request.url.path.startswith("/ui/")


def _json(status: int, detail: str, code: str | None = None) -> JSONResponse:
    body: dict[str, object] = {"detail": detail}
    if code is not None:
        body["code"] = code
    return JSONResponse(status_code=status, content=body)


def _title_for(status: int, code: str | None) -> str:
    if status == 400 and code == "scope_violation":
        return "Host fuera de alcance"
    if status == 404:
        return "No encontrado"
    if status == 409:
        return "Ciclo ya en curso"
    if status == 503:
        return "Descubrimiento no disponible"
    if status in (400, 422):
        return "Solicitud inválida"
    return f"Error {status}"


def render_error(
    request: Request,
    status: int,
    title: str,
    detail: str,
    code: str | None = None,
) -> Response:
    """Página ``error.html`` (fallback JSON si el template no carga)."""
    try:
        templates = get_templates()
    except Exception:  # noqa: BLE001 — sin templates ⇒ JSON (nunca traceback)
        return _json(status, detail, code)
    vm = ErrorVM(status=status, title=title, detail=detail, code=code)
    return templates.TemplateResponse(request, "error.html", {"vm": vm}, status_code=status)


def register_gui_exception_handlers(app: FastAPI) -> None:
    """Handlers de U3; pisan a los de U2 con branch HTML/JSON por path."""

    @app.exception_handler(CoreUnavailableError)
    async def _core_unavailable(request: Request, exc: CoreUnavailableError) -> Response:
        _log.warning(
            "core api unavailable",
            extra={"event": "core_unavailable", "path": request.url.path},
        )
        if _want_html(request):
            return render_error(
                request, 502, "Core API no disponible", "core api no disponible", "core_unavailable"
            )
        return _json(502, "core api unavailable", "core_unavailable")

    @app.exception_handler(ApiStatusError)
    async def _api_status(request: Request, exc: ApiStatusError) -> Response:
        status_code = exc.status_code
        if _want_html(request):
            return render_error(
                request,
                status_code,
                _title_for(status_code, exc.response_code),
                exc.message,
                exc.response_code,
            )
        return _json(status_code, exc.message, exc.response_code)

    @app.exception_handler(ValidationError)
    async def _validation(request: Request, exc: ValidationError) -> Response:
        # Rama JSON idéntica a U2 (sin ``code``): los tests de U2 comparan
        # el body exacto; el ``code`` solo se muestra en la página HTML.
        if _want_html(request):
            return render_error(request, 400, "Solicitud inválida", str(exc), exc.code)
        return _json(400, str(exc))

    @app.exception_handler(NotFoundError)
    async def _not_found(request: Request, exc: NotFoundError) -> Response:
        if _want_html(request):
            return render_error(request, 404, "No encontrado", "not found", exc.code)
        return _json(404, "not found")

    @app.exception_handler(ConflictError)
    async def _conflict(request: Request, exc: ConflictError) -> Response:
        if _want_html(request):
            return render_error(
                request, 409, "Ciclo ya en curso", "discovery already running", exc.code
            )
        return _json(409, "discovery already running")

    @app.exception_handler(RequestValidationError)
    async def _request_validation(request: Request, exc: RequestValidationError) -> Response:
        errors = jsonable_encoder(exc.errors())
        status_code = 400 if errors and all(e.get("type") == "missing" for e in errors) else 422
        if _want_html(request):
            return render_error(
                request, status_code, "Solicitud inválida", "validation error", "validation_error"
            )
        return JSONResponse(status_code=status_code, content={"detail": errors})

    @app.exception_handler(HTTPException)
    async def _http(request: Request, exc: HTTPException) -> Response:
        detail = str(exc.detail)
        if _want_html(request):
            return render_error(request, exc.status_code, _title_for(exc.status_code, None), detail)
        return _json(exc.status_code, detail)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> Response:
        _log.error(
            "unhandled error",
            extra={"event": "internal_error", "path": request.url.path},
            exc_info=True,
        )
        if _want_html(request):
            return render_error(request, 500, "Error interno", "internal error", "internal_error")
        return _json(500, "internal error")
