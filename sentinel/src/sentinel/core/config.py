"""Configuración de U2 (Core) — patrón de ``foundation.config`` (Q13 FD, BR-U2-41).

Exactamente cuatro claves ``SENTINEL_*``; fail-fast con ``ConfigError``.
Las claves comunes (log/component/debug) siguen en ``foundation.config`` (BR-06).
"""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from sentinel.foundation.errors import ConfigError

__all__ = ["CoreSettings", "load_core_settings"]

_ENV_MAP = {
    "SENTINEL_DB_PATH": "db_path",
    "SENTINEL_INGEST_TOKEN": "ingest_token",
    "SENTINEL_PAGE_LIMIT": "page_limit",
    "SENTINEL_MISSING_CYCLES": "missing_cycles",
}


class CoreSettings(BaseModel):
    """Settings del Core (U2)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    db_path: str = Field(default="/data/sentinel.db", min_length=1)
    ingest_token: str = ""
    page_limit: int = Field(default=100, ge=1, le=1000)
    missing_cycles: int = Field(default=3, ge=1)


def _env_to_dict(environ: dict[str, str]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for env_key, field in _ENV_MAP.items():
        if env_key in environ:
            data[field] = environ[env_key]
    return data


def load_core_settings(environ: dict[str, str] | None = None) -> CoreSettings:
    """Carga ``CoreSettings`` desde variables de entorno ``SENTINEL_*``.

    Lanza :class:`ConfigError` si la configuración es inválida (fail-fast).
    """
    env = os.environ if environ is None else environ
    try:
        return CoreSettings.model_validate(_env_to_dict(dict(env)))
    except ValidationError as exc:
        raise ConfigError(f"invalid core settings: {exc}") from exc
