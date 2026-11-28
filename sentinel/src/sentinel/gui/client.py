"""``GuiClient`` — cliente httpx síncrono contra la API loopback (P7/P10).

``API_BASE`` es constante (TS-U3-09) y **sobreescribible** por parámetro en
``create_app``/fixtures de tests (mismo patrón que ``metrics_port`` en U2).
Sin retry y sin caché (NFR-U3-AVAIL-01/SCAL-01): fallo de red/timeout ⇒
``CoreUnavailableError`` (502); 4xx/5xx de la API ⇒ ``ApiStatusError``.
"""

from __future__ import annotations

from typing import Any

import httpx

from sentinel.core.api.schemas import (
    AlertOut,
    AssetDetail,
    AssetSummary,
    DiscoveryRunStatus,
    EventOut,
    HealthStatus,
    Page,
    ResetResult,
)

from .errors import ApiStatusError, CoreUnavailableError

__all__ = ["API_BASE", "GuiClient"]

#: Loopback dentro del Pod (requirements §6.5 / TS-U3-09).
API_BASE = "http://127.0.0.1:8080"


class GuiClient:
    """Wrapper de ``httpx.Client`` con métodos tipados por endpoint."""

    def __init__(
        self,
        base_url: str = API_BASE,
        *,
        client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        if client is not None:
            # Cliente inyectado (tests con MockTransport): se reapunta a api_base.
            self._client = client
            self._client.base_url = base_url
        else:
            self._client = httpx.Client(base_url=base_url, transport=transport, timeout=timeout)

    @property
    def base_url(self) -> str:
        return str(self._client.base_url)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> GuiClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    # transporte
    # ------------------------------------------------------------------ #

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        try:
            resp = self._client.request(
                method, path, params=clean or None, json=json, headers=headers
            )
        except httpx.HTTPError as exc:
            raise CoreUnavailableError("core api unavailable") from exc
        if resp.status_code >= 400:
            detail, code = _error_body(resp)
            raise ApiStatusError(detail, status_code=resp.status_code, response_code=code)
        return resp

    def _get_model(self, model: Any, path: str, **params: Any) -> Any:
        resp = self._request("GET", path, params=params)
        return model.model_validate(resp.json())

    # ------------------------------------------------------------------ #
    # endpoints U2
    # ------------------------------------------------------------------ #

    def get_assets(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        status: str | None = None,
    ) -> Page[AssetSummary]:
        return self._get_model(
            Page[AssetSummary],
            "/api/v1/assets",
            limit=limit,
            offset=offset,
            status=status,
        )

    def get_asset(self, asset_id: str) -> AssetDetail:
        return self._get_model(AssetDetail, f"/api/v1/assets/{asset_id}")

    def get_events(
        self,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        asset_id: str | None = None,
        rule: str | None = None,
        severity: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Page[EventOut]:
        return self._get_model(
            Page[EventOut],
            "/api/v1/events",
            **{
                "from": date_from,
                "to": date_to,
                "asset_id": asset_id,
                "rule": rule,
                "severity": severity,
                "limit": limit,
                "offset": offset,
            },
        )

    def get_alerts(
        self,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        state: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Page[AlertOut]:
        return self._get_model(
            Page[AlertOut],
            "/api/v1/alerts",
            **{"from": date_from, "to": date_to, "state": state, "limit": limit, "offset": offset},
        )

    def get_health(self) -> HealthStatus:
        return self._get_model(HealthStatus, "/api/v1/health")

    def post_discovery(self, hosts: list[str], *, timeout_seconds: int = 30) -> DiscoveryRunStatus:
        resp = self._request(
            "POST",
            "/api/v1/discovery",
            json={"hosts": hosts, "timeout_seconds": timeout_seconds},
        )
        return DiscoveryRunStatus.model_validate(resp.json())

    def get_discovery_run(self, run_id: str) -> DiscoveryRunStatus:
        return self._get_model(DiscoveryRunStatus, f"/api/v1/discovery/{run_id}")

    def reset_scenario(self, token: str) -> ResetResult:
        """Borra los datos derivados del escenario (Bearer de ingesta)."""
        resp = self._request(
            "POST",
            "/api/v1/admin/reset",
            headers={"Authorization": f"Bearer {token}"},
        )
        return ResetResult.model_validate(resp.json())


def _error_body(resp: httpx.Response) -> tuple[str, str | None]:
    """Extrae ``(detail, code)`` del cuerpo de error de U2 (o genérico)."""
    detail = f"api error {resp.status_code}"
    code: str | None = None
    try:
        body = resp.json()
        if isinstance(body, dict):
            raw = body.get("detail")
            if isinstance(raw, str):
                detail = raw
            elif raw is not None:
                detail = str(raw)
            got = body.get("code")
            if isinstance(got, str):
                code = got
    except ValueError:
        pass
    return detail, code
