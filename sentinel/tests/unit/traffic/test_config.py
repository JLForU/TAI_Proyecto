"""Configuración estricta del sensor (U5, BR-U5-01..05/36)."""

from __future__ import annotations

import pytest

from sentinel.foundation.errors import ConfigError
from sentinel.traffic.config import WINDOW_VALUES, TrafficSettings, load_traffic_settings


def test_defaults() -> None:
    settings = load_traffic_settings({})
    assert settings.window_seconds == 5
    assert settings.interface == "eth0"
    assert settings.sensor_id == "sensor-0"
    assert settings.sim_seed == 42
    assert settings.sim_rate == 50.0
    assert settings.fallback is True


def test_sensor_id_default() -> None:
    assert load_traffic_settings({}).sensor_id == "sensor-0"
    custom = load_traffic_settings({"SENTINEL_TRAFFIC_SENSOR_ID": "sensor-9"})
    assert custom.sensor_id == "sensor-9"


def test_window_values() -> None:
    for value in WINDOW_VALUES:
        settings = load_traffic_settings({"SENTINEL_TRAFFIC_WINDOW_SECONDS": str(value)})
        assert settings.window_seconds == value


def test_window_seven_rejected() -> None:
    with pytest.raises(ConfigError, match="WINDOW_SECONDS"):
        load_traffic_settings({"SENTINEL_TRAFFIC_WINDOW_SECONDS": "7"})


def test_invalid_config() -> None:
    with pytest.raises(ConfigError, match="SIM_SEED"):
        load_traffic_settings({"SENTINEL_TRAFFIC_SIM_SEED": "-1"})
    with pytest.raises(ConfigError, match="INTERFACE"):
        load_traffic_settings({"SENTINEL_TRAFFIC_INTERFACE": "   "})
    with pytest.raises(ConfigError, match="SENSOR_ID"):
        load_traffic_settings({"SENTINEL_TRAFFIC_SENSOR_ID": ""})


def test_fallback_false_rejected() -> None:
    with pytest.raises(ConfigError, match="FALLBACK"):
        load_traffic_settings({"SENTINEL_TRAFFIC_FALLBACK": "false"})


def test_strict_env() -> None:
    with pytest.raises(ConfigError, match="unknown"):
        load_traffic_settings({"SENTINEL_TRAFFIC_WINDOW_SECS": "5"})


def test_sim_rate_positive() -> None:
    settings = load_traffic_settings({"SENTINEL_TRAFFIC_SIM_RATE": "500.5"})
    assert settings.sim_rate == 500.5
    with pytest.raises(ConfigError, match="SIM_RATE"):
        load_traffic_settings({"SENTINEL_TRAFFIC_SIM_RATE": "0"})


def test_settings_are_frozen() -> None:
    import pydantic

    settings = TrafficSettings()
    with pytest.raises(pydantic.ValidationError):
        settings.window_seconds = 10  # type: ignore[misc]
