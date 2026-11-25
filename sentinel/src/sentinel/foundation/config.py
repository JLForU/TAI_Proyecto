"""Configuración común de Sentinel (P1 — fail-fast, BR-06..BR-08).

Solo define las claves comunes: ``log_level``, ``component``, ``debug``.
Las claves ``scope.*``, ``discovery.*``, ``traffic.*``, ``gui.*`` viven en
cada unidad que las necesite (U4/U5/U3), reutilizando este patrón.
"""

from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from sentinel.foundation.errors import ConfigError

__all__ = ["Settings", "load_settings"]

EnvLogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]

_ENV_MAP = {
    "SENTINEL_LOG_LEVEL": "log_level",
    "SENTINEL_COMPONENT": "component",
    "SENTINEL_DEBUG": "debug",
}


class Settings(BaseModel):
    """Settings comunes de cualquier workload de Sentinel."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    log_level: EnvLogLevel = "INFO"
    component: str = "sentinel"
    debug: bool = False


def _env_to_dict(environ: dict[str, str]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for env_key, field in _ENV_MAP.items():
        if env_key in environ:
            data[field] = environ[env_key]
    return data


def load_settings(environ: dict[str, str] | None = None) -> Settings:
    """Carga ``Settings`` desde variables de entorno ``SENTINEL_*``.

    Lanza :class:`ConfigError` si la configuración es inválida (fail-fast,
    BR-07): una config inválida no es un estado recuperable.
    """
    env = os.environ if environ is None else environ
    try:
        return Settings.model_validate(_env_to_dict(dict(env)))
    except ValidationError as exc:
        raise ConfigError(f"invalid sentinel settings: {exc}") from exc
