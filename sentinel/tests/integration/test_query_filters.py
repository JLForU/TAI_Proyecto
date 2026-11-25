"""ST-M4-07 AC2: los filtros de rango temporal devuelven solo el rango."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from sentinel.core.api.app import create_app
from sentinel.core.config import CoreSettings
from sentinel.core.db.repos.events import EventRepository


def test_time_range(tmp_path) -> None:  # type: ignore[no-untyped-def]
    settings = CoreSettings(
        db_path=str(tmp_path / "filters.db"), ingest_token="t", page_limit=100, missing_cycles=3
    )
    base = datetime(2026, 11, 11, 12, 0, 0, tzinfo=UTC)
    app = create_app(settings, metrics_port=None)
    with TestClient(app, raise_server_exceptions=False) as client:
        with client.app.state.db.write() as conn:
            repo = EventRepository()
            for i, hours in enumerate((-5, 0, 5)):
                repo.save_ignore(
                    conn,
                    {
                        "event_id": f"20000000-0000-0000-0000-{i:012d}",
                        "type": "asset_first_seen",
                        "asset_id": None,
                        "severity": "info",
                        "rule": None,
                        "occurred_at": (base + timedelta(hours=hours)).isoformat(),
                        "details": {},
                    },
                )

        full = client.get(
            "/api/v1/events",
            params={
                "from": (base - timedelta(days=1)).isoformat(),
                "to": (base + timedelta(days=1)).isoformat(),
            },
        ).json()
        assert full["total"] == 3

        # solo la hora central dentro del rango
        window = client.get(
            "/api/v1/events",
            params={
                "from": (base - timedelta(minutes=30)).isoformat(),
                "to": (base + timedelta(minutes=30)).isoformat(),
            },
        ).json()
        assert window["total"] == 1
        assert window["items"][0]["occurred_at"] == base.isoformat()

        # rango futuro ⇒ vacío
        future = client.get(
            "/api/v1/events", params={"from": (base + timedelta(days=30)).isoformat()}
        ).json()
        assert future["total"] == 0
        assert future["items"] == []
