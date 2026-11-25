"""Estadística pura del baseline (U6, FR-BASE-02/03): media, s², umbral."""

from __future__ import annotations

import math

from sentinel.baseline.statistics import mean, sample_variance, select_threshold


def test_mean_values() -> None:
    assert mean([1.0, 2.0, 3.0]) == 2.0
    assert mean([10.0]) == 10.0
    assert mean([]) == 0.0


def test_variance_sample() -> None:
    # s² con denominador n-1: [1,2,3] ⇒ μ=2, Σ(x-μ)²=2, /(3-1)=1.0
    assert sample_variance([1.0, 2.0, 3.0]) == 1.0
    assert sample_variance([2.0, 2.0, 2.0]) == 0.0


def test_variance_single() -> None:
    assert sample_variance([5.0]) == 0.0
    assert sample_variance([]) == 0.0


def test_variance_matches_brute_force() -> None:
    xs = [10.0, 12.5, 9.0, 15.5, 11.0]
    mu = sum(xs) / len(xs)
    expected = sum((x - mu) ** 2 for x in xs) / (len(xs) - 1)
    assert math.isclose(sample_variance(xs), expected, rel_tol=1e-12)


def test_threshold_relative() -> None:
    # μ=10, s=2, k=3 ⇒ 16
    assert select_threshold(10.0, 2.0, 3.0, None, established=True) == 16.0


def test_threshold_absolute_fallback() -> None:
    assert select_threshold(10.0, 2.0, 3.0, 1_000.0, established=False) == 1_000.0


def test_threshold_none() -> None:
    # No establecida y sin absoluto ⇒ sin umbral (no_data).
    assert select_threshold(10.0, 2.0, 3.0, None, established=False) is None


def test_threshold_prefers_relative_when_established() -> None:
    # Establecida gana sobre el absoluto (FD §3.4).
    assert select_threshold(10.0, 0.0, 3.0, 999.0, established=True) == 10.0


def test_strict_comparison() -> None:
    # R-01 usa comparación estricta `>` (Q12=A): igual ⇒ no dispara.
    threshold = 100.0
    measured = 99.9
    assert not (measured > threshold)
    measured = 100.0
    assert not (measured > threshold)
    measured = 100.1
    assert measured > threshold
