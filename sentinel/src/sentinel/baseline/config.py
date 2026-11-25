"""Configuración estricta del servicio de baseline (U6, BR-U6-02..04, FD §3.1).

Patrón ``foundation.config``: ``frozen`` + ``extra="forbid"``, fail-fast con
``ConfigError``. ``ABSOLUTE_BPS`` **sin default numérico** (PRD §3.3: sin
umbrales arbitrarios en el código — el valor llega de ``values.yaml``).
``CoreSettings`` de U1 no cambia (BR-U6-02).
"""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from sentinel.foundation.errors import ConfigError

__all__ = ["BASELINE_SAMPLES", "BaselineSettings", "load_baseline_settings"]

_ENV_MAP = {
    "SENTINEL_BASELINE_K": "k",
    "SENTINEL_BASELINE_ABSOLUTE_BPS": "absolute_bps",
    "SENTINEL_BASELINE_INTERVAL_SECONDS": "interval_seconds",
    "SENTINEL_BASELINE_COLLECTOR_TIMEOUT_SECONDS": "collector_timeout_seconds",
}

#: Muestras para establecer la baseline (FR-BASE-01/ST-M5-01, FD §3.1):
#: constante de dominio, no env.
BASELINE_SAMPLES = 5


class BaselineSettings(BaseModel):
    """Settings del ``ConditionService`` (FD §3.1 / NFR-U6-SEC-02)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    k: float = 3.0
    absolute_bps: float | None = None
    interval_seconds: int = 5
    collector_timeout_seconds: int = 300


def _validate_business_rules(settings: BaselineSettings) -> None:
    if settings.k <= 0:
        raise ConfigError("SENTINEL_BASELINE_K must be > 0")
    if settings.absolute_bps is not None and settings.absolute_bps <= 0:
        raise ConfigError("SENTINEL_BASELINE_ABSOLUTE_BPS must be > 0 when present")
    if settings.interval_seconds < 1:
        raise ConfigError("SENTINEL_BASELINE_INTERVAL_SECONDS must be >= 1")
    if settings.collector_timeout_seconds < 1:
        raise ConfigError("SENTINEL_BASELINE_COLLECTOR_TIMEOUT_SECONDS must be >= 1")


def _parse(env_key: str, field: str, raw: str) -> Any:
    value = raw.strip()
    # Opcional: cadena vacía equivale a ausente (fallback no disponible).
    if field == "absolute_bps" and not value:
        return None
    try:
        if field in {"k", "absolute_bps"}:
            return float(value)
        return int(value)
    except ValueError as exc:
        raise ConfigError(f"invalid {env_key}: {raw!r}") from exc


def load_baseline_settings(environ: dict[str, str] | None = None) -> BaselineSettings:
    """Carga ``BaselineSettings`` desde ``SENTINEL_BASELINE_*`` (fail-fast).

    Lanza :class:`ConfigError` ante clave desconocida, valor no numérico o
    violación de rangos (BR-U6-03/04).
    """
    env = os.environ if environ is None else environ
    unknown = sorted(
        key for key in env if key.startswith("SENTINEL_BASELINE_") and key not in _ENV_MAP
    )
    if unknown:
        raise ConfigError(f"unknown baseline settings: {', '.join(unknown)}")
    data: dict[str, Any] = {}
    for env_key, field in _ENV_MAP.items():
        if env_key in env:
            data[field] = _parse(env_key, field, env[env_key])
    try:
        settings = BaselineSettings.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"invalid baseline settings: {exc}") from exc
    _validate_business_rules(settings)
    return settings
