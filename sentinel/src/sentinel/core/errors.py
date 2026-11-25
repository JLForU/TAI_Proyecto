"""Excepciones de dominio del Core (mapeadas a HTTP en ``api/errors.py``)."""

from __future__ import annotations

from sentinel.foundation.errors import SentinelError

__all__ = [
    "ConflictError",
    "NotFoundError",
    "RunnerUnavailableError",
]


class NotFoundError(SentinelError):
    """Recurso inexistente (asset_id, run_id) ⇒ 404."""

    code = "not_found"


class ConflictError(SentinelError):
    """Estado en conflicto (discovery ya en curso) ⇒ 409."""

    code = "conflict"


class RunnerUnavailableError(SentinelError):
    """``CycleRunner`` no inyectado (U4 pendiente) ⇒ 503."""

    code = "runner_unavailable"
