"""Tests de configuración fail-fast (BR-06, BR-07)."""

from __future__ import annotations

import pytest

from sentinel.foundation.config import Settings, load_settings
from sentinel.foundation.errors import ConfigError


def test_settings_fields_are_common_only() -> None:
    assert set(Settings.model_fields) == {"log_level", "component", "debug"}


def test_settings_frozen() -> None:
    settings = Settings()
    with pytest.raises(ValueError):
        settings.log_level = "DEBUG"  # type: ignore[misc]


def test_load_settings_defaults() -> None:
    settings = load_settings({})
    assert settings.log_level == "INFO"
    assert settings.component == "sentinel"
    assert settings.debug is False


def test_load_settings_from_env() -> None:
    settings = load_settings(
        {
            "SENTINEL_LOG_LEVEL": "DEBUG",
            "SENTINEL_COMPONENT": "core",
            "SENTINEL_DEBUG": "true",
        }
    )
    assert settings.log_level == "DEBUG"
    assert settings.component == "core"
    assert settings.debug is True


def test_invalid_log_level_raises_config_error() -> None:
    with pytest.raises(ConfigError) as exc_info:
        load_settings({"SENTINEL_LOG_LEVEL": "VERBOSE"})
    assert exc_info.value.code == "config_error"


def test_scope_keys_not_accepted() -> None:
    with pytest.raises(ValueError):
        Settings(log_level="INFO", scope_mode="explicit_hosts")  # type: ignore[call-arg]
