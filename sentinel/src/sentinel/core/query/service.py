"""QueryService — lecturas de inventario, eventos y alertas (ST-M4-06).

Clamp de paginación: ``limit`` default ``page_limit`` (100), tope 1000;
``offset`` ≥ 0. Orden estable: activos por ``last_seen DESC``, eventos por
``occurred_at DESC``, alertas por ``fired_at DESC`` (índices ⇒ USING INDEX).
"""

from __future__ import annotations

import json
from typing import Any

from ..api.schemas import AlertOut, AssetDetail, AssetSummary, EventOut, ObservationOut, Page
from ..db.database import Database
from ..db.repos.alerts import AlertRepository
from ..db.repos.assets import AssetRepository
from ..db.repos.events import EventRepository
from ..db.repos.observations import ObservationRepository

__all__ = ["QueryService", "MAX_LIMIT"]

MAX_LIMIT = 1000


def _clamp(limit: int | None, offset: int | None, default: int) -> tuple[int, int]:
    lim = default if limit is None else int(limit)
    lim = max(1, min(lim, MAX_LIMIT))
    off = 0 if offset is None else max(0, int(offset))
    return lim, off


class QueryService:
    def __init__(
        self,
        db: Database,
        *,
        assets: AssetRepository | None = None,
        events: EventRepository | None = None,
        alerts: AlertRepository | None = None,
        observations: ObservationRepository | None = None,
        page_limit: int = 100,
    ) -> None:
        self._db = db
        self._assets = assets or AssetRepository()
        self._events = events or EventRepository()
        self._alerts = alerts or AlertRepository()
        self._observations = observations or ObservationRepository()
        self._page_limit = page_limit

    def list_assets(
        self,
        *,
        status: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Page[AssetSummary]:
        lim, off = _clamp(limit, offset, self._page_limit)
        with self._db.read() as conn:
            rows, total = self._assets.list(conn, status=status, limit=lim, offset=off)
            items = [AssetSummary(**self._assets.summary(conn, r)) for r in rows]
        return Page(items=items, total=total, limit=lim, offset=off)

    def get_asset(self, asset_id: str) -> AssetDetail | None:
        with self._db.read() as conn:
            r = self._assets.get(conn, asset_id)
            if r is None:
                return None
            obs = self._observations.list_by_asset(conn, asset_id, limit=200)
            ev_rows, _ = self._events.list(conn, asset_id=asset_id, limit=100, offset=0)
            return AssetDetail(
                **self._assets.summary(conn, r),
                os_name=r["os_name"],
                os_provenance=r["os_provenance"] or "unknown",
                recent_observations=[
                    ObservationOut(
                        dedup_key=str(o["dedup_key"]),
                        source=str(o["source"]),
                        kind=str(o["kind"]),
                        sensor_id=o["sensor_id"],
                        observed_at=str(o["observed_at"]),
                        payload=_json_obj(o["payload"]),
                    )
                    for o in obs
                ],
                recent_events=[_event_out(e) for e in ev_rows],
            )

    def list_events(
        self,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        asset_id: str | None = None,
        rule: str | None = None,
        severity: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Page[EventOut]:
        lim, off = _clamp(limit, offset, self._page_limit)
        with self._db.read() as conn:
            rows, total = self._events.list(
                conn,
                date_from=date_from,
                date_to=date_to,
                asset_id=asset_id,
                rule=rule,
                severity=severity,
                limit=lim,
                offset=off,
            )
            items = [_event_out(r) for r in rows]
        return Page(items=items, total=total, limit=lim, offset=off)

    def list_alerts(
        self,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        state: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Page[AlertOut]:
        lim, off = _clamp(limit, offset, self._page_limit)
        with self._db.read() as conn:
            rows, total = self._alerts.list(
                conn, date_from=date_from, date_to=date_to, state=state, limit=lim, offset=off
            )
            items = [
                AlertOut(
                    alert_id=str(r["alert_id"]),
                    condition_id=str(r["condition_id"]),
                    rule=str(r["rule"]),
                    metric_key=r["metric_key"],
                    asset_id=r["asset_id"],
                    state=str(r["state"]),
                    measured_value=r["measured_value"],
                    threshold=r["threshold"],
                    fired_at=str(r["fired_at"]),
                    resolved_at=r["resolved_at"],
                )
                for r in rows
            ]
        return Page(items=items, total=total, limit=lim, offset=off)


def _json_obj(value: Any) -> dict:
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:  # pragma: no cover - dato corrupto
            return {}
    return value if isinstance(value, dict) else {}


def _event_out(r) -> EventOut:  # type: ignore[no-untyped-def]
    return EventOut(
        event_id=str(r["event_id"]),
        type=str(r["type"]),
        asset_id=r["asset_id"],
        severity=str(r["severity"]),
        rule=r["rule"],
        occurred_at=str(r["occurred_at"]),
        details=_json_obj(r["details"]),
    )
