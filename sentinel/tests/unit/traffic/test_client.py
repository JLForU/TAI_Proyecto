"""Cliente de export (U5, BR-U5-23..26, P13): Bearer, chunking, sin reconcile."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from sentinel.foundation.errors import IngestionError
from sentinel.foundation.models import ArpObservation, FlowPair, TrafficObservation
from sentinel.traffic.client import IngestClient

NOW = datetime(2026, 11, 19, 12, 0, 0, tzinfo=UTC)


def _traffic(i: int = 0) -> TrafficObservation:
    return TrafficObservation(
        observed_at=NOW + timedelta(seconds=5),
        window_start=NOW,
        window_end=NOW + timedelta(seconds=5),
        interface="eth0",
        protocol="tcp",
        packet_length_bytes=64 + i,
        bytes_per_second=12.8,
        packets=1,
        flows=1,
        pairs=[FlowPair(src_ip=f"10.0.0.{i % 250 + 1}", dst_ip="10.0.1.1")],
        window_id=None,
    )


def _arp(i: int = 0) -> ArpObservation:
    return ArpObservation(
        observed_at=NOW,
        interface="eth0",
        opcode=1,
        psrc=f"10.0.0.{i % 250 + 1}",
        pdst="10.0.0.99",
        hwsrc=f"aa:bb:cc:dd:ee:{i % 250:02x}",
        hwdst="ff:ff:ff:ff:ff:ff",
    )


def _items(n: int) -> list:
    # lote mixto traffic+arp (BR-U5-23)
    items: list = []
    for i in range(n):
        items.append(_traffic(i) if i % 2 == 0 else _arp(i))
    return items


def _client(handler, token: str = "s3cret") -> IngestClient:
    return IngestClient(
        base_url="http://sentinel-core:8080",
        token=token,
        transport=httpx.MockTransport(handler),
    )


def test_single_post_per_window() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(202, json={"accepted": 3, "deduplicated": 0, "events_persisted": 0})

    client = _client(handler)
    result = client.post_batch(_items(3))
    assert result["accepted"] == 3
    assert seen["url"] == "http://sentinel-core:8080/api/v1/ingest"
    assert len(seen["body"]["items"]) == 3
    sources = {item["source"] for item in seen["body"]["items"]}
    assert sources == {"traffic", "arp"}


def test_bearer_header() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(202, json={"accepted": 1, "deduplicated": 0})

    _client(handler, token="tok-123").post_batch(_items(1))
    assert seen["auth"] == "Bearer tok-123"


def test_no_reconcile_field() -> None:
    body: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body.update(json.loads(request.content))
        return httpx.Response(202, json={"accepted": 1, "deduplicated": 0})

    _client(handler).post_batch(_items(1))
    assert "reconcile" not in body


def test_chunked_export() -> None:
    posts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        posts.append(len(payload["items"]))
        return httpx.Response(202, json={"accepted": len(payload["items"]), "deduplicated": 0})

    _client(handler).post_batch(_items(2500))
    assert posts == [1000, 1000, 500]


def test_empty_batch_does_not_post() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("no debe haber POST con lote vacío")

    result = _client(handler).post_batch([])
    assert result["accepted"] == 0


def test_retry_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    import sentinel.foundation.retry as retry_mod

    monkeypatch.setattr(retry_mod.time, "sleep", lambda _s: None)
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500, json={"detail": "boom"})

    with pytest.raises(IngestionError, match="ingest failed after 5 attempts"):
        _client(handler).post_batch(_items(1))
    assert calls["n"] == 5


def test_4xx_is_definitive_no_retry() -> None:
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, json={"detail": "bad token"})

    with pytest.raises(IngestionError, match="ingest rejected: 401"):
        _client(handler).post_batch(_items(1))
    assert calls["n"] == 1
