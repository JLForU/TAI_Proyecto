"""Baseline de latencia informativo (NFR-U2-PERF-01/02, P9).

Sin asserts de umbral (baseline local); imprime p50/p95 de las rutas de
consulta sobre un lote representativo. Se ejecuta en el suite normal.
"""

from __future__ import annotations

import statistics
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sentinel.core.api.app import create_app
from sentinel.core.config import CoreSettings

N_EVENTS = 500
ROUNDS = 10


@pytest.fixture()
def seeded_client(tmp_path: Path) -> TestClient:
    settings = CoreSettings(
        db_path=str(tmp_path / "latency.db"),
        ingest_token="t",
        page_limit=100,
        missing_cycles=3,
    )
    app = create_app(settings, metrics_port=None)
    with TestClient(app) as client:
        # siembra directa de eventos (sin pasar por ingest para el volumen)
        from sentinel.core.db.repos.events import EventRepository

        now = datetime.now(UTC)
        with client.app.state.db.write() as conn:
            repo = EventRepository()
            for i in range(N_EVENTS):
                repo.save_ignore(
                    conn,
                    {
                        "event_id": f"10000000-0000-0000-0000-{i:012d}",
                        "type": "metric_threshold",
                        "asset_id": None,
                        "severity": "warning",
                        "rule": "threshold_exceeded",
                        "occurred_at": (now - timedelta(seconds=i)).isoformat(),
                        "details": {"measured_value": float(i)},
                    },
                )
        yield client


def _p95(samples: list[float]) -> float:
    ordered = sorted(samples)
    idx = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
    return ordered[idx]


def test_latency_baseline_report(seeded_client: TestClient, capsys: pytest.CaptureFixture) -> None:
    routes = [
        ("GET", "/api/v1/events", {"limit": 100}),
        ("GET", "/api/v1/events", {"limit": 100, "severity": "warning"}),
        ("GET", "/api/v1/assets", {"limit": 100}),
        ("GET", "/api/v1/health", None),
        (
            "GET",
            "/api/v1/export",
            {
                "format": "json",
                "from": "2000-01-01T00:00:00+00:00",
                "to": "2100-01-01T00:00:00+00:00",
            },
        ),
    ]
    lines = ["latency baseline (local, informational):"]
    for _method, path, params in routes:
        samples: list[float] = []
        for _ in range(ROUNDS):
            start = time.perf_counter()
            response = seeded_client.get(path, params=params)
            samples.append((time.perf_counter() - start) * 1000)
            assert response.status_code == 200
        lines.append(
            f"  {path} {params}: p50={statistics.median(samples):.1f}ms"
            f" p95={_p95(samples):.1f}ms n={len(samples)}"
        )
    with capsys.disabled():
        print("\n".join(lines))
