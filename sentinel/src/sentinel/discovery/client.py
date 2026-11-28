"""Cliente de ingesta del worker (U4, BR-U4-21/22, TS-U4-05).

Un solo ``POST /api/v1/ingest`` por ciclo con Bearer ``SENTINEL_INGEST_TOKEN``
y ``with_retries`` (×5, backoff ± jitter). Los 4xx son definitivos (sin
reintento); los 5xx/errores de red reintentan (D-U4-03).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from ipaddress import IPv4Address
from typing import Any

import httpx

from sentinel.discovery.domain import HostFinding
from sentinel.foundation.errors import IngestionError
from sentinel.foundation.models import DiscoveryObservation
from sentinel.foundation.retry import with_retries

__all__ = ["IngestClient", "to_observations"]

#: URL por defecto del Core (loopback); en K8s U9 inyecta ``SENTINEL_API_BASE``.
_DEFAULT_BASE_URL = "http://127.0.0.1:8080"

_RETRYABLE = (httpx.TransportError, httpx.HTTPStatusError)


def to_observations(
    findings: list[HostFinding], observed_at: datetime | None = None
) -> list[DiscoveryObservation]:
    """1 ``DiscoveryObservation`` por host (frontera Pydantic U1, D-U4-06/07)."""
    moment = observed_at if observed_at is not None else datetime.now(UTC)
    return [
        DiscoveryObservation(
            observed_at=moment,
            ip=IPv4Address(finding.ip),
            mac=finding.mac,
            hostname=finding.hostname,
            ports=finding.ports,
            os_name=finding.os_name,
            os_provenance=finding.os_provenance,
            method=finding.method,
        )
        for finding in findings
    ]


class IngestClient:
    """``POST /api/v1/ingest`` con token, reintento y ``reconcile`` (§3.5)."""

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._base_url = base_url or os.environ.get("SENTINEL_API_BASE", _DEFAULT_BASE_URL)
        self._token = token if token is not None else os.environ.get("SENTINEL_INGEST_TOKEN", "")
        self._http = httpx.Client(base_url=self._base_url, transport=transport, timeout=timeout)

    def post_ingest(self, items: list[DiscoveryObservation], *, reconcile: bool) -> dict[str, Any]:
        """Envía el lote único del ciclo; reintentos solo ante 5xx/red."""
        payload = {
            "items": [item.model_dump(mode="json") for item in items],
            "reconcile": reconcile,
        }
        headers = {"Authorization": f"Bearer {self._token}"}

        def _send() -> dict[str, Any]:
            response = self._http.post("/api/v1/ingest", json=payload, headers=headers)
            if 500 <= response.status_code < 600:
                raise httpx.HTTPStatusError(
                    f"ingest 5xx: {response.status_code}",
                    request=response.request,
                    response=response,
                )
            if response.status_code >= 400:
                raise IngestionError(
                    f"ingest rejected: {response.status_code} {response.text[:200]}"
                )
            return dict(response.json())

        return with_retries(
            _send,
            attempts=5,
            retry_on=_RETRYABLE,
            operation="ingest",
        )

    def close(self) -> None:
        self._http.close()
