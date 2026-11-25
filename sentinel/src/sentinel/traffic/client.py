"""Cliente de export del sensor (U5, BR-U5-23..26, P13, TS-U5-06).

1 ``POST /api/v1/ingest`` por ventana con lote mixto ``traffic``+``arp``
(BR-U5-23); chunking ≤ ``MAX_BATCH_ITEMS`` por POST secuencial (P13);
Bearer ``SENTINEL_INGEST_TOKEN``; ``with_retries`` ×5 — los 4xx son
definitivos sin reintento. El body **no envía ``reconcile``** (BR-U5-26):
los lotes del sensor jamás incrementan ``miss_count``.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

import httpx

from sentinel.foundation.errors import IngestionError
from sentinel.foundation.models import MAX_BATCH_ITEMS, Observation
from sentinel.foundation.retry import with_retries

__all__ = ["IngestClient"]

#: URL por defecto del Core (loopback); en K8s U9 inyecta ``SENTINEL_API_BASE``.
_DEFAULT_BASE_URL = "http://127.0.0.1:8080"

_RETRYABLE = (httpx.TransportError, httpx.HTTPStatusError)


class IngestClient:
    """``POST /api/v1/ingest`` con token, reintento y chunking (FD §3.5)."""

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

    def post_batch(self, items: Sequence[Observation]) -> dict[str, Any]:
        """Envía la ventana en chunks ≤1000; reintentos solo ante 5xx/red."""
        if not items:
            return {"accepted": 0, "deduplicated": 0, "events_persisted": 0}
        headers = {"Authorization": f"Bearer {self._token}"}
        totals: dict[str, Any] = {
            "accepted": 0,
            "deduplicated": 0,
            "events_persisted": 0,
        }
        for start in range(0, len(items), MAX_BATCH_ITEMS):
            chunk = items[start : start + MAX_BATCH_ITEMS]
            # sin clave "reconcile" en el body (BR-U5-26)
            payload = {"items": [item.model_dump(mode="json") for item in chunk]}

            def _send(payload: dict[str, Any] = payload) -> dict[str, Any]:
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

            result = with_retries(
                _send,
                attempts=5,
                retry_on=_RETRYABLE,
                operation="ingest",
            )
            for key in totals:
                totals[key] += int(result.get(key, 0))
        return totals

    def close(self) -> None:
        self._http.close()
