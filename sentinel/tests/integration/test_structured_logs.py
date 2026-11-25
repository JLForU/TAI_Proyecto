"""ST-M4-05: JSON Lines de evidencia (jsonl_fields, source_kind)."""

from __future__ import annotations

import io
import json
import logging
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from sentinel.core import evidence as evidence_mod
from sentinel.core.api.app import create_app
from sentinel.core.config import CoreSettings
from sentinel.foundation.logging import get_logger

REQUIRED_EVIDENCE_FIELDS = (
    "asset",
    "pair",
    "method",
    "protocol",
    "condition",
    "rule",
    "threshold",
    "measured_value",
    "result",
)
BASE_LOG_FIELDS = ("ts", "level", "component", "event", "msg")
VALID_KINDS = {"observation", "inference", "event", "alert"}


def _run_and_collect(fn) -> list[dict]:  # type: ignore[no-untyped-def]
    """Ejecuta ``fn`` capturando las líneas JSON de ``core.evidence``."""
    logger = get_logger("core.evidence")
    handler = next(h for h in logger.handlers if isinstance(h, logging.StreamHandler))
    buffer = io.StringIO()
    original = handler.stream
    handler.stream = buffer
    try:
        fn()
    finally:
        handler.stream = original
    return [json.loads(raw) for raw in buffer.getvalue().splitlines() if raw.strip()]


def _client(tmp_path):  # type: ignore[no-untyped-def]
    settings = CoreSettings(
        db_path=str(tmp_path / "logs.db"), ingest_token="t", page_limit=100, missing_cycles=3
    )
    return TestClient(create_app(settings, metrics_port=None), raise_server_exceptions=False)


def test_jsonl_fields(tmp_path) -> None:  # type: ignore[no-untyped-def]
    now = datetime.now(UTC).isoformat()
    batch = {
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
    }

    def action() -> None:
        with _client(tmp_path) as client:
            r = client.post("/api/v1/ingest", json=batch, headers={"Authorization": "Bearer t"})
            assert r.status_code == 202

    records = _run_and_collect(action)
    assert records, "debe haber al menos una línea de evidencia"
    for record in records:
        # BR-09: campos base del formatter U1
        for field in BASE_LOG_FIELDS:
            assert field in record, f"falta {field} en {record}"
        # BR-10: ISO 8601 UTC con offset
        assert record["ts"].endswith("Z") or "+" in record["ts"] or record["ts"].endswith("00:00")
        # BR-U2-25: los 9 campos de evidencia presentes (pueden ser null)
        for field in REQUIRED_EVIDENCE_FIELDS:
            assert field in record, f"falta {field} de evidencia en {record}"
        # BR-U2-26: kind válido
        assert record["kind"] in VALID_KINDS


def test_source_kind(tmp_path) -> None:  # type: ignore[no-untyped-def]
    now = datetime.now(UTC).isoformat()

    def action() -> None:
        evidence_mod.emit("inference", "baseline_evaluated", result="within_baseline")
        evidence_mod.emit("alert", "threshold_exceeded", rule="r1", threshold=10, measured_value=42)
        with _client(tmp_path) as client:
            client.post(
                "/api/v1/ingest",
                json={
                    "items": [
                        {
                            "source": "discovery",
                            "observed_at": now,
                            "ip": "10.0.0.5",
                            "mac": "aa:bb:cc:dd:ee:05",
                            "hostname": "h5",
                            "method": "arp",
                        }
                    ]
                },
                headers={"Authorization": "Bearer t"},
            )

    records = _run_and_collect(action)
    kinds = {r["kind"] for r in records}
    # observación (ingesta), inferencia y alerta (emisión directa) + evento (inventario)
    assert "observation" in kinds
    assert "inference" in kinds
    assert "alert" in kinds
    assert "event" in kinds
    alert = next(r for r in records if r["kind"] == "alert")
    assert alert["rule"] == "r1"
    assert alert["threshold"] == 10
    assert alert["measured_value"] == 42
