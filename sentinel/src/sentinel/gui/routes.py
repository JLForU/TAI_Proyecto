"""Routers ``/ui/*`` — handlers delgados (Q8=NFR=A, FD §3.1–3.5).

Flujo por vista: validar params (``gui.validation``) ⇒ ``GuiClient`` ⇒
view models ⇒ plantilla Jinja. Cero SQL, cero acceso a ``core.db``: todo
pasa por la API loopback (frontera U3↔U2).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, Response

from sentinel.foundation.errors import ValidationError

from .client import GuiClient
from .errors import ApiStatusError
from .report.sections import ReportRequest
from .report.service import ReportService
from .templates import get_templates
from .validation import (
    parse_date_range,
    parse_format,
    parse_host,
    parse_optional_date,
    parse_page,
)
from .viewmodels import (
    AssetDetailVM,
    AssetRowVM,
    DiscoveryRunVM,
    HealthVM,
    PageVM,
    TimelineEntryVM,
)

__all__ = [
    "PAGE_LIMIT",
    "get_gui_client",
    "get_report_service",
    "report_api_router",
    "router",
]

PAGE_LIMIT = 100

router = APIRouter(prefix="/ui", tags=["ui"])

FromParam = Annotated[str | None, Query(alias="from")]
ToParam = Annotated[str | None, Query(alias="to")]


def get_gui_client(request: Request) -> GuiClient:
    """Dependencia: GuiClient retenido en ``app.state`` (P7/Q6=NFR=A)."""
    client = getattr(request.app.state, "gui_client", None)
    if client is None:
        api_base, http_client = request.app.state.gui_config
        client = GuiClient(api_base, client=http_client)
        request.app.state.gui_client = client
    return client


def _render(request: Request, name: str, context: dict, status: int = 200) -> Response:
    return get_templates().TemplateResponse(request, name, context, status_code=status)


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _validate_status(status: str | None) -> str | None:
    if status in (None, ""):
        return None
    if status in ("present", "absent"):
        return status
    raise ValidationError("status must be present or absent")


# --------------------------------------------------------------------------- #
# ST-M10-01 — inventario paginado (FD §3.1)
# --------------------------------------------------------------------------- #


@router.get("/assets", response_class=HTMLResponse)
def assets_page(
    request: Request,
    page: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    client: GuiClient = Depends(get_gui_client),
) -> Response:
    page_n = parse_page(page)
    status = _validate_status(status_filter)
    offset = (page_n - 1) * PAGE_LIMIT
    asset_page = client.get_assets(limit=PAGE_LIMIT, offset=offset, status=status)
    rows: list[AssetRowVM] = []
    for summary in asset_page.items:
        try:
            detail = client.get_asset(summary.asset_id)
        except ApiStatusError as exc:
            if exc.status_code != 404:
                raise
            detail = None
        rows.append(AssetRowVM.from_summary_with_detail(summary, detail))
    vm = PageVM.build(rows, page=page_n, total=asset_page.total, limit=PAGE_LIMIT)
    return _render(request, "assets.html", {"page": vm, "status": status})


# --------------------------------------------------------------------------- #
# ST-M10-02 — detalle de activo (FD §3.2)
# --------------------------------------------------------------------------- #


@router.get("/assets/{asset_id}", response_class=HTMLResponse)
def asset_detail(
    asset_id: str,
    request: Request,
    client: GuiClient = Depends(get_gui_client),
) -> Response:
    detail = client.get_asset(asset_id)
    vm = AssetDetailVM.from_detail(detail)
    return _render(request, "asset_detail.html", {"asset": vm})


# --------------------------------------------------------------------------- #
# ST-M10-03 — línea de tiempo unificada + vista de alertas (FD §3.3)
# --------------------------------------------------------------------------- #


def _filters(
    asset_id: str | None,
    severity: str | None,
    rule: str | None,
    date_from: str | None,
    date_to: str | None,
) -> dict:
    return {
        "asset_id": asset_id or "",
        "severity": severity or "",
        "rule": rule or "",
        "from": date_from or "",
        "to": date_to or "",
    }


def _timeline_context(
    client: GuiClient,
    *,
    page_n: int,
    asset_id: str | None,
    severity: str | None,
    rule: str | None,
    date_from: str | None,
    date_to: str | None,
) -> dict:
    offset = (page_n - 1) * PAGE_LIMIT
    events = client.get_events(
        date_from=date_from,
        date_to=date_to,
        asset_id=asset_id,
        rule=rule,
        severity=severity,
        limit=PAGE_LIMIT,
        offset=offset,
    )
    # Las alertas solo filtran rango en U2; asset/rule/severity aquí (Q5=NFR).
    alerts = client.get_alerts(
        date_from=date_from,
        date_to=date_to,
        limit=PAGE_LIMIT,
        offset=offset,
    )
    entries = [TimelineEntryVM.from_event(e) for e in events.items]
    entries += [TimelineEntryVM.from_alert(a) for a in alerts.items]
    entries.sort(key=lambda e: e.when, reverse=True)
    total = events.total + alerts.total
    vm = PageVM.build(entries, page=page_n, total=total, limit=PAGE_LIMIT)
    return {
        "entries": vm,
        "filters": _filters(asset_id, severity, rule, date_from, date_to),
    }


@router.get("/events", response_class=HTMLResponse)
def events_page(
    request: Request,
    page: str | None = None,
    asset_id: str | None = None,
    severity: str | None = None,
    rule: str | None = None,
    date_from: FromParam = None,
    date_to: ToParam = None,
    client: GuiClient = Depends(get_gui_client),
) -> Response:
    page_n = parse_page(page)
    start = parse_optional_date(date_from, field="from")
    end = parse_optional_date(date_to, field="to")
    if start is not None and end is not None and start > end:
        raise ValidationError("from must be <= to")
    context = _timeline_context(
        client,
        page_n=page_n,
        asset_id=asset_id,
        severity=severity,
        rule=rule,
        date_from=_iso(start),
        date_to=_iso(end),
    )
    return _render(request, "events.html", context)


@router.get("/alerts", response_class=HTMLResponse)
def alerts_page(
    request: Request,
    page: str | None = None,
    asset_id: str | None = None,
    severity: str | None = None,
    rule: str | None = None,
    date_from: FromParam = None,
    date_to: ToParam = None,
    client: GuiClient = Depends(get_gui_client),
) -> Response:
    page_n = parse_page(page)
    start = parse_optional_date(date_from, field="from")
    end = parse_optional_date(date_to, field="to")
    if start is not None and end is not None and start > end:
        raise ValidationError("from must be <= to")
    offset = (page_n - 1) * PAGE_LIMIT
    alerts = client.get_alerts(
        date_from=_iso(start),
        date_to=_iso(end),
        limit=PAGE_LIMIT,
        offset=offset,
    )
    entries = [TimelineEntryVM.from_alert(a) for a in alerts.items]
    entries.sort(key=lambda e: e.when, reverse=True)
    vm = PageVM.build(entries, page=page_n, total=alerts.total, limit=PAGE_LIMIT)
    context: dict = {
        "entries": vm,
        "filters": _filters(asset_id, severity, rule, _iso(start), _iso(end)),
    }
    return _render(request, "alerts.html", context)


# --------------------------------------------------------------------------- #
# ST-M10-05 — salud (FD §3.5)
# --------------------------------------------------------------------------- #


@router.get("/health", response_class=HTMLResponse)
def health_page(
    request: Request,
    client: GuiClient = Depends(get_gui_client),
) -> Response:
    health = client.get_health()
    vm = HealthVM.from_status(health)
    return _render(request, "health.html", {"health": vm})


# --------------------------------------------------------------------------- #
# ST-M10-04 — disparo de discovery (FD §3.4, P1)
# --------------------------------------------------------------------------- #

_DISCOVERY_MESSAGES = {
    409: "ciclo ya en curso",
    503: "descubrimiento no disponible (U4 pendiente)",
}


@router.get("/discovery", response_class=HTMLResponse)
def discovery_form(request: Request) -> Response:
    return _render(request, "discovery.html", {"run": None, "message": None})


@router.post("/discovery", response_class=HTMLResponse)
async def discovery_post(
    request: Request,
    client: GuiClient = Depends(get_gui_client),
) -> Response:
    form = await request.form()
    raw_host = str(form.get("host") or "")
    host = parse_host(raw_host)
    ctx: dict = {"run": None, "message": None}
    try:
        run = client.post_discovery([host], timeout_seconds=30)
    except ApiStatusError as exc:
        if exc.response_code == "scope_violation":
            message = "host fuera de alcance"
        else:
            message = _DISCOVERY_MESSAGES.get(exc.status_code, exc.message)
        ctx["message"] = message
        ctx["message_status"] = exc.status_code
    else:
        ctx["run"] = DiscoveryRunVM(
            run_id=run.run_id,
            status=run.status,
            started_at=run.started_at,
            finished_at=run.finished_at,
            hosts_seen=run.hosts_seen,
            error=run.error,
            message="disparado",
        )
    if request.headers.get("hx-request"):
        return _render(request, "discovery_panel.html", ctx)
    return _render(request, "discovery.html", ctx)


# --------------------------------------------------------------------------- #
# Reporte (ST-M10-06, C7, P2) — mismo servicio para /ui y /api/v1
# --------------------------------------------------------------------------- #


def get_report_service(request: Request) -> ReportService:
    """Dependencia: ``ReportService`` con ``GuiClient`` timeout 30 s (P2).

    Si la app recibió ``http_client`` (tests con MockTransport) se reutiliza;
    en producción se crea un cliente propio con timeout de 30 s.
    """
    service = getattr(request.app.state, "report_service", None)
    if service is None:
        api_base, http_client = request.app.state.gui_config
        if http_client is not None:
            client = GuiClient(api_base, client=http_client)
        else:
            client = GuiClient(api_base, timeout=30.0)
        clock = getattr(request.app.state, "report_clock", None)
        service = ReportService(client, now=clock)
        request.app.state.report_service = service
    return service


def _report_response(service: ReportService, request: Request) -> Response:
    date_from, date_to = parse_date_range(
        request.query_params.get("from"), request.query_params.get("to")
    )
    fmt = parse_format(request.query_params.get("format"))
    artifact = service.generate(ReportRequest(date_from, date_to), fmt)  # type: ignore[arg-type]
    return Response(
        content=artifact.data,
        media_type=artifact.content_type,
        headers={"Content-Disposition": f'attachment; filename="{artifact.filename}"'},
    )


@router.get("/report")
def ui_report(
    request: Request,
    service: ReportService = Depends(get_report_service),
) -> Response:
    """FileResponse del reporte (AC: ``curl -o report.md``)."""
    return _report_response(service, request)


report_api_router = APIRouter(tags=["report"])


@report_api_router.get("/api/v1/report")
def api_report(
    request: Request,
    service: ReportService = Depends(get_report_service),
) -> Response:
    """Contrato C7: U3 sirve el mismo artefacto por la API."""
    return _report_response(service, request)
