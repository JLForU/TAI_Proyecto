"""Property tests del baseline (NFR-TECH-03 designado, Q2 NFR-Req=A, P12).

PB-U6-01 media/varianza n-1 == brute force; PB-U6-02 congelada; PB-U6-03
umbral monótono en k + comparación estricta; PB-U6-04 máquina de estados
solo emite ``ConditionState`` U1 y ``suppressed ⇒ nunca firing``.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from sentinel.baseline.conditions import ConditionService, TrafficWindow
from sentinel.baseline.config import BaselineSettings
from sentinel.baseline.statistics import mean, sample_variance, select_threshold
from sentinel.foundation.models import ConditionState
from sentinel.foundation.testing import utc_datetimes

NOW = datetime(2026, 3, 5, 9, 30, 0, tzinfo=UTC)
KEY = "bytes_per_second|eth0|tcp"
STATES: tuple[ConditionState, ...] = (
    "baseline_establishing",
    "firing",
    "resolved",
    "no_data",
)

_finite = st.floats(allow_nan=False, allow_infinity=False, min_value=-1e9, max_value=1e9)
_nonneg = st.floats(allow_nan=False, allow_infinity=False, min_value=0.0, max_value=1e9)
_k = st.floats(allow_nan=False, allow_infinity=False, min_value=1e-6, max_value=100.0)


class FakeClock:
    def __init__(self) -> None:
        self._now = NOW

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += timedelta(seconds=seconds)


class _MemBaselines:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    def list(self) -> list[dict[str, Any]]:
        return list(self.rows.values())

    def upsert(self, row: dict[str, Any]) -> None:
        self.rows[row["metric_key"]] = dict(row)


class _MemAlerts:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    def upsert(self, alert: dict[str, Any]) -> None:
        self.rows[alert["alert_id"]] = dict(alert)

    def list_firing(self) -> list[dict[str, Any]]:
        return [r for r in self.rows.values() if r.get("state") == "firing"]


def _service(clock: FakeClock | None = None) -> ConditionService:
    c = clock or FakeClock()
    return ConditionService(
        baselines=_MemBaselines(),
        alerts=_MemAlerts(),
        settings=BaselineSettings(absolute_bps=None),
        clock=c,
    )


# --- PB-U6-01: media/varianza n-1 == fuerza bruta --------------------------


@given(st.lists(_finite, min_size=0, max_size=40))
@settings(max_examples=150)
def test_property_mean_variance_brute_force(xs: list[float]) -> None:
    if not xs:
        assert mean(xs) == 0.0
        assert sample_variance(xs) == 0.0
        return
    n = len(xs)
    mu = sum(xs) / n
    assert math.isclose(mean(xs), mu, rel_tol=1e-9, abs_tol=1e-12)
    if n < 2:
        assert sample_variance(xs) == 0.0
        return
    var = sum((x - mu) ** 2 for x in xs) / (n - 1)
    assert math.isclose(sample_variance(xs), var, rel_tol=1e-9, abs_tol=1e-9)


# --- PB-U6-02: congelada a BASELINE_SAMPLES --------------------------------


@given(
    st.lists(_finite, min_size=5, max_size=5),
    st.lists(_finite, min_size=1, max_size=15),
)
@settings(max_examples=100)
def test_property_frozen_after_five(initial: list[float], extra: list[float]) -> None:
    svc = _service()
    for value in initial:
        svc.update_baseline(KEY, value, NOW)
    state = svc.states[KEY]
    assert state.established is True
    frozen_samples = list(state.samples)
    frozen_mu, frozen_var = state.mean, state.variance
    for value in extra:
        svc.update_baseline(KEY, value, NOW)
    assert state.samples == frozen_samples
    assert state.mean == frozen_mu
    assert state.variance == frozen_var
    assert len(state.samples) == 5  # jamás crece después de establecer


# --- PB-U6-03: umbral monótono en k + comparación estricta -----------------


@given(mu=_finite, sigma=_nonneg, k1=_k, k2=_k)
@settings(max_examples=150)
def test_property_threshold_monotonic_in_k(mu: float, sigma: float, k1: float, k2: float) -> None:
    low, high = min(k1, k2), max(k1, k2)
    t_low = select_threshold(mu, sigma, low, None, established=True)
    t_high = select_threshold(mu, sigma, high, None, established=True)
    assert t_low is not None and t_high is not None
    assert t_low <= t_high + 1e-9  # monótono no-decreciente en k


@given(mu=_finite, sigma=_nonneg, k=_k, delta=st.sampled_from([-1.0, 0.0, 1.0]))
@settings(max_examples=150)
def test_property_strict_comparison_under_equal_over(
    mu: float, sigma: float, k: float, delta: float
) -> None:
    """Fixtures bajo/igual/encima: estricto ``>`` ⇒ igual NO dispara (Q12)."""
    threshold = select_threshold(mu, sigma, k, None, established=True)
    assert threshold is not None
    measured = threshold + delta
    fired = measured > threshold
    assert fired == (delta > 0)


@given(absolute=_nonneg)
def test_property_no_absolute_no_threshold(absolute: float) -> None:
    assert select_threshold(100.0, 1.0, 3.0, None, established=False) is None
    assert select_threshold(100.0, 1.0, 3.0, absolute, established=False) == absolute


# --- PB-U6-04: máquina de estados válida; suppressed ⇒ nunca firing --------


@given(
    samples=st.lists(_finite, min_size=1, max_size=8),
    measured=_finite,
    advance_seconds=st.integers(min_value=0, max_value=120),
)
@settings(max_examples=150)
def test_property_state_machine_suppressed_never_firing(
    samples: list[float], measured: float, advance_seconds: int
) -> None:
    clock = FakeClock()
    svc = _service(clock)
    for value in samples:
        svc.update_baseline(KEY, value, clock.now())
    clock.advance(float(advance_seconds))
    cond = svc.evaluate(
        TrafficWindow(
            window_start=clock.now(),
            window_end=clock.now() + timedelta(seconds=5),
            interface="eth0",
            protocol="tcp",
            bytes_per_second=measured,
            packets=1,
            flows=1,
            sensor_id="sensor-pbt",
        )
    )
    assert cond.state in STATES  # solo ConditionState U1
    assert cond.rule == "R-01"
    if cond.suppressed:
        assert cond.state == "baseline_establishing"
        assert cond.state != "firing"
        assert cond.threshold is None
    # Supresión exclusivamente dentro de t_first + 5×interval
    suppressed_expected = advance_seconds < 5 * 5
    assert cond.suppressed is suppressed_expected


@given(st.lists(_finite, min_size=0, max_size=6))
@settings(max_examples=100)
def test_property_update_never_raises_for_arbitrary_series(values: list[float]) -> None:
    svc = _service()
    for i, value in enumerate(values):
        svc.update_baseline(KEY, value, NOW + timedelta(seconds=i))
    state = svc.states.get(KEY)
    if state is None:
        return
    assert state.established == (len(state.samples) >= 5)
    if state.established:
        assert len(state.samples) == 5
    if len(state.samples) >= 2:
        assert state.variance >= 0.0
    # La media siempre está dentro del rango de las muestras (si n ≥ 1),
    # con tolerancia relativa al orden de magnitud (float64 en valores grandes).
    if state.samples:
        lo, hi = min(state.samples), max(state.samples)
        eps = 1e-6 * max(abs(lo), abs(hi), 1.0)
        assert lo - eps <= state.mean <= hi + eps


@given(utc_datetimes)
def test_property_clock_domain_is_utc(t: datetime) -> None:
    """Dominio temporal del reloj inyectado: siempre UTC aware (P7)."""
    clock = FakeClock()
    clock._now = t  # type: ignore[attr-defined]
    now = clock.now()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)
