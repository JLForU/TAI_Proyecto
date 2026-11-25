"""Configuración estricta del sensor de tráfico (U5, BR-U5-01..05).

Patrón ``foundation.config``: ``frozen`` + ``extra="forbid"``, fail-fast con
``ConfigError`` — con config inválida nada se captura. ``CoreSettings`` de U1
no cambia (BR-U5-04); ``SENTINEL_API_BASE``/``SENTINEL_INGEST_TOKEN`` se leen
en ``client.py`` sin redefinir (mismo patrón que U4).
"""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from sentinel.foundation.errors import ConfigError

__all__ = ["WINDOW_VALUES", "TrafficSettings", "load_traffic_settings"]

#: Ventanas tumbling admitidas (BR-U5-02); este validador es el que está
#: detrás de ``helm lint --set traffic.window=7s`` en U9/Build & Test.
WINDOW_VALUES: tuple[int, ...] = (1, 5, 10, 30, 60)

_ENV_MAP = {
    "SENTINEL_TRAFFIC_WINDOW_SECONDS": "window_seconds",
    "SENTINEL_TRAFFIC_INTERFACE": "interface",
    "SENTINEL_TRAFFIC_SENSOR_ID": "sensor_id",
    "SENTINEL_TRAFFIC_SIM_SEED": "sim_seed",
    "SENTINEL_TRAFFIC_SIM_RATE": "sim_rate",
    "SENTINEL_TRAFFIC_FALLBACK": "fallback",
}


class TrafficSettings(BaseModel):
    """Settings del sensor (domain-entities §1.1)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    window_seconds: int = 5
    interface: str = "eth0"
    sensor_id: str = "sensor-0"
    sim_seed: int = 42
    sim_rate: float = 50.0
    fallback: bool = True


def _validate_business_rules(settings: TrafficSettings) -> None:
    if settings.window_seconds not in WINDOW_VALUES:
        raise ConfigError(
            f"SENTINEL_TRAFFIC_WINDOW_SECONDS must be one of {WINDOW_VALUES}"
            f" (got {settings.window_seconds})"
        )
    if not settings.interface.strip() or len(settings.interface) > 255:
        raise ConfigError("SENTINEL_TRAFFIC_INTERFACE must be non-empty (<= 255 chars)")
    if not settings.sensor_id.strip() or len(settings.sensor_id) > 255:
        raise ConfigError("SENTINEL_TRAFFIC_SENSOR_ID must be non-empty (<= 255 chars)")
    if settings.sim_seed < 0:
        raise ConfigError("SENTINEL_TRAFFIC_SIM_SEED must be >= 0")
    if settings.sim_rate <= 0:
        raise ConfigError("SENTINEL_TRAFFIC_SIM_RATE must be > 0")
    if not settings.fallback:
        raise ConfigError(
            "SENTINEL_TRAFFIC_FALLBACK=false: real capture is documented, not implemented (D-U5-07)"
        )


def load_traffic_settings(environ: dict[str, str] | None = None) -> TrafficSettings:
    """Carga ``TrafficSettings`` desde ``SENTINEL_TRAFFIC_*`` (fail-fast, BR-U5-01).

    Lanza :class:`ConfigError` ante clave desconocida, ventana fuera de
    ``WINDOW_VALUES``, ``sim_rate <= 0``, ``sim_seed < 0``, campos vacíos o
    ``FALLBACK=false`` (D-U5-07).
    """
    env = os.environ if environ is None else environ
    unknown = sorted(
        key for key in env if key.startswith("SENTINEL_TRAFFIC_") and key not in _ENV_MAP
    )
    if unknown:
        raise ConfigError(f"unknown traffic settings: {', '.join(unknown)}")
    data: dict[str, Any] = {
        field: env[env_key] for env_key, field in _ENV_MAP.items() if env_key in env
    }
    try:
        settings = TrafficSettings.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"invalid traffic settings: {exc}") from exc
    _validate_business_rules(settings)
    return settings
