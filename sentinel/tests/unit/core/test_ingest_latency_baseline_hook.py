"""Baseline de latencia de ingesta CON hook baseline (NFR-U6-PERF-01).

Informativo: imprime p50/p95 de ``POST /api/v1/ingest`` con el
``ConditionService`` enlazado (3 upserts + 1 evaluate por obs traffic).
**Sin assert de duración** (sin gate en CI); la envolvente NFR-PERF-03
(p95 < 500 ms) se valida en lab/Build & Test con este mismo test (``-s``).
"""

from __future__ import annotations

import statistics
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from sentinel.core.api.app import create_app
from sentinel.core.config import CoreSettings

N_REQUESTS = 100
T0 = datetime(2026, 11, 23, 9, 0, 0, tzinfo=UTC)


def test_ingest_latency_with_baseline_hook(tmp_path: Path) -> None:
    settings = CoreSettings(
        db_path=str(tmp_path / "latency_hook.db"),
        ingest_token="t",
        page_limit=100,
        missing_cycles=3,
    )
    auth = {"Authorization": "Bearer t"}
    durations_ms: list[float] = []

    with TestClient(create_app(settings, metrics_port=None)) as client:
        # el hook está enlazado por create_app (app.state.condition)
        assert getattr(client.app.state, "condition", None) is not None
        assert client.app.state.ingestion._on_accepted is not None

        for i in range(N_REQUESTS):
            at = T0 + timedelta(seconds=i)
            payload = {
                "items": [
                    {
                        "source": "traffic",
                        "observed_at": at.isoformat(),
                        "sensor_id": "sensor-0",
                        "window_start": (at - timedelta(seconds=5)).isoformat(),
                        "window_end": at.isoformat(),
                        "interface": "eth0",
                        "protocol": "tcp",
                        "packet_length_bytes": 600,
                        "bytes_per_second": 120.0,
                        "packets": 5,
                        "flows": 1,
                        "pairs": [{"src_ip": "10.0.0.1", "dst_ip": "10.0.1.1"}],
                    }
                ]
            }
            start = time.perf_counter()
            resp = client.post("/api/v1/ingest", json=payload, headers=auth)
            durations_ms.append((time.perf_counter() - start) * 1000)
            assert resp.status_code == 202, resp.text
            assert resp.json()["accepted"] == 1, resp.text

    ordered = sorted(durations_ms)
    p50 = statistics.median(ordered)
    p95 = ordered[max(0, int(len(ordered) * 0.95) - 1)]
    print(
        f"[NFR-U6-PERF-01] ingest+baseline_hook n={N_REQUESTS} "
        f"p50={p50:.1f}ms p95={p95:.1f}ms max={ordered[-1]:.1f}ms"
    )
    # Sin assert de duración (informativo; NFR-PERF-03 se valida en lab)
