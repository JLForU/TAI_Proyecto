"""Fixtures compartidas para tests de API (TestClient + SQLite temporal)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from sentinel.core.api.app import create_app
from sentinel.core.config import CoreSettings

TOKEN = "test-token"


@pytest.fixture()
def settings(tmp_path) -> CoreSettings:  # type: ignore[no-untyped-def]
    return CoreSettings(
        db_path=str(tmp_path / "api.db"),
        ingest_token=TOKEN,
        page_limit=100,
        missing_cycles=3,
    )


@pytest.fixture()
def app(settings: CoreSettings):  # type: ignore[no-untyped-def]
    # metrics_port=None: los tests de API no abren el 9108 (evita conflictos
    # de puerto); test_metrics.py lo levanta con puerto efímero.
    return create_app(settings, metrics_port=None)


@pytest.fixture()
def client(app) -> Iterator[TestClient]:  # type: ignore[no-untyped-def]
    # raise_server_exceptions=False ⇒ el handler 500 de api/errors.py responde
    # JSON sin stacktrace en lugar de re-lanzar (FD §5).
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture()
def auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


def sample_batch(n: int = 1, *, mac: str = "aa:bb:cc:dd:ee:ff") -> dict:
    """Lote ``n`` observaciones de discovery con IPs 10.0.0.1..n."""
    now = datetime.now(UTC)
    return {
        "items": [
            {
                "source": "discovery",
                "observed_at": (now + timedelta(seconds=i)).isoformat(),
                "ip": f"10.0.0.{i}",
                "mac": mac,
                "hostname": f"host{i}",
                "method": "arp",
            }
            for i in range(1, n + 1)
        ]
    }
