"""Estadística pura de la línea base (U6, FR-BASE-02/03, BR-U6-06..10, P15).

Funciones sin estado ni I/O: media, varianza muestral (denominador ``n-1``)
y selección de umbral (``μ + k·s`` con fallback absoluto). Solo stdlib —
blanco del PBT designado (NFR-TECH-03).
"""

from __future__ import annotations

__all__ = ["mean", "sample_variance", "select_threshold"]


def mean(xs: list[float]) -> float:
    """Media aritmética; lista vacía ⇒ 0.0 (sin muestras no hay serie)."""
    if not xs:
        return 0.0
    return sum(xs) / len(xs)


def sample_variance(xs: list[float]) -> float:
    """Varianza muestral ``s² = Σ(x-μ)² / (n-1)`` (FR-BASE-02).

    ``n < 2`` ⇒ 0.0 (con una muestra no hay dispersión estimable).
    """
    n = len(xs)
    if n < 2:
        return 0.0
    mu = mean(xs)
    return sum((x - mu) ** 2 for x in xs) / (n - 1)


def select_threshold(
    mu: float,
    sigma: float,
    k: float,
    absolute: float | None,
    *,
    established: bool,
) -> float | None:
    """Umbral efectivo de la serie (FR-BASE-03, BR-U6-09/10).

    - establecida ⇒ ``mu + k * sigma`` (relativo);
    - no establecida ⇒ ``absolute`` si está configurado (fallback), si no
      ``None`` (sin umbral disponible ⇒ evaluación ``no_data``).
    """
    if established:
        return mu + k * sigma
    return absolute
