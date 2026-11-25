"""Jerarquía de excepciones de dominio de Sentinel (BR-23, BR-24).

Toda falla de negocio se lanza como subtipo de ``SentinelError`` con un
``code`` estable. Foundation no conoce FastAPI ni traduce a HTTP (U2 lo hace).
"""

from __future__ import annotations

__all__ = [
    "ConfigError",
    "IngestionError",
    "ProbeError",
    "ScopeError",
    "SentinelError",
    "StorageError",
    "ValidationError",
]


class SentinelError(Exception):
    """Base de todos los errores de dominio de Sentinel."""

    code: str = "sentinel_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code


class ConfigError(SentinelError):
    """Settings inválidos (fail-fast al arranque)."""

    code = "config_error"


class ScopeError(SentinelError):
    """Alcance violado / host fuera de allowlist (usa U4)."""

    code = "scope_violation"


class ValidationError(SentinelError):
    """Payload de observación inválido (usa U2/U4/U5)."""

    code = "validation_error"


class ProbeError(SentinelError):
    """Fallo de sondeo (nmap/arp/icmp) (usa U4)."""

    code = "probe_error"


class IngestionError(SentinelError):
    """Fallo de ingesta o reintento agotado (usa U2/U4/U5)."""

    code = "ingestion_error"


class StorageError(SentinelError):
    """Fallo de persistencia (usa U2)."""

    code = "storage_error"
