"""U6 — Baseline & deterministic conditions (R-01, GT-04).

Frontera (BR-U6-01, unit-of-work §imports): todo el paquete importa solo
``sentinel.foundation`` y stdlib — nunca ``sentinel.core`` ni ``sqlite3``.
Los repos y el reloj llegan inyectados como ``Protocol`` duck-typing desde
``core/api/app.py`` (composición core→baseline, nunca al revés).
"""

from __future__ import annotations

from sentinel.baseline.conditions import ConditionService, SystemClock
from sentinel.baseline.config import BASELINE_SAMPLES, BaselineSettings, load_baseline_settings
from sentinel.baseline.statistics import mean, sample_variance, select_threshold

__all__ = [
    "BASELINE_SAMPLES",
    "BaselineSettings",
    "ConditionService",
    "SystemClock",
    "load_baseline_settings",
    "mean",
    "sample_variance",
    "select_threshold",
]
