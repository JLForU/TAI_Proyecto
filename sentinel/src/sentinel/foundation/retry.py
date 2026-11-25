"""Primitiva de reintento con backoff exponencial + jitter (P3).

Stdlib puro (``time.sleep``, ``random.uniform``); sin I/O de red: el
``fn`` lo aporta cada colector (U4/U5 envían lotes al Core). No persiste
lotes perdidos (responsabilidad del buffer del colector).
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

from sentinel.foundation.errors import IngestionError

__all__ = ["with_retries"]

T = TypeVar("T")


def with_retries(
    fn: Callable[[], T],
    *,
    attempts: int = 5,
    base_delay: float = 0.5,
    max_delay: float = 30.0,
    jitter: bool = True,
    retry_on: tuple[type[Exception], ...] = (Exception,),
    operation: str = "operation",
) -> T:
    """Ejecuta ``fn`` reintentando con backoff ``min(base*2**n, max)`` ± jitter.

    Devuelve el primer resultado exitoso. Si se agotan los intentos, lanza
    :class:`IngestionError` envolviendo la última excepción (BR-23: nunca
    excepción de dominio sin envolver). Las excepciones fuera de ``retry_on``
    propagan sin reintento.
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")

    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except retry_on as exc:
            last_exc = exc
        if attempt == attempts - 1:
            break
        delay = min(base_delay * (2**attempt), max_delay)
        if jitter:
            delay = max(0.0, delay + random.uniform(-0.1 * delay, 0.1 * delay))
        time.sleep(delay)

    raise IngestionError(
        f"{operation} failed after {attempts} attempts: {last_exc}",
        code="ingestion_error",
    ) from last_exc
