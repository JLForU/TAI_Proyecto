"""Tests de QueryService (ST-M4-06, BR-U2-21..24, Q8 FD)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from sentinel.core.db.database import Database
from sentinel.core.db.repos.alerts import AlertRepository
from sentinel.core.ingestion.service import IngestionService
from sentinel.core.query.service import MAX_LIMIT, QueryService
from sentinel.foundation.models import Batch, DiscoveryObservation

NOW = datetime(2026, 11, 11, 10, 0, 0, tzinfo=UTC)


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    database = Database(str(tmp_path / "query.db"))
    database.startup_checks()
    yield database
    database.close()


@pytest.fixture()
def q(db: Database) -> QueryService:
    return QueryService(db)


def _seed(db: Database, n: int = 3) -> None:
    ing = IngestionService(db, missing_cycles=3)
    items = [
        DiscoveryObservation(
            observed_at=NOW + timedelta(seconds=i),
            ip=f"10.0.0.{i}",
            mac=None,
            hostname=f"h{i}",
            method="arp",
        )
        for i in range(1, n + 1)
    ]
    ing.process(Batch(items=items))
    with db.write() as conn:
        AlertRepository().upsert(
            conn,
            {
                "alert_id": "a-1",
                "condition_id": "C1",
                "rule": "threshold_exceeded",
                "state": "firing",
                "fired_at": "2026-11-11T10:00:00+00:00",
                "measured_value": 42.0,
                "threshold": 10.0,
                "evidence": {},
            },
        )


def test_list_assets_pagination_and_total(db: Database, q: QueryService) -> None:
    _seed(db, 3)
    page = q.list_assets(limit=2, offset=0)
    assert page.total == 3 and len(page.items) == 2 and page.limit == 2
    page2 = q.list_assets(limit=2, offset=2)
    assert len(page2.items) == 1
    ids = {a.asset_id for a in page.items} | {a.asset_id for a in page2.items}
    assert len(ids) == 3
    assert page.items[0].ips  # ips resueltas


def test_limit_clamp(db: Database, q: QueryService) -> None:
    assert q.list_assets(limit=5000).limit == MAX_LIMIT
    assert q.list_assets(limit=0).limit == 1
    assert q.list_assets(offset=-3).offset == 0
    assert q.list_assets().limit == 100


def test_get_asset_detail_and_404(db: Database, q: QueryService) -> None:
    _seed(db, 1)
    aid = q.list_assets().items[0].asset_id
    detail = q.get_asset(aid)
    assert detail is not None
    assert detail.ips and detail.recent_observations and detail.recent_events
    assert detail.recent_observations[0].payload["ip"] == "10.0.0.1"
    assert q.get_asset("does-not-exist") is None


def test_list_events_filters(db: Database, q: QueryService) -> None:
    from sentinel.core.db.repos.events import EventRepository

    _seed(db, 2)
    # eventos de inventario: severity=info, rule=NULL
    page = q.list_events(severity="info")
    assert page.total == 2
    # evento con rule (patrón de U6) insertado directamente
    with db.write() as conn:
        EventRepository().save_ignore(
            conn,
            {
                "event_id": "00000000-0000-0000-0000-0000000000aa",
                "type": "metric_threshold",
                "asset_id": None,
                "severity": "warning",
                "rule": "threshold_exceeded",
                "occurred_at": datetime.now(UTC).isoformat(),
                "details": {"measured_value": 42},
            },
        )
    assert q.list_events(rule="threshold_exceeded").total == 1
    assert q.list_events(rule="no-such-rule").total == 0
    assert q.list_events(severity="no-such").total == 0
    # occurred_at = instante de ingesta (tiempo real): rangos calculados
    full = q.list_events(date_from="2000-01-01T00:00:00+00:00", date_to="2100-01-01T00:00:00+00:00")
    assert full.total == 3
    future = q.list_events(date_from=(datetime.now(UTC) + timedelta(hours=1)).isoformat())
    assert future.total == 0
    past = q.list_events(date_to=(datetime.now(UTC) - timedelta(hours=1)).isoformat())
    assert past.total == 0


def test_list_alerts_by_state(db: Database, q: QueryService) -> None:
    _seed(db, 1)
    page = q.list_alerts(state="firing")
    assert page.total == 1 and page.items[0].measured_value == 42.0
    assert q.list_alerts(state="resolved").total == 0
