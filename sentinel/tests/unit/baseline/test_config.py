"""Config estricta del baseline (U6, BR-U6-02..04): fail-fast con ConfigError."""

from __future__ import annotations

import pytest

from sentinel.baseline.config import BASELINE_SAMPLES, BaselineSettings, load_baseline_settings
from sentinel.foundation.errors import ConfigError


def test_defaults() -> None:
    settings = load_baseline_settings({})
    assert settings.k == 3.0
    assert settings.absolute_bps is None
    assert settings.interval_seconds == 5
    assert settings.collector_timeout_seconds == 300


def test_defaults_without_env_keys() -> None:
    settings = BaselineSettings()
    assert (settings.k, settings.absolute_bps, settings.interval_seconds) == (3.0, None, 5)
    assert settings.collector_timeout_seconds == 300


def test_samples_constant() -> None:
    # FR-BASE-01/ST-M5-01: 5 muestras es constante de dominio, no env.
    assert BASELINE_SAMPLES == 5


def test_strict_env() -> None:
    with pytest.raises(ConfigError, match="unknown baseline settings"):
        load_baseline_settings({"SENTINEL_BASELINE_FOO": "1"})


@pytest.mark.parametrize(
    "env",
    [
        {"SENTINEL_BASELINE_K": "0"},
        {"SENTINEL_BASELINE_K": "-1.5"},
        {"SENTINEL_BASELINE_K": "abc"},
        {"SENTINEL_BASELINE_ABSOLUTE_BPS": "-1"},
        {"SENTINEL_BASELINE_ABSOLUTE_BPS": "abc"},
        {"SENTINEL_BASELINE_INTERVAL_SECONDS": "0"},
        {"SENTINEL_BASELINE_INTERVAL_SECONDS": "x"},
        {"SENTINEL_BASELINE_COLLECTOR_TIMEOUT_SECONDS": "0"},
    ],
)
def test_invalid_config(env: dict[str, str]) -> None:
    with pytest.raises(ConfigError):
        load_baseline_settings(env)


def test_absolute_optional() -> None:
    assert load_baseline_settings({}).absolute_bps is None
    assert load_baseline_settings({"SENTINEL_BASELINE_ABSOLUTE_BPS": "1000000"}).absolute_bps == (
        1_000_000.0
    )
    # Cadena vacía equivale a ausente (fallback no disponible).
    assert load_baseline_settings({"SENTINEL_BASELINE_ABSOLUTE_BPS": ""}).absolute_bps is None


def test_full_env() -> None:
    settings = load_baseline_settings(
        {
            "SENTINEL_BASELINE_K": "2.5",
            "SENTINEL_BASELINE_ABSOLUTE_BPS": "500000",
            "SENTINEL_BASELINE_INTERVAL_SECONDS": "10",
            "SENTINEL_BASELINE_COLLECTOR_TIMEOUT_SECONDS": "60",
        }
    )
    assert (settings.k, settings.absolute_bps) == (2.5, 500_000.0)
    assert (settings.interval_seconds, settings.collector_timeout_seconds) == (10, 60)


def test_frozen_and_forbid() -> None:
    from pydantic import ValidationError

    settings = BaselineSettings()
    with pytest.raises(ValidationError):
        settings.k = 5.0  # type: ignore[misc]
    with pytest.raises(ValidationError):
        BaselineSettings(extra_field=1)  # type: ignore[call-arg]
