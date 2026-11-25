"""Cliente de ingesta (U4, BR-U4-21/22): Bearer, reintento y 4xx definitivos."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest

from sentinel.discovery.client import IngestClient, to_observations
from sentinel.discovery.domain import HostFinding
from sentinel.foundation.errors import IngestionError


def _items(n: int = 2) -> list:
    findings = [
        HostFinding(ip=f"10.0.0.{i}", method="arp", mac=f"aa:bb:cc:dd:ee:0{i}")
        for i in range(1, n + 1)
    ]
    return to_observations(findings, datetime(2026, 11, 16, 12, 0, tzinfo=UTC))


def test_single_post_per_cycle_happy_path() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(202, json={"accepted": 2, "events_persisted": 0})

    client = IngestClient(
        base_url="http://sentinel-core:8080", token="s3cret", transport=httpx.MockTransport(handler)
    )
    result = client.post_ingest(_items(), reconcile=True)
    assert result["accepted"] == 2
    assert seen["url"] == "http://sentinel-core:8080/api/v1/ingest"
    assert seen["auth"] == "Bearer s3cret"
    assert seen["body"]["reconcile"] is True
    assert len(seen["body"]["items"]) == 2
    assert seen["body"]["items"][0]["source"] == "discovery"
    assert seen["body"]["items"][0]["os_name"] is None


def test_reconcile_false_payload() -> None:
    body: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body.update(json.loads(request.content))
        return httpx.Response(202, json={"accepted": 0})

    client = IngestClient(base_url="http://x", token="t", transport=httpx.MockTransport(handler))
    client.post_ingest(_items(1), reconcile=False)
    assert body["reconcile"] is False


def test_retry_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    import sentinel.foundation.retry as retry_mod

    monkeypatch.setattr(retry_mod.time, "sleep", lambda _s: None)
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500, json={"detail": "boom"})

    client = IngestClient(base_url="http://x", token="t", transport=httpx.MockTransport(handler))
    with pytest.raises(IngestionError, match="ingest failed after 5 attempts"):
        client.post_ingest(_items(1), reconcile=True)
    assert calls["n"] == 5


def test_4xx_is_definitive_no_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    import sentinel.foundation.retry as retry_mod

    monkeypatch.setattr(retry_mod.time, "sleep", lambda _s: None)
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, json={"detail": "bad token"})

    client = IngestClient(base_url="http://x", token="bad", transport=httpx.MockTransport(handler))
    with pytest.raises(IngestionError, match="ingest rejected: 401"):
        client.post_ingest(_items(1), reconcile=True)
    assert calls["n"] == 1


def test_network_error_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    import sentinel.foundation.retry as retry_mod

    monkeypatch.setattr(retry_mod.time, "sleep", lambda _s: None)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("down", request=request)
        return httpx.Response(202, json={"accepted": 1})

    client = IngestClient(base_url="http://x", token="t", transport=httpx.MockTransport(handler))
    result = client.post_ingest(_items(1), reconcile=True)
    assert result["accepted"] == 1
    assert calls["n"] == 3


def test_default_token_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTINEL_INGEST_TOKEN", "env-token")
    monkeypatch.setenv("SENTINEL_API_BASE", "http://env-core:8080")
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        seen["url"] = str(request.url)
        return httpx.Response(202, json={"accepted": 0})

    client = IngestClient(transport=httpx.MockTransport(handler))
    client.post_ingest([], reconcile=True)
    assert seen["auth"] == "Bearer env-token"
    assert seen["url"] == "http://env-core:8080/api/v1/ingest"
