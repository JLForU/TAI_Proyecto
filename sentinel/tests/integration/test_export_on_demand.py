"""ST-M4-06 AC2: export bajo demanda, sin scheduler ni push (no_scheduler)."""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from sentinel.core.api.app import create_app
from sentinel.core.config import CoreSettings

_SCHEDULER_MARKERS = ("sched", "apscheduler", "celery", "periodic", "export")


def test_no_scheduler(tmp_path) -> None:  # type: ignore[no-untyped-def]
    settings = CoreSettings(
        db_path=str(tmp_path / "nodata.db"), ingest_token="t", page_limit=100, missing_cycles=3
    )
    app = create_app(settings, metrics_port=None)
    before = {
        t.name
        for t in threading.enumerate()
        if any(marker in t.name.lower() for marker in _SCHEDULER_MARKERS)
    }
    with TestClient(app, raise_server_exceptions=False) as client:
        auth = {"Authorization": "Bearer t"}
        now = datetime.now(UTC).isoformat()
        client.post(
            "/api/v1/ingest",
            json={
                "items": [
                    {
                        "source": "discovery",
                        "observed_at": now,
                        "ip": "10.0.0.1",
                        "mac": "aa:bb:cc:dd:ee:ff",
                        "hostname": "h1",
                        "method": "arp",
                    }
                ]
            },
            headers=auth,
        )
        # sin solicitud explícita no hay export: no se escriben artefactos
        # la exportación SOLO ocurre bajo demanda
        r = client.get("/api/v1/export", params={"format": "csv"})
        assert r.status_code == 200
        assert r.text.splitlines()[0].startswith("timestamp,")
        # y una segunda exportación bajo demanda produce el mismo resultado
        r2 = client.get("/api/v1/export", params={"format": "csv"})
        assert r2.text == r.text

    after_threads = {
        t.name
        for t in threading.enumerate()
        if any(marker in t.name.lower() for marker in _SCHEDULER_MARKERS)
    }
    assert after_threads <= before  # ningún hilo de scheduler nuevo
    # solo archivos de SQLite en tmp (ningún artefacto de export automático)
    for path in Path(tmp_path).rglob("*"):
        if path.is_file():
            assert str(path).endswith((".db", "-wal", "-shm")), path
