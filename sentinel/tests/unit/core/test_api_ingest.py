"""Tests de API de ingesta (ST-M4-01/03, FD §3.1/§5, TS-U2-04)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sentinel.core.api.app import create_app
from sentinel.core.config import CoreSettings
from sentinel.foundation.errors import StorageError

from .conftest import TOKEN, sample_batch


def test_ingest_accepted_202(client: TestClient, auth: dict[str, str]) -> None:
    r = client.post("/api/v1/ingest", json=sample_batch(2), headers=auth)
    assert r.status_code == 202
    body = r.json()
    assert body["accepted"] == 2
    assert body["deduplicated"] == 0
    assert body["events_persisted"] == 2
    assert body["ingest_id"]


def test_ingest_401_without_or_wrong_token(client: TestClient) -> None:
    r = client.post("/api/v1/ingest", json=sample_batch())
    assert r.status_code == 401 and r.json() == {"detail": "unauthorized"}
    r = client.post(
        "/api/v1/ingest",
        json=sample_batch(),
        headers={"Authorization": "Bearer wrong"},
    )
    assert r.status_code == 401 and r.json() == {"detail": "unauthorized"}


def test_ingest_403_when_token_not_configured(tmp_path) -> None:  # type: ignore[no-untyped-def]
    settings = CoreSettings(db_path=str(tmp_path / "no-token.db"), ingest_token="")
    with TestClient(create_app(settings, metrics_port=None)) as client:
        r = client.post(
            "/api/v1/ingest",
            json=sample_batch(),
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
    assert r.status_code == 403
    assert r.json() == {"detail": "ingest token not configured"}


def test_ingest_422_invalid_payload(client: TestClient, auth: dict[str, str]) -> None:
    r = client.post(
        "/api/v1/ingest",
        json={"items": [{"source": "bogus"}]},
        headers=auth,
    )
    assert r.status_code == 422
    assert "detail" in r.json()


def test_ingest_400_missing_required_field(client: TestClient, auth: dict[str, str]) -> None:
    # ST-M4-01 AC2: campo obligatorio faltante ⇒ 400 con el campo inválido
    r = client.post("/api/v1/ingest", json={}, headers=auth)
    assert r.status_code == 400
    assert r.json()["detail"][0]["type"] == "missing"


def test_ingest_idempotent_double_post(client: TestClient, auth: dict[str, str]) -> None:
    batch = sample_batch(3)
    first = client.post("/api/v1/ingest", json=batch, headers=auth)
    second = client.post("/api/v1/ingest", json=batch, headers=auth)
    assert first.status_code == second.status_code == 202
    assert first.json()["accepted"] == 3
    assert second.json()["accepted"] == 0
    assert second.json()["deduplicated"] == 3
    assert second.json()["events_persisted"] == 0
    events_total = client.get("/api/v1/events").json()["total"]
    assert events_total == first.json()["events_persisted"]


def test_ingest_503_storage_error_without_partial_writes(
    client: TestClient, auth: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise StorageError("disk full")

    monkeypatch.setattr(client.app.state.ingestion, "process", boom)
    r = client.post("/api/v1/ingest", json=sample_batch(2), headers=auth)
    assert r.status_code == 503 and r.json() == {"detail": "storage unavailable"}


def test_ingest_500_without_traceback(
    client: TestClient, auth: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("unexpected bug")

    monkeypatch.setattr(client.app.state.ingestion, "process", boom)
    r = client.post("/api/v1/ingest", json=sample_batch(), headers=auth)
    assert r.status_code == 500
    assert r.json() == {"detail": "internal error"}
    assert "Traceback" not in r.text
    assert "unexpected bug" not in r.text
