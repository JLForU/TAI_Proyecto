"""``GET /api/v1/export`` — exportación bajo demanda CSV/JSON (ST-M4-06/07)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from ..export.service import ExportService
from .deps import get_export

router = APIRouter(tags=["export"])

_FULL_FROM = "2000-01-01T00:00:00+00:00"
_FULL_TO = "2100-01-01T00:00:00+00:00"


@router.get("/export")
def export_evidence(
    fmt: Annotated[str, Query(alias="format", description="csv|json")],
    date_from: Annotated[str, Query(alias="from")] = _FULL_FROM,
    date_to: Annotated[str, Query(alias="to")] = _FULL_TO,
    export: ExportService = Depends(get_export),
) -> Response:
    if fmt not in {"csv", "json"}:
        raise HTTPException(status_code=400, detail="format must be csv or json")
    body = export.export(date_from=date_from, date_to=date_to, fmt=fmt)  # type: ignore[arg-type]
    media = "text/csv; charset=utf-8" if fmt == "csv" else "application/json"
    return Response(content=body, media_type=media)
