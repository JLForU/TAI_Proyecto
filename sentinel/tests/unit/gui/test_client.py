"""Tests de ``gui.client`` con ``httpx.MockTransport`` (NFR-U3-MNT-02, P7)."""

from __future__ import annotations

import json

import httpx
import pytest

from sentinel.gui.client import API_BASE, GuiClient
from sentinel.gui.errors import ApiStatusError, CoreUnavailableError


def _client(handler: httpx.MockTransport) -> GuiClient:
    return GuiClient(API_BASE, transport=handler)


class TestTransport:
    def test_base_url_default(self) -> None:
        with GuiClient() as client:
            assert client.base_url.rstrip("/") == API_BASE

    def test_connection_error_raises_core_unavailable(self) -> None:
        def boom(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused", request=request)

        with _client(httpx.MockTransport(boom)) as client, pytest.raises(CoreUnavailableError):
            client.get_health()

    def test_timeout_raises_core_unavailable(self) -> None:
        def slow(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("timed out", request=request)

        with _client(httpx.MockTransport(slow)) as client, pytest.raises(CoreUnavailableError):
            client.get_assets()


class TestEndpoints:
    def test_get_assets_parses_page(self) -> None:
        body = {
            "items": [
                {
                    "asset_id": "a-1",
                    "ips": ["10.0.0.10"],
                    "status": "present",
                    "first_seen": "2026-11-01T00:00:00+00:00",
                    "last_seen": "2026-11-11T10:00:00+00:00",
                }
            ],
            "total": 1,
            "limit": 100,
            "offset": 0,
        }
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json=body)

        with _client(httpx.MockTransport(handler)) as client:
            page = client.get_assets(limit=100, offset=0, status="present")
        assert page.total == 1
        assert page.items[0].asset_id == "a-1"
        assert "status=present" in str(seen[0].url)
        assert seen[0].url.path == "/api/v1/assets"

    def test_get_events_sends_from_to_aliases(self) -> None:
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json={"items": [], "total": 0, "limit": 100, "offset": 0})

        with _client(httpx.MockTransport(handler)) as client:
            client.get_events(date_from="2026-11-01", date_to="2026-11-07", rule="R-01")
        url = str(seen[0].url)
        assert "from=2026-11-01" in url
        assert "to=2026-11-07" in url
        assert "rule=R-01" in url

    def test_post_discovery_body(self) -> None:
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(
                202,
                json={"run_id": "r-1", "status": "running", "started_at": "t0"},
            )

        with _client(httpx.MockTransport(handler)) as client:
            run = client.post_discovery(["192.168.1.10"], timeout_seconds=30)
        assert run.run_id == "r-1"
        assert json.loads(seen[0].content) == {"hosts": ["192.168.1.10"], "timeout_seconds": 30}


class TestApiErrors:
    def test_404_maps_to_api_status_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"detail": "not found"})

        with _client(httpx.MockTransport(handler)) as client, pytest.raises(ApiStatusError) as exc:
            client.get_asset("missing")
        assert exc.value.status_code == 404

    def test_503_preserves_runner_unavailable(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, json={"detail": "discovery runner not available"})

        with _client(httpx.MockTransport(handler)) as client, pytest.raises(ApiStatusError) as exc:
            client.post_discovery(["10.0.0.1"])
        assert exc.value.status_code == 503
        assert "runner" in exc.value.message

    def test_scope_violation_carries_code(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"detail": "out of scope", "code": "scope_violation"})

        with _client(httpx.MockTransport(handler)) as client, pytest.raises(ApiStatusError) as exc:
            client.post_discovery(["10.0.0.1"])
        assert exc.value.status_code == 400
        assert exc.value.response_code == "scope_violation"

    def test_5xx_is_api_status_not_core_unavailable(self) -> None:
        """503 de U2 (runner) pasa como status; no se convierte en 502."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"detail": "internal error"})

        with _client(httpx.MockTransport(handler)) as client, pytest.raises(ApiStatusError) as exc:
            client.get_health()
        assert exc.value.status_code == 500
