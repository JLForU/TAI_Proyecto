"""Helpers compartidos de los repositorios de U2."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

__all__ = ["dumps", "iso_now", "loads", "normalize_iso"]


def iso_now() -> str:
    return datetime.now(UTC).isoformat()


def dumps(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def loads(value: str) -> Any:
    return json.loads(value)


def normalize_iso(value: str) -> str:
    """Normaliza un filtro temporal a ISO 8601 UTC con offset ``+00:00``.

    Acepta ``...Z`` o offset; así las comparaciones lexicográficas contra lo
    almacenado (``datetime.isoformat()``) son correctas.
    """
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()
