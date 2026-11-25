"""Consultas paginadas: ``/assets``, ``/events``, ``/alerts`` (ST-M4-06)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from ..errors import NotFoundError
from ..query.service import QueryService
from .deps import get_query
from .schemas import AlertOut, AssetDetail, AssetSummary, EventOut, Page

router = APIRouter(tags=["query"])

LimitParam = Annotated[int | None, Query(ge=1, description="1..1000, default 100")]
OffsetParam = Annotated[int, Query(ge=0)]


@router.get("/assets", response_model=Page[AssetSummary])
def list_assets(
    query: QueryService = Depends(get_query),
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: LimitParam = None,
    offset: OffsetParam = 0,
) -> Page[AssetSummary]:
    return query.list_assets(status=status_filter, limit=limit, offset=offset)


@router.get("/assets/{asset_id}", response_model=AssetDetail)
def get_asset(asset_id: str, query: QueryService = Depends(get_query)) -> AssetDetail:
    detail = query.get_asset(asset_id)
    if detail is None:
        raise NotFoundError(f"asset {asset_id} not found")
    return detail


@router.get("/events", response_model=Page[EventOut])
def list_events(
    query: QueryService = Depends(get_query),
    date_from: Annotated[str | None, Query(alias="from")] = None,
    date_to: Annotated[str | None, Query(alias="to")] = None,
    asset_id: str | None = None,
    rule: str | None = None,
    severity: str | None = None,
    limit: LimitParam = None,
    offset: OffsetParam = 0,
) -> Page[EventOut]:
    return query.list_events(
        date_from=date_from,
        date_to=date_to,
        asset_id=asset_id,
        rule=rule,
        severity=severity,
        limit=limit,
        offset=offset,
    )


@router.get("/alerts", response_model=Page[AlertOut])
def list_alerts(
    query: QueryService = Depends(get_query),
    date_from: Annotated[str | None, Query(alias="from")] = None,
    date_to: Annotated[str | None, Query(alias="to")] = None,
    state: str | None = None,
    limit: LimitParam = None,
    offset: OffsetParam = 0,
) -> Page[AlertOut]:
    return query.list_alerts(
        date_from=date_from, date_to=date_to, state=state, limit=limit, offset=offset
    )
