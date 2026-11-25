"""Tests de API de exportación (ST-M4-06/07, cabecera exacta, 400 format)."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from sentinel.core.export.service import CSV_HEADER

from .conftest import sample_batch

FULL_RANGE = {"from": "2000-01-01T00:00:00+00:00", "to": "2100-01-01T00:00:00+00:00"}


def test_export_csv_header_exact(client: TestClient, auth: dict[str, str]) -> None:
    client.post("/api/v1/ingest", json=sample_batch(2), headers=auth)
    r = client.get("/api/v1/export", params={**FULL_RANGE, "format": "csv"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    lines = r.text.splitlines()
    assert lines[0] == CSV_HEADER
    assert len(lines) == 3  # header + 2 eventos


def test_export_json_and_empty_range(client: TestClient, auth: dict[str, str]) -> None:
    client.post("/api/v1/ingest", json=sample_batch(1), headers=auth)
    r = client.get("/api/v1/export", params={**FULL_RANGE, "format": "json"})
    assert r.status_code == 200
    records = json.loads(r.text)
    assert len(records) == 1
    assert records[0]["timestamp"]
    empty = client.get(
        "/api/v1/export",
        params={
            "format": "json",
            "from": FULL_RANGE["from"],
            "to": "2026-01-01T00:00:00+00:00",
        },
    )
    assert json.loads(empty.text) == []


def test_export_invalid_format_400(client: TestClient) -> None:
    r = client.get("/api/v1/export", params={**FULL_RANGE, "format": "xml"})
    assert r.status_code == 400
    assert r.json() == {"detail": "format must be csv or json"}


def test_export_from_to_optional_full_range(client: TestClient, auth: dict[str, str]) -> None:
    # ST-M4-06 AC1: curl sin from/to ⇒ rango completo por defecto
    client.post("/api/v1/ingest", json=sample_batch(1), headers=auth)
    r = client.get("/api/v1/export", params={"format": "csv"})
    assert r.status_code == 200
    assert r.text.splitlines()[0] == CSV_HEADER
    assert len(r.text.splitlines()) == 2
